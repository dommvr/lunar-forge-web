from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import pytest
from redis.exceptions import ResponseError

from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.security.redaction import REDACTED
from lunar_forge_web.security.tickets import TicketValidationError
from lunar_forge_web.storage.redis import UpstashRedisStore
from lunar_forge_web.storage.repositories import RepositoryConflictError


class FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.sets: dict[str, set[str]] = {}
        self.streams: dict[str, list[tuple[str, dict[str, str]]]] = {}
        self.closed = False

    async def eval(self, script: str, numkeys: int, *items: Any) -> Any:
        keys = items[:numkeys]
        arguments = items[numkeys:]
        if "LF_SEQUENCE_EXPECTED" in script:
            stream_key, sequence_key = keys
            sequence = int(arguments[0])
            expected = int(self.values.get(sequence_key, "0")) + 1
            if sequence != expected:
                raise ResponseError(f"LF_SEQUENCE_EXPECTED:{expected}")
            rows = self.streams.setdefault(stream_key, [])
            rows.append((f"{sequence}-0", {"event": str(arguments[1])}))
            del rows[: max(0, len(rows) - int(arguments[2]))]
            self.values[sequence_key] = str(sequence)
            return sequence
        if "GETDEL" in script:
            ticket_key, index_key = keys
            value = self.values.pop(ticket_key, None)
            if value is not None:
                self.sets.setdefault(index_key, set()).discard(str(arguments[0]))
            return value
        if "INCR" in script:
            key = keys[0]
            count = int(self.values.get(key, "0")) + 1
            self.values[key] = str(count)
            return [count, int(arguments[0])]
        if "PEXPIRE" in script:
            key = keys[0]
            return int(self.values.get(key, "") == str(arguments[0]))
        if "redis.call('DEL'" in script:
            key = keys[0]
            if self.values.get(key) == str(arguments[0]):
                self.values.pop(key, None)
                return 1
            return 0
        raise AssertionError("Unexpected Redis script")

    async def get(self, key: str) -> str | None:
        return self.values.get(key)

    async def set(self, key: str, value: str, **kwargs: Any) -> bool:
        if kwargs.get("nx") and key in self.values:
            return False
        self.values[key] = value
        return True

    async def delete(self, *keys: str) -> int:
        removed = 0
        for key in keys:
            removed += int(key in self.values or key in self.sets or key in self.streams)
            self.values.pop(key, None)
            self.sets.pop(key, None)
            self.streams.pop(key, None)
        return removed

    async def expire(self, key: str, seconds: int) -> bool:
        del seconds
        return key in self.values or key in self.sets or key in self.streams

    async def sadd(self, key: str, *values: str) -> int:
        selected = self.sets.setdefault(key, set())
        before = len(selected)
        selected.update(values)
        return len(selected) - before

    async def smembers(self, key: str) -> set[str]:
        return set(self.sets.get(key, set()))

    @staticmethod
    def _stream_number(value: str) -> int:
        return int(value.removeprefix("(").split("-", 1)[0])

    async def xrange(
        self, name: str, min: str, max: str, count: int
    ) -> list[tuple[str, dict[str, str]]]:
        del max
        after = self._stream_number(min)
        exclusive = min.startswith("(")
        return [
            row
            for row in self.streams.get(name, [])
            if self._stream_number(row[0]) > after
            or (not exclusive and self._stream_number(row[0]) == after)
        ][:count]

    async def xread(
        self, streams: dict[str, str], count: int, block: int
    ) -> list[tuple[str, list[tuple[str, dict[str, str]]]]]:
        del block
        key, after_id = next(iter(streams.items()))
        rows = await self.xrange(key, f"({after_id}", "+", count)
        return [(key, rows)] if rows else []

    async def xadd(
        self,
        name: str,
        fields: dict[str, str],
        *,
        maxlen: int,
        approximate: bool,
    ) -> str:
        assert approximate is False
        rows = self.streams.setdefault(name, [])
        message_id = f"{len(rows) + 1}-0"
        rows.append((message_id, fields))
        del rows[: max(0, len(rows) - maxlen)]
        return message_id

    async def aclose(self) -> None:
        self.closed = True


def event(sequence: int, payload: dict[str, Any] | None = None) -> AgentEventContract:
    return AgentEventContract(
        event_id=f"event-{sequence}",
        session_id="session-a",
        turn_id="turn-a",
        sequence=sequence,
        timestamp="2026-08-03T12:00:00+00:00",
        type="status.updated",
        payload=payload or {"step": sequence},
    )


@pytest.fixture
def redis_store():
    client = FakeRedisClient()
    return client, UpstashRedisStore(
        client,
        key_prefix="lfw:test",
        event_ttl_seconds=3_600,
        control_ttl_seconds=3_600,
    )


async def test_redis_event_stream_is_monotonic_redacted_replayable_and_trimmed(
    redis_store,
):
    client, store = redis_store
    await store.append(event(1, {"api_key": "sk-super-secret-value"}))
    replay = await store.replay("session-a", 0, 10)
    assert replay[0].payload["api_key"] == REDACTED
    assert await store.last_sequence("session-a") == 1
    assert await store.wait_for_events("session-a", 0, 0.01) is True
    with pytest.raises(RepositoryConflictError, match="Expected event sequence 2"):
        await store.append(event(3))

    for sequence in range(2, 2_002):
        await store.append(event(sequence))
    rows = client.streams[store.event_stream_key("session-a")]
    assert len(rows) == 2_000
    assert rows[0][0] == "2-0"
    assert rows[-1][0] == "2001-0"

    await store.clear_session("session-a")
    assert await store.last_sequence("session-a") == 0
    assert await store.replay("session-a", 0, 10) == ()


async def test_redis_controls_tickets_rate_limits_and_leases(redis_store):
    client, store = redis_store
    now = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
    message_id = await store.publish_control(
        session_id="session-a",
        kind="approval",
        action_id="approval-a",
        payload={"approved": True, "provider_api_key": "sk-secret-value"},
        now=now,
    )
    controls = await store.replay_controls("session-a")
    assert controls[0].id == message_id
    assert controls[0].payload["provider_api_key"] == REDACTED

    issued = await store.issue_websocket_ticket("user-a", "session-a", 60)
    serialized_storage = json.dumps(
        {"values": client.values, "sets": {k: sorted(v) for k, v in client.sets.items()}}
    )
    assert issued.token not in serialized_storage
    grant = await store.consume_websocket_ticket(issued.token, "session-a")
    assert grant.user_id == "user-a"
    with pytest.raises(TicketValidationError):
        await store.consume_websocket_ticket(issued.token, "session-a")

    preview = await store.issue_preview_ticket(
        user_id="user-a",
        sandbox_id="sandbox-a",
        preview_id="preview-a",
        ttl_seconds=60,
    )
    preview_grant = await store.consume_preview_ticket(
        preview.token, "sandbox-a", "preview-a"
    )
    assert preview_grant.preview_id == "preview-a"

    first = await store.rate_limit(
        scope="api", identifier="user-a", limit=1, window_seconds=60
    )
    second = await store.rate_limit(
        scope="api", identifier="user-a", limit=1, window_seconds=60
    )
    assert first.allowed is True
    assert second.allowed is False and second.count == 2

    lease = await store.acquire_lock("cleanup", 10)
    assert lease is not None
    assert await store.acquire_lock("cleanup", 10) is None
    assert await store.refresh_lock(lease, 10) is True
    assert await store.release_lock(lease) is True
    assert await store.release_lock(lease) is False

    await store.close()
    assert client.closed is True

