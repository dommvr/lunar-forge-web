"""Upstash-compatible Redis streams, controls, tickets, limits, and leases."""

from __future__ import annotations

import asyncio
import hashlib
import json
import re
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Any, Protocol

from pydantic import ValidationError
from redis.asyncio import Redis
from redis.exceptions import ResponseError

from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.security.limits import (
    MAX_CONTROL_PAYLOAD_CHARACTERS,
    MAX_CONTROL_STREAM_ITEMS,
    MAX_EVENT_STREAM_ITEMS,
    MAX_REPLAY_EVENTS,
    PREVIEW_TICKET_MAX_CHARACTERS,
    WEBSOCKET_TICKET_MAX_CHARACTERS,
)
from lunar_forge_web.security.redaction import redact
from lunar_forge_web.security.tickets import (
    IssuedTicket,
    TicketGrant,
    TicketValidationError,
)
from lunar_forge_web.storage.repositories import (
    RepositoryConflictError,
    RepositoryStateError,
)


_SAFE_KEY_PART = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")
_APPEND_EVENT_SCRIPT = """
local current = tonumber(redis.call('GET', KEYS[2]) or '0')
local incoming = tonumber(ARGV[1])
if incoming ~= current + 1 then
  return redis.error_reply('LF_SEQUENCE_EXPECTED:' .. tostring(current + 1))
end
redis.call('XADD', KEYS[1], ARGV[1] .. '-0', 'event', ARGV[2])
redis.call('XTRIM', KEYS[1], 'MAXLEN', '=', ARGV[3])
redis.call('EXPIRE', KEYS[1], ARGV[4])
redis.call('SET', KEYS[2], ARGV[1], 'EX', ARGV[4])
return incoming
"""
_CONSUME_TICKET_SCRIPT = """
local value = redis.call('GETDEL', KEYS[1])
if value then redis.call('SREM', KEYS[2], ARGV[1]) end
return value
"""
_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then redis.call('EXPIRE', KEYS[1], ARGV[1]) end
local ttl = redis.call('TTL', KEYS[1])
return {current, ttl}
"""
_RELEASE_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('DEL', KEYS[1])
end
return 0
"""
_REFRESH_LOCK_SCRIPT = """
if redis.call('GET', KEYS[1]) == ARGV[1] then
  return redis.call('PEXPIRE', KEYS[1], ARGV[2])
end
return 0
"""


class RedisClient(Protocol):
    async def eval(self, script: str, numkeys: int, *keys_and_args: Any) -> Any: ...
    async def get(self, key: str) -> str | None: ...
    async def set(self, key: str, value: str, **kwargs: Any) -> Any: ...
    async def delete(self, *keys: str) -> int: ...
    async def expire(self, key: str, seconds: int) -> Any: ...
    async def sadd(self, key: str, *values: str) -> int: ...
    async def smembers(self, key: str) -> set[str]: ...
    async def xrange(
        self, name: str, min: str, max: str, count: int
    ) -> list[tuple[str, dict[str, str]]]: ...
    async def xread(
        self, streams: dict[str, str], count: int, block: int
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]: ...
    async def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        maxlen: int,
        approximate: bool,
    ) -> str: ...
    async def aclose(self) -> None: ...


@dataclass(frozen=True, slots=True)
class ControlMessage:
    id: str
    kind: str
    action_id: str
    payload: dict[str, Any]
    created_at: datetime


