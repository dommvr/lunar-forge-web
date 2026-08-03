"""One-time, hashed, process-local WebSocket ticket implementation."""

from __future__ import annotations

import asyncio
import hashlib
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import Protocol


class TicketValidationError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class IssuedTicket:
    token: str
    expires_at: datetime


@dataclass(frozen=True, slots=True)
class TicketGrant:
    user_id: str
    session_id: str
    expires_at: datetime


class WebSocketTicketStore(Protocol):
    async def issue(self, user_id: str, session_id: str) -> IssuedTicket: ...
    async def consume(self, token: str, session_id: str) -> TicketGrant: ...


class InMemoryWebSocketTicketStore:
    """Store only SHA-256 ticket digests and consume them atomically once."""

    def __init__(self, ttl_seconds: int) -> None:
        self._ttl = timedelta(seconds=ttl_seconds)
        self._records: dict[str, TicketGrant] = {}
        self._lock = asyncio.Lock()

    @staticmethod
    def _digest(token: str) -> str:
        return hashlib.sha256(token.encode("utf-8")).hexdigest()

    async def issue(self, user_id: str, session_id: str) -> IssuedTicket:
        now = datetime.now(timezone.utc)
        token = f"wst_{secrets.token_urlsafe(32)}"
        expires_at = now + self._ttl
        async with self._lock:
            self._purge_expired(now)
            self._records[self._digest(token)] = TicketGrant(
                user_id=user_id,
                session_id=session_id,
                expires_at=expires_at,
            )
        return IssuedTicket(token=token, expires_at=expires_at)

    async def consume(self, token: str, session_id: str) -> TicketGrant:
        if not token or len(token) > 512:
            raise TicketValidationError("Ticket is invalid.")
        now = datetime.now(timezone.utc)
        async with self._lock:
            record = self._records.pop(self._digest(token), None)
            self._purge_expired(now)
        if record is None or record.expires_at <= now:
            raise TicketValidationError("Ticket is invalid or expired.")
        if not secrets.compare_digest(record.session_id, session_id):
            raise TicketValidationError("Ticket does not match the session.")
        return record

    def _purge_expired(self, now: datetime) -> None:
        expired = [key for key, value in self._records.items() if value.expires_at <= now]
        for key in expired:
            self._records.pop(key, None)

    def stored_digests(self) -> tuple[str, ...]:
        return tuple(sorted(self._records))
