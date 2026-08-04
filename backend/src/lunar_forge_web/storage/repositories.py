"""Async repository protocols and deterministic process-local stores."""

from __future__ import annotations

import asyncio
from datetime import date, datetime, timedelta, timezone
from typing import Protocol
from uuid import uuid4

from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import (
    ApprovalResponse,
    SandboxResponse,
    SessionResponse,
    SessionSettings,
    TurnResponse,
    UserRecord,
)
from lunar_forge_web.domain.enums import ApprovalStatus, TurnStatus
from lunar_forge_web.security.limits import (
    OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD,
    OWNER_FUNDED_TURNS_PER_USER_PER_DAY,
    OWNER_FUNDED_USER_DAILY_COST_MICROUSD,
    RETAINED_METADATA_DAYS,
)
from lunar_forge_web.storage.records import (
    AdminSettingsRecord,
    CleanupClaim,
    QuotaReservation,
    QuotaSnapshot,
    UsageRecord,
    TurnRecord,
)


class RepositoryConflictError(ValueError):
    pass


class QuotaLimitError(RepositoryConflictError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code


class RepositoryStateError(RepositoryConflictError):
    pass


class UserRepository(Protocol):
    async def get(self, user_id: str) -> UserRecord | None: ...
    async def put(self, user: UserRecord) -> None: ...


class SandboxRepository(Protocol):
    async def get(self, sandbox_id: str) -> SandboxResponse | None: ...
    async def put(self, sandbox: SandboxResponse) -> None: ...
    async def list_for_owner(self, owner_id: str) -> tuple[SandboxResponse, ...]: ...
    async def extend_activity(
        self, sandbox_id: str, activity_at: datetime, expires_at: datetime
    ) -> SandboxResponse | None: ...
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


class TurnRepository(Protocol):
    async def create(
        self,
        turn: TurnResponse,
        *,
        sandbox_id: str,
        prompt: str,
        settings: SessionSettings,
    ) -> TurnRecord: ...
    async def get(self, turn_id: str) -> TurnRecord | None: ...
    async def active_for_session(self, session_id: str) -> TurnRecord | None: ...
    async def mark_running(self, turn_id: str, started_at: datetime) -> TurnRecord: ...
    async def finish(
        self,
        turn_id: str,
        *,
        status: TurnStatus,
        finished_at: datetime,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_microusd: int,
        error_code: str | None,
    ) -> TurnRecord: ...


class ApprovalRepository(Protocol):
    async def get(self, approval_id: str) -> ApprovalResponse | None: ...
    async def put(self, approval: ApprovalResponse) -> None: ...
    async def resolve(
        self, approval_id: str, owner_id: str, approved: bool
    ) -> ApprovalResponse: ...


class AdminSettingsRepository(Protocol):
    async def get(self) -> AdminSettingsRecord: ...
    async def update(
        self,
        *,
        sandbox_kill_switch_enabled: bool | None = None,
        owner_funded_enabled: bool | None = None,
    ) -> AdminSettingsRecord: ...


class QuotaRepository(Protocol):
    async def reserve_owner_funded_turn(
        self,
        *,
        user_id: str,
        turn_id: str,
        reserved_cost_microusd: int | None,
        now: datetime,
    ) -> QuotaReservation: ...

    async def settle_owner_funded_turn(
        self,
        *,
        turn_id: str,
        actual_cost_microusd: int,
        input_tokens: int,
        output_tokens: int,
        sandbox_id: str | None,
        provider: str,
        model: str,
        now: datetime,
    ) -> UsageRecord: ...

    async def release_owner_funded_reservation(
        self, turn_id: str, now: datetime
    ) -> None: ...

    async def snapshot(self, user_id: str, day: date) -> QuotaSnapshot: ...


class CleanupRepository(Protocol):
    async def claim_expired(
        self, now: datetime, limit: int
    ) -> tuple[CleanupClaim, ...]: ...
    async def complete(self, claim: CleanupClaim, now: datetime) -> None: ...
    async def fail(
        self, claim: CleanupClaim, result_code: str, now: datetime
    ) -> None: ...
    async def purge_retained(self, now: datetime, limit: int) -> int: ...


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
            if sandbox.status in {"creating", "ready", "busy", "deleting"}:
                duplicate = next(
                    (
                        item
                        for item in self._items.values()
                        if item.owner_id == sandbox.owner_id
                        and item.id != sandbox.id
                        and item.status in {"creating", "ready", "busy", "deleting"}
                    ),
                    None,
                )
                if duplicate is not None:
                    raise RepositoryConflictError(
                        "Only one active sandbox is allowed per user."
                    )
            self._items[sandbox.id] = sandbox

    async def list_for_owner(self, owner_id: str) -> tuple[SandboxResponse, ...]:
        return tuple(
            sorted(
                (item for item in self._items.values() if item.owner_id == owner_id),
                key=lambda item: (item.created_at, item.id),
            )
        )

    async def extend_activity(
        self,
        sandbox_id: str,
        activity_at: datetime,
        expires_at: datetime,
    ) -> SandboxResponse | None:
        async with self._lock:
            sandbox = self._items.get(sandbox_id)
            if sandbox is None or sandbox.status not in {"creating", "ready", "busy"}:
                return None
            if activity_at < sandbox.last_activity_at:
                return sandbox
            extended = sandbox.model_copy(
                update={"last_activity_at": activity_at, "expires_at": expires_at}
            )
            self._items[sandbox_id] = extended
            return extended

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


class InMemoryTurnRepository:
    def __init__(self) -> None:
        self._items: dict[str, TurnRecord] = {}
        self._prompts: dict[str, str] = {}
        self._lock = asyncio.Lock()

    async def create(
        self,
        turn: TurnResponse,
        *,
        sandbox_id: str,
        prompt: str,
        settings: SessionSettings,
    ) -> TurnRecord:
        record = TurnRecord(
            turn=turn,
            sandbox_id=sandbox_id,
            funding_mode=str(settings.funding_mode),
            provider=settings.provider,
            model=settings.model,
            reasoning_effort=str(settings.reasoning_effort),
        )
        async with self._lock:
            if turn.id in self._items:
                raise RepositoryConflictError("Turn already exists.")
            if any(
                item.turn.session_id == turn.session_id
                and item.turn.status
                in {TurnStatus.QUEUED, TurnStatus.RUNNING, TurnStatus.WAITING_FOR_APPROVAL}
                for item in self._items.values()
            ):
                raise RepositoryConflictError("A turn is already active for this session.")
            self._items[turn.id] = record
            self._prompts[turn.id] = prompt
        return record

    async def get(self, turn_id: str) -> TurnRecord | None:
        async with self._lock:
            return self._items.get(turn_id)

    async def active_for_session(self, session_id: str) -> TurnRecord | None:
        async with self._lock:
            return next(
                (
                    item
                    for item in self._items.values()
                    if item.turn.session_id == session_id
                    and item.turn.status
                    in {
                        TurnStatus.QUEUED,
                        TurnStatus.RUNNING,
                        TurnStatus.WAITING_FOR_APPROVAL,
                    }
                ),
                None,
            )

    async def mark_running(self, turn_id: str, started_at: datetime) -> TurnRecord:
        async with self._lock:
            current = self._items.get(turn_id)
            if current is None:
                raise RepositoryStateError("Turn was not found.")
            if current.turn.status not in {TurnStatus.QUEUED, TurnStatus.RUNNING}:
                raise RepositoryStateError("Turn is not runnable.")
            updated = TurnRecord(
                turn=current.turn.model_copy(
                    update={"status": TurnStatus.RUNNING, "started_at": started_at}
                ),
                sandbox_id=current.sandbox_id,
                funding_mode=current.funding_mode,
                provider=current.provider,
                model=current.model,
                reasoning_effort=current.reasoning_effort,
            )
            self._items[turn_id] = updated
            return updated

    async def finish(
        self,
        turn_id: str,
        *,
        status: TurnStatus,
        finished_at: datetime,
        input_tokens: int,
        output_tokens: int,
        estimated_cost_microusd: int,
        error_code: str | None,
    ) -> TurnRecord:
        if status not in {TurnStatus.COMPLETED, TurnStatus.CANCELLED, TurnStatus.FAILED}:
            raise ValueError("A terminal turn status is required.")
        async with self._lock:
            current = self._items.get(turn_id)
            if current is None:
                raise RepositoryStateError("Turn was not found.")
            updated = TurnRecord(
                turn=current.turn.model_copy(
                    update={
                        "status": status,
                        "finished_at": finished_at,
                        "input_tokens": input_tokens,
                        "output_tokens": output_tokens,
                        "estimated_cost_microusd": estimated_cost_microusd,
                        "error_code": error_code,
                    }
                ),
                sandbox_id=current.sandbox_id,
                funding_mode=current.funding_mode,
                provider=current.provider,
                model=current.model,
                reasoning_effort=current.reasoning_effort,
            )
            self._items[turn_id] = updated
            self._prompts.pop(turn_id, None)
            return updated


class InMemoryApprovalRepository:
    def __init__(self) -> None:
        self._items: dict[str, ApprovalResponse] = {}
        self._lock = asyncio.Lock()

    async def get(self, approval_id: str) -> ApprovalResponse | None:
        async with self._lock:
            return self._items.get(approval_id)

    async def put(self, approval: ApprovalResponse) -> None:
        async with self._lock:
            self._items.setdefault(approval.id, approval)

    async def resolve(
        self, approval_id: str, owner_id: str, approved: bool
    ) -> ApprovalResponse:
        async with self._lock:
            current = self._items.get(approval_id)
            if current is None or current.owner_id != owner_id:
                raise RepositoryStateError("Approval was not found.")
            if current.status != ApprovalStatus.PENDING.value:
                raise RepositoryConflictError("Approval was already resolved.")
            updated = current.model_copy(
                update={
                    "status": (
                        ApprovalStatus.APPROVED if approved else ApprovalStatus.DENIED
                    )
                }
            )
            self._items[approval_id] = updated
            return updated


class InMemoryAdminSettingsRepository:
    def __init__(self, settings: AdminSettingsRecord | None = None) -> None:
        self._settings = settings or AdminSettingsRecord()
        self._lock = asyncio.Lock()

    async def get(self) -> AdminSettingsRecord:
        return self._settings

    async def update(
        self,
        *,
        sandbox_kill_switch_enabled: bool | None = None,
        owner_funded_enabled: bool | None = None,
    ) -> AdminSettingsRecord:
        async with self._lock:
            self._settings = AdminSettingsRecord(
                sandbox_kill_switch_enabled=(
                    self._settings.sandbox_kill_switch_enabled
                    if sandbox_kill_switch_enabled is None
                    else sandbox_kill_switch_enabled
                ),
                owner_funded_enabled=(
                    self._settings.owner_funded_enabled
                    if owner_funded_enabled is None
                    else owner_funded_enabled
                ),
            )
            return self._settings


class InMemoryQuotaRepository:
    """Concurrency-safe fake implementing the same hard quota contract."""

    def __init__(self, admin_settings: AdminSettingsRepository) -> None:
        self._admin_settings = admin_settings
        self._counters: dict[tuple[str, date], dict[str, int]] = {}
        self._reservations: dict[str, tuple[QuotaReservation, str, int | None]] = {}
        self._usage: dict[str, UsageRecord] = {}
        self._lock = asyncio.Lock()

    def _counter(self, scope: str, day: date) -> dict[str, int]:
        return self._counters.setdefault(
            (scope, day), {"turns": 0, "settled": 0, "reserved": 0}
        )

    async def reserve_owner_funded_turn(
        self,
        *,
        user_id: str,
        turn_id: str,
        reserved_cost_microusd: int | None,
        now: datetime,
    ) -> QuotaReservation:
        if reserved_cost_microusd is not None and reserved_cost_microusd <= 0:
            raise ValueError("A positive cost reservation is required.")
        settings = await self._admin_settings.get()
        if settings.sandbox_kill_switch_enabled:
            raise QuotaLimitError("sandbox_kill_switch", "Sandbox use is disabled.")
        if not settings.owner_funded_enabled:
            raise QuotaLimitError("owner_funded_disabled", "Owner-funded mode is disabled.")
        current_day = now.astimezone(timezone.utc).date()
        async with self._lock:
            existing = self._reservations.get(turn_id)
            if existing is not None:
                reservation, status, _ = existing
                if status == "reserved" and reservation.user_id == user_id:
                    return reservation
                raise RepositoryStateError("Quota reservation is already finalized.")
            user = self._counter(f"user:{user_id}", current_day)
            global_counter = self._counter("global", current_day)
            if user["turns"] >= OWNER_FUNDED_TURNS_PER_USER_PER_DAY:
                raise QuotaLimitError("daily_turn_limit", "Daily turn limit reached.")
            user_available = (
                OWNER_FUNDED_USER_DAILY_COST_MICROUSD
                - user["settled"]
                - user["reserved"]
            )
            global_available = (
                OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD
                - global_counter["settled"]
                - global_counter["reserved"]
            )
            if user_available <= 0:
                raise QuotaLimitError(
                    "daily_user_cost_limit", "Daily user cost cap reached."
                )
            if global_available <= 0:
                raise QuotaLimitError(
                    "daily_global_cost_limit", "Global daily cost cap reached."
                )
            selected_reservation = (
                min(user_available, global_available)
                if reserved_cost_microusd is None
                else reserved_cost_microusd
            )
            if selected_reservation > user_available:
                raise QuotaLimitError("daily_user_cost_limit", "Daily user cost cap reached.")
            if selected_reservation > global_available:
                raise QuotaLimitError("daily_global_cost_limit", "Global daily cost cap reached.")
            user["turns"] += 1
            user["reserved"] += selected_reservation
            global_counter["turns"] += 1
            global_counter["reserved"] += selected_reservation
            reservation = QuotaReservation(
                turn_id=turn_id,
                user_id=user_id,
                day=current_day,
                reserved_cost_microusd=selected_reservation,
            )
            self._reservations[turn_id] = (reservation, "reserved", None)
            return reservation

    async def settle_owner_funded_turn(
        self,
        *,
        turn_id: str,
        actual_cost_microusd: int,
        input_tokens: int,
        output_tokens: int,
        sandbox_id: str | None,
        provider: str,
        model: str,
        now: datetime,
    ) -> UsageRecord:
        if min(actual_cost_microusd, input_tokens, output_tokens) < 0:
            raise ValueError("Usage values must be non-negative.")
        async with self._lock:
            stored = self._reservations.get(turn_id)
            if stored is None:
                raise RepositoryStateError("Quota reservation was not found.")
            reservation, status, settled = stored
            if status == "settled":
                return next(item for item in self._usage.values() if item.turn_id == turn_id)
            if status != "reserved":
                raise RepositoryStateError("Quota reservation is not active.")
            if actual_cost_microusd > reservation.reserved_cost_microusd:
                raise QuotaLimitError(
                    "reservation_exceeded", "Actual cost exceeds the hard reservation."
                )
            user = self._counter(f"user:{reservation.user_id}", reservation.day)
            global_counter = self._counter("global", reservation.day)
            for counter in (user, global_counter):
                counter["reserved"] -= reservation.reserved_cost_microusd
                counter["settled"] += actual_cost_microusd
            usage = UsageRecord(
                id=f"usage_{uuid4().hex}",
                user_id=reservation.user_id,
                sandbox_id=sandbox_id,
                turn_id=turn_id,
                day=reservation.day,
                funding_mode="owner_funded",
                provider=provider,
                model=model,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                estimated_cost_microusd=actual_cost_microusd,
                created_at=now,
                retention_expires_at=now + timedelta(days=RETAINED_METADATA_DAYS),
            )
            self._usage[usage.id] = usage
            self._reservations[turn_id] = (
                reservation,
                "settled",
                actual_cost_microusd,
            )
            return usage

    async def release_owner_funded_reservation(
        self, turn_id: str, now: datetime
    ) -> None:
        del now
        async with self._lock:
            stored = self._reservations.get(turn_id)
            if stored is None:
                return
            reservation, status, _ = stored
            if status != "reserved":
                return
            user = self._counter(f"user:{reservation.user_id}", reservation.day)
            global_counter = self._counter("global", reservation.day)
            for counter in (user, global_counter):
                counter["reserved"] -= reservation.reserved_cost_microusd
            self._reservations[turn_id] = (reservation, "released", None)

    async def snapshot(self, user_id: str, day: date) -> QuotaSnapshot:
        async with self._lock:
            user = self._counter(f"user:{user_id}", day)
            global_counter = self._counter("global", day)
            return QuotaSnapshot(
                user_id=user_id,
                day=day,
                turns=user["turns"],
                settled_cost_microusd=user["settled"],
                reserved_cost_microusd=user["reserved"],
                global_settled_cost_microusd=global_counter["settled"],
                global_reserved_cost_microusd=global_counter["reserved"],
            )