class InMemoryControlStore:
    """Deterministic process-local substitute for the Redis control stream."""

    def __init__(self) -> None:
        self._messages: dict[str, list[ControlMessage]] = {}
        self._lock = asyncio.Lock()
        self._next_id = 0

    async def publish_control(
        self,
        *,
        session_id: str,
        kind: str,
        action_id: str,
        payload: dict[str, Any],
        now: datetime | None = None,
    ) -> str:
        if kind not in {"approval", "cancel"}:
            raise ValueError("Control kind must be approval or cancel.")
        safe_payload = redact(payload)
        serialized = json.dumps(
            safe_payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        if len(serialized) > MAX_CONTROL_PAYLOAD_CHARACTERS:
            raise ValueError("Control payload is too large.")
        async with self._lock:
            self._next_id += 1
            message_id = f"{self._next_id}-0"
            messages = self._messages.setdefault(session_id, [])
            messages.append(
                ControlMessage(
                    id=message_id,
                    kind=kind,
                    action_id=action_id,
                    payload=dict(safe_payload),
                    created_at=now or datetime.now(timezone.utc),
                )
            )
            del messages[:-MAX_CONTROL_STREAM_ITEMS]
            return message_id

    async def replay_controls(
        self, session_id: str, after_id: str = "0-0", limit: int = 100
    ) -> tuple[ControlMessage, ...]:
        if not 1 <= limit <= MAX_CONTROL_STREAM_ITEMS:
            raise ValueError("Control replay limit is out of bounds.")
        try:
            after = int(after_id.partition("-")[0])
        except ValueError as exc:
            raise ValueError("Control cursor is invalid.") from exc
        async with self._lock:
            return tuple(
                message
                for message in self._messages.get(session_id, ())
                if int(message.id.partition("-")[0]) > after
            )[:limit]


@dataclass(frozen=True, slots=True)
class PreviewTicketGrant:
    user_id: str
    sandbox_id: str
    preview_id: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class RateLimitResult:
    allowed: bool
    count: int
    limit: int
    retry_after_seconds: int


@dataclass(frozen=True, slots=True)
class RedisLease:
    name: str
    token: str


def create_redis_client(
    redis_url: str,
    *,
    max_connections: int,
    socket_timeout_seconds: float,
) -> Redis:
    """Create one pooled async client for local Redis or TLS Upstash Redis."""

    return Redis.from_url(
        redis_url,
        decode_responses=True,
        max_connections=max_connections,
        socket_timeout=socket_timeout_seconds,
        socket_connect_timeout=socket_timeout_seconds,
        health_check_interval=30,
    )


class UpstashRedisStore:
    """Shared coordination adapter using only Upstash-supported Redis commands."""

    def __init__(
        self,
        client: RedisClient,
        *,
        key_prefix: str,
        event_ttl_seconds: int,
        control_ttl_seconds: int,
    ) -> None:
        if not key_prefix or len(key_prefix) > 100 or any(
            character.isspace() for character in key_prefix
        ):
            raise ValueError("Redis key prefix must be non-empty, bounded, and whitespace-free.")
        self._client = client
        self._prefix = key_prefix.rstrip(":")
        self._event_ttl = event_ttl_seconds
        self._control_ttl = control_ttl_seconds

    @staticmethod
    def _part(value: str) -> str:
        if not _SAFE_KEY_PART.fullmatch(value):
            raise ValueError("Redis key identifiers must be bounded safe identifiers.")
        return value

    def _key(self, kind: str, identifier: str) -> str:
        return f"{self._prefix}:{kind}:{self._part(identifier)}"

    def event_stream_key(self, session_id: str) -> str:
        return self._key("events", session_id)

    def event_sequence_key(self, session_id: str) -> str:
        return self._key("event-sequence", session_id)

    def control_stream_key(self, session_id: str) -> str:
        return self._key("controls", session_id)

    async def append(self, event: AgentEventContract) -> None:
        safe_event = event.model_copy(update={"payload": redact(event.payload)})
        serialized = safe_event.model_dump_json()
        try:
            await self._client.eval(
                _APPEND_EVENT_SCRIPT,
                2,
                self.event_stream_key(event.session_id),
                self.event_sequence_key(event.session_id),
                event.sequence,
                serialized,
                MAX_EVENT_STREAM_ITEMS,
                self._event_ttl,
            )
        except ResponseError as exc:
            message = str(exc)
            marker = "LF_SEQUENCE_EXPECTED:"
            if marker in message:
                expected = message.split(marker, 1)[1].split()[0]
                raise RepositoryConflictError(
                    f"Expected event sequence {expected}, received {event.sequence}."
                ) from exc
            raise

    async def replay(
        self, session_id: str, after_sequence: int, limit: int
    ) -> tuple[AgentEventContract, ...]:
        if after_sequence < 0:
            raise ValueError("after_sequence must be non-negative.")
        if not 1 <= limit <= MAX_REPLAY_EVENTS:
            raise ValueError(f"Replay limit must be between 1 and {MAX_REPLAY_EVENTS}.")
        rows = await self._client.xrange(
            self.event_stream_key(session_id),
            min=f"({after_sequence}-0",
            max="+",
            count=limit,
        )
        events: list[AgentEventContract] = []
        for _, fields in rows:
            serialized = fields.get("event")
            if serialized is None:
                continue
            try:
                events.append(AgentEventContract.model_validate_json(serialized))
            except ValidationError as exc:
                raise RepositoryStateError("Stored event is invalid.") from exc
        return tuple(events)

    async def last_sequence(self, session_id: str) -> int:
        value = await self._client.get(self.event_sequence_key(session_id))
        return int(value) if value is not None else 0

    async def wait_for_events(
        self, session_id: str, after_sequence: int, timeout: float
    ) -> bool:
        if timeout <= 0:
            return await self.last_sequence(session_id) > after_sequence
        block_ms = min(max(int(timeout * 1_000), 1), 60_000)
        rows = await self._client.xread(
            {self.event_stream_key(session_id): f"{after_sequence}-0"},
            count=1,
            block=block_ms,
        )
        return bool(rows)

    async def clear_session(self, session_id: str) -> None:
        await self._client.delete(
            self.event_stream_key(session_id),
            self.event_sequence_key(session_id),
            self.control_stream_key(session_id),
        )
        await self._clear_ticket_scope("ws", session_id)

    async def publish_control(
        self,
        *,
        session_id: str,
        kind: str,
        action_id: str,
        payload: dict[str, Any],
        now: datetime | None = None,
    ) -> str:
        if kind not in {"approval", "cancel"}:
            raise ValueError("Control kind must be approval or cancel.")
        self._part(action_id)
        safe_payload = redact(payload)
        serialized = json.dumps(
            safe_payload, ensure_ascii=False, allow_nan=False, separators=(",", ":")
        )
        if len(serialized) > MAX_CONTROL_PAYLOAD_CHARACTERS:
            raise ValueError("Control payload is too large.")
        created_at = (now or datetime.now(timezone.utc)).isoformat()
        key = self.control_stream_key(session_id)
        message_id = await self._client.xadd(
            key,
            {
                "kind": kind,
                "action_id": action_id,
                "payload": serialized,
                "created_at": created_at,
            },
            maxlen=MAX_CONTROL_STREAM_ITEMS,
            approximate=False,
        )
        await self._client.expire(key, self._control_ttl)
        return message_id

    async def replay_controls(
        self, session_id: str, after_id: str = "0-0", limit: int = 100
    ) -> tuple[ControlMessage, ...]:
        if not 1 <= limit <= MAX_CONTROL_STREAM_ITEMS:
            raise ValueError("Control replay limit is out of bounds.")
        rows = await self._client.xrange(
            self.control_stream_key(session_id),
            min=f"({after_id}",
            max="+",
            count=limit,
        )
        return tuple(
            ControlMessage(
                id=message_id,
                kind=fields["kind"],
                action_id=fields["action_id"],
                payload=json.loads(fields["payload"]),
                created_at=datetime.fromisoformat(fields["created_at"]),
            )
            for message_id, fields in rows
        )

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    def _ticket_key(self, kind: str, digest: str) -> str:
        return f"{self._prefix}:ticket:{kind}:{digest}"

    def _ticket_scope_key(self, kind: str, scope_id: str) -> str:
        return f"{self._prefix}:ticket-index:{kind}:{self._part(scope_id)}"

    async def _issue_ticket(
        self,
        *,
        kind: str,
        prefix: str,
        scope_id: str,
        grant: dict[str, str],
        ttl_seconds: int,
    ) -> IssuedTicket:
        now = datetime.now(timezone.utc)
        expires_at = now + timedelta(seconds=ttl_seconds)
        token = f"{prefix}_{secrets.token_urlsafe(32)}"
        digest = self._digest(token)
        value = json.dumps(
            {**grant, "expires_at": expires_at.isoformat()}, separators=(",", ":")
        )
        stored = await self._client.set(
            self._ticket_key(kind, digest), value, ex=ttl_seconds, nx=True
        )
        if not stored:
            raise RepositoryConflictError("Could not allocate a unique ticket.")
        scope_key = self._ticket_scope_key(kind, scope_id)
        await self._client.sadd(scope_key, digest)
        await self._client.expire(scope_key, ttl_seconds)
        return IssuedTicket(token=token, expires_at=expires_at)

    async def _consume_ticket(
        self,
        *,
        kind: str,
        token: str,
        scope_id: str,
        max_characters: int,
    ) -> dict[str, str]:
        if not token or len(token) > max_characters:
            raise TicketValidationError("Ticket is invalid.")
        digest = self._digest(token)
        value = await self._client.eval(
            _CONSUME_TICKET_SCRIPT,
            2,
            self._ticket_key(kind, digest),
            self._ticket_scope_key(kind, scope_id),
            digest,
        )
        if value is None:
            raise TicketValidationError("Ticket is invalid or expired.")
        try:
            record = json.loads(value)
            expires_at = datetime.fromisoformat(record["expires_at"])
        except (KeyError, TypeError, ValueError, json.JSONDecodeError) as exc:
            raise TicketValidationError("Ticket record is invalid.") from exc
        if expires_at <= datetime.now(timezone.utc):
            raise TicketValidationError("Ticket is invalid or expired.")
        return record

    async def issue_websocket_ticket(
        self, user_id: str, session_id: str, ttl_seconds: int
    ) -> IssuedTicket:
        return await self._issue_ticket(
            kind="ws",
            prefix="wst",
            scope_id=session_id,
            grant={"user_id": user_id, "session_id": session_id},
            ttl_seconds=ttl_seconds,
        )

    async def consume_websocket_ticket(
        self, token: str, session_id: str
    ) -> TicketGrant:
        record = await self._consume_ticket(
            kind="ws",
            token=token,
            scope_id=session_id,
            max_characters=WEBSOCKET_TICKET_MAX_CHARACTERS,
        )
        if not secrets.compare_digest(record.get("session_id", ""), session_id):
            raise TicketValidationError("Ticket does not match the session.")
        return TicketGrant(
            user_id=record["user_id"],
            session_id=record["session_id"],
            expires_at=datetime.fromisoformat(record["expires_at"]),
        )

    async def issue_preview_ticket(
        self,
        *,
        user_id: str,
        sandbox_id: str,
        preview_id: str,
        ttl_seconds: int,
    ) -> IssuedTicket:
        return await self._issue_ticket(
            kind="preview",
            prefix="pvt",
            scope_id=sandbox_id,
            grant={
                "user_id": user_id,
                "sandbox_id": sandbox_id,
                "preview_id": preview_id,
            },
            ttl_seconds=ttl_seconds,
        )

    async def consume_preview_ticket(
        self, token: str, sandbox_id: str, preview_id: str
    ) -> PreviewTicketGrant:
        record = await self._consume_ticket(
            kind="preview",
            token=token,
            scope_id=sandbox_id,
            max_characters=PREVIEW_TICKET_MAX_CHARACTERS,
        )
        if not secrets.compare_digest(record.get("sandbox_id", ""), sandbox_id):
            raise TicketValidationError("Ticket does not match the sandbox.")
        if not secrets.compare_digest(record.get("preview_id", ""), preview_id):
            raise TicketValidationError("Ticket does not match the preview.")
        return PreviewTicketGrant(
            user_id=record["user_id"],
            sandbox_id=record["sandbox_id"],
            preview_id=record["preview_id"],
            expires_at=datetime.fromisoformat(record["expires_at"]),
        )

    async def _clear_ticket_scope(self, kind: str, scope_id: str) -> None:
        index_key = self._ticket_scope_key(kind, scope_id)
        digests = await self._client.smembers(index_key)
        keys = [self._ticket_key(kind, digest) for digest in digests]
        if keys:
            await self._client.delete(*keys)
        await self._client.delete(index_key)

    async def clear_sandbox(
        self, sandbox_id: str, session_ids: tuple[str, ...]
    ) -> None:
        for session_id in session_ids[:100]:
            await self.clear_session(session_id)
        await self._clear_ticket_scope("preview", sandbox_id)

    async def rate_limit(
        self, *, scope: str, identifier: str, limit: int, window_seconds: int
    ) -> RateLimitResult:
        if not 1 <= limit <= 100_000:
            raise ValueError("Rate limit must be between 1 and 100,000.")
        if not 1 <= window_seconds <= 86_400:
            raise ValueError("Rate-limit window must be between 1 and 86,400 seconds.")
        key = self._key(f"rate:{self._part(scope)}", identifier)
        count, ttl = await self._client.eval(
            _RATE_LIMIT_SCRIPT, 1, key, window_seconds
        )
        return RateLimitResult(
            allowed=int(count) <= limit,
            count=int(count),
            limit=limit,
            retry_after_seconds=max(int(ttl), 0),
        )

    async def acquire_lock(
        self, name: str, ttl_seconds: float
    ) -> RedisLease | None:
        if not 0.1 <= ttl_seconds <= 300:
            raise ValueError("Lock TTL must be between 0.1 and 300 seconds.")
        token = secrets.token_urlsafe(24)
        stored = await self._client.set(
            self._key("lock", name),
            token,
            nx=True,
            px=max(100, int(ttl_seconds * 1_000)),
        )
        return RedisLease(name=name, token=token) if stored else None

    async def refresh_lock(self, lease: RedisLease, ttl_seconds: float) -> bool:
        if not 0.1 <= ttl_seconds <= 300:
            raise ValueError("Lock TTL must be between 0.1 and 300 seconds.")
        result = await self._client.eval(
            _REFRESH_LOCK_SCRIPT,
            1,
            self._key("lock", lease.name),
            lease.token,
            max(100, int(ttl_seconds * 1_000)),
        )
        return bool(result)

    async def release_lock(self, lease: RedisLease) -> bool:
        result = await self._client.eval(
            _RELEASE_LOCK_SCRIPT,
            1,
            self._key("lock", lease.name),
            lease.token,
        )
        return bool(result)

    async def close(self) -> None:
        await self._client.aclose()


class RedisWebSocketTicketStore:
    def __init__(self, redis_store: UpstashRedisStore, ttl_seconds: int) -> None:
        self._redis = redis_store
        self._ttl_seconds = ttl_seconds

    async def issue(self, user_id: str, session_id: str) -> IssuedTicket:
        return await self._redis.issue_websocket_ticket(
            user_id, session_id, self._ttl_seconds
        )

    async def consume(self, token: str, session_id: str) -> TicketGrant:
        return await self._redis.consume_websocket_ticket(token, session_id)
