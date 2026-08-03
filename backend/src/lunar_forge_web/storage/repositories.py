"""Async repository protocols and deterministic process-local stores."""

from __future__ import annotations

import asyncio
from typing import Protocol

from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import (
    SandboxResponse,
    SessionResponse,
    UserRecord,
)


class RepositoryConflictError(ValueError):
    pass


class UserRepository(Protocol):
    async def get(self, user_id: str) -> UserRecord | None: ...
    async def put(self, user: UserRecord) -> None: ...


class SandboxRepository(Protocol):
    async def get(self, sandbox_id: str) -> SandboxResponse | None: ...
    async def put(self, sandbox: SandboxResponse) -> None: ...
    async def list_for_owner(self, owner_id: str) -> tuple[SandboxResponse, ...]: ...
    async def delete(self, sandbox_id: str) -> None: ...


class SessionRepository(Protocol):
    async def get(self, session_id: str) -> SessionResponse | None: ...
    async def put(self, session: SessionResponse) -> None: ...
    async def list_for_sandbox(self, sandbox_id: str) -> tuple[SessionResponse, ...]: ...
    async def delete_for_sandbox(self, sandbox_id: str) -> None: ...


class EventRepository(Protocol):
    async def append(self, event: AgentEventContract) -> None: ...
    async def replay(
        self,
        session_id: str,
        after_sequence: int,
        limit: int,
    ) -> tuple[AgentEventContract, ...]: ...
    async def last_sequence(self, session_id: str) -> int: ...
    async def wait_for_events(
        self, session_id: str, after_sequence: int, timeout: float
    ) -> bool: ...
    async def clear_session(self, session_id: str) -> None: ...


class InMemoryUserRepository:
    def __init__(self, users: tuple[UserRecord, ...] = ()) -> None:
        self._items = {user.id: user for user in users}
        self._lock = asyncio.Lock()

    async def get(self, user_id: str) -> UserRecord | None:
        return self._items.get(user_id)

    async def put(self, user: UserRecord) -> None:
        async with self._lock:
            self._items[user.id] = user


class InMemorySandboxRepository:
    def __init__(self, sandboxes: tuple[SandboxResponse, ...] = ()) -> None:
        self._items = {sandbox.id: sandbox for sandbox in sandboxes}
        self._lock = asyncio.Lock()

    async def get(self, sandbox_id: str) -> SandboxResponse | None:
        return self._items.get(sandbox_id)

    async def put(self, sandbox: SandboxResponse) -> None:
        async with self._lock:
            self._items[sandbox.id] = sandbox

    async def list_for_owner(self, owner_id: str) -> tuple[SandboxResponse, ...]:
        return tuple(
            sorted(
                (item for item in self._items.values() if item.owner_id == owner_id),
                key=lambda item: (item.created_at, item.id),
            )
        )

    async def delete(self, sandbox_id: str) -> None:
        async with self._lock:
            self._items.pop(sandbox_id, None)


class InMemorySessionRepository:
    def __init__(self, sessions: tuple[SessionResponse, ...] = ()) -> None:
        self._items = {session.id: session for session in sessions}
        self._lock = asyncio.Lock()

    async def get(self, session_id: str) -> SessionResponse | None:
        return self._items.get(session_id)

    async def put(self, session: SessionResponse) -> None:
        async with self._lock:
            self._items[session.id] = session

    async def list_for_sandbox(self, sandbox_id: str) -> tuple[SessionResponse, ...]:
        return tuple(
            sorted(
                (item for item in self._items.values() if item.sandbox_id == sandbox_id),
                key=lambda item: (item.created_at, item.id),
            )
        )

    async def delete_for_sandbox(self, sandbox_id: str) -> None:
        async with self._lock:
            for session_id, session in tuple(self._items.items()):
                if session.sandbox_id == sandbox_id:
                    self._items.pop(session_id, None)


class InMemoryEventRepository:
    def __init__(self) -> None:
        self._events: dict[str, list[AgentEventContract]] = {}
        self._lock = asyncio.Lock()
        self._changed = asyncio.Condition(self._lock)

    async def append(self, event: AgentEventContract) -> None:
        async with self._changed:
            events = self._events.setdefault(event.session_id, [])
            expected = events[-1].sequence + 1 if events else 1
            if event.sequence != expected:
                raise RepositoryConflictError(
                    f"Expected event sequence {expected}, received {event.sequence}."
                )
            events.append(event)
            self._changed.notify_all()

    async def replay(
        self,
        session_id: str,
        after_sequence: int,
        limit: int,
    ) -> tuple[AgentEventContract, ...]:
        async with self._lock:
            selected = [
                event
                for event in self._events.get(session_id, [])
                if event.sequence > after_sequence
            ]
            return tuple(selected[:limit])

    async def last_sequence(self, session_id: str) -> int:
        async with self._lock:
            events = self._events.get(session_id, [])
            return events[-1].sequence if events else 0

    async def wait_for_events(
        self,
        session_id: str,
        after_sequence: int,
        timeout: float,
    ) -> bool:
        def available() -> bool:
            events = self._events.get(session_id, [])
            return bool(events and events[-1].sequence > after_sequence)

        async with self._changed:
            if available():
                return True
            try:
                await asyncio.wait_for(self._changed.wait_for(available), timeout)
            except TimeoutError:
                return False
            return True

    async def clear_session(self, session_id: str) -> None:
        async with self._changed:
            self._events.pop(session_id, None)
            self._changed.notify_all()
