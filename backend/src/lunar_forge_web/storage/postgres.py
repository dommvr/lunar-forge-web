"""Async SQLAlchemy adapters for Neon PostgreSQL (and SQLite contract tests)."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from uuid import uuid4

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.postgresql import insert as postgresql_insert
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from lunar_forge_web.domain.enums import ApprovalStatus, SandboxStatus, SessionStatus
from lunar_forge_web.domain.models import (
    PreviewResponse,
    SandboxResponse,
    SessionResponse,
    UserRecord,
)
from lunar_forge_web.security.limits import (
    OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD,
    OWNER_FUNDED_TURNS_PER_USER_PER_DAY,
    OWNER_FUNDED_USER_DAILY_COST_MICROUSD,
    RETAINED_METADATA_DAYS,
)
from lunar_forge_web.storage.orm import (
    AdminSettingRow,
    ApprovalRow,
    ArtifactRow,
    AuditEventRow,
    CleanupJobRow,
    DailyQuotaCounterRow,
    EventOffsetRow,
    PreviewRow,
    ProjectSourceRow,
    QuotaReservationRow,
    SandboxRow,
    SessionRow,
    TurnRow,
    UsageLedgerRow,
    UserRow,
)
from lunar_forge_web.storage.records import (
    AdminSettingsRecord,
    CleanupClaim,
    QuotaReservation,
    QuotaSnapshot,
    UsageRecord,
)
from lunar_forge_web.storage.repositories import (
    QuotaLimitError,
    RepositoryConflictError,
    RepositoryStateError,
)


SessionFactory = async_sessionmaker[AsyncSession]
_ACTIVE_SANDBOX_STATUSES = {
    SandboxStatus.CREATING.value,
    SandboxStatus.READY.value,
    SandboxStatus.BUSY.value,
    SandboxStatus.DELETING.value,
}


def _as_utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc)


def _sandbox_contract(row: SandboxRow) -> SandboxResponse:
    return SandboxResponse(
        id=row.id,
        owner_id=row.owner_id,
        template_id=row.template_id,
        runtime_provider=row.runtime_provider,
        runtime_reference=row.runtime_reference,
        status=row.status,
        created_at=_as_utc(row.created_at),
        last_activity_at=_as_utc(row.last_activity_at),
        expires_at=_as_utc(row.expires_at),
    )


def _session_contract(row: SessionRow) -> SessionResponse:
    return SessionResponse(
        id=row.id,
        sandbox_id=row.sandbox_id,
        owner_id=row.owner_id,
        status=row.status,
        created_at=_as_utc(row.created_at),
        last_sequence=row.last_sequence,
        compacted_summary_count=row.compacted_summary_count,
    )


class PostgresUserRepository:
    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def get(self, user_id: str) -> UserRecord | None:
        async with self._factory() as session:
            row = await session.get(UserRow, user_id)
            if row is None:
                return None
            return UserRecord(
                id=row.id,
                email=row.email,
                role=row.role,
                suspended=row.suspended,
                created_at=_as_utc(row.created_at),
            )

    async def put(self, user: UserRecord) -> None:
        async with self._factory() as session, session.begin():
            row = await session.get(UserRow, user.id)
            if row is None:
                session.add(
                    UserRow(
                        id=user.id,
                        email=str(user.email),
                        role=user.role,
                        suspended=user.suspended,
                        created_at=user.created_at,
                    )
                )
            else:
                row.email = str(user.email)
                row.role = user.role
                row.suspended = user.suspended


class PostgresSandboxRepository:
    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def get(self, sandbox_id: str) -> SandboxResponse | None:
        async with self._factory() as session:
            row = await session.scalar(
                select(SandboxRow).where(
                    SandboxRow.id == sandbox_id,
                    SandboxRow.deleted_at.is_(None),
                )
            )
            return _sandbox_contract(row) if row is not None else None

    async def put(self, sandbox: SandboxResponse) -> None:
        try:
            async with self._factory() as session, session.begin():
                row = await session.get(SandboxRow, sandbox.id)
                if row is None:
                    session.add(
                        SandboxRow(
                            id=sandbox.id,
                            owner_id=sandbox.owner_id,
                            template_id=sandbox.template_id,
                            runtime_provider=sandbox.runtime_provider,
                            runtime_reference=sandbox.runtime_reference,
                            status=sandbox.status,
                            created_at=sandbox.created_at,
                            last_activity_at=sandbox.last_activity_at,
                            expires_at=sandbox.expires_at,
                        )
                    )
                else:
                    row.template_id = sandbox.template_id
                    row.runtime_provider = sandbox.runtime_provider
                    row.runtime_reference = sandbox.runtime_reference
                    row.status = sandbox.status
                    row.last_activity_at = sandbox.last_activity_at
                    row.expires_at = sandbox.expires_at
                    row.deleted_at = None
                    row.retention_expires_at = None
                    row.deletion_reason = None
        except IntegrityError as exc:
            message = str(exc.orig)
            if (
                "uq_sandboxes_one_active_per_owner" not in message
                and "UNIQUE constraint failed: sandboxes.owner_id" not in message
            ):
                raise
            raise RepositoryConflictError(
                "Only one active sandbox is allowed per user."
            ) from exc

    async def list_for_owner(self, owner_id: str) -> tuple[SandboxResponse, ...]:
        async with self._factory() as session:
            rows = (
                await session.scalars(
                    select(SandboxRow)
                    .where(
                        SandboxRow.owner_id == owner_id,
                        SandboxRow.deleted_at.is_(None),
                    )
                    .order_by(SandboxRow.created_at, SandboxRow.id)
                    .limit(100)
                )
            ).all()
            return tuple(_sandbox_contract(row) for row in rows)

    async def extend_activity(
        self,
        sandbox_id: str,
        activity_at: datetime,
        expires_at: datetime,
    ) -> SandboxResponse | None:
        async with self._factory() as session, session.begin():
            row = await session.scalar(
                select(SandboxRow)
                .where(
                    SandboxRow.id == sandbox_id,
                    SandboxRow.deleted_at.is_(None),
                    SandboxRow.status.in_(
                        [
                            SandboxStatus.CREATING.value,
                            SandboxStatus.READY.value,
                            SandboxStatus.BUSY.value,
                        ]
                    ),
                )
                .with_for_update()
            )
            if row is None:
                return None
            if _as_utc(row.last_activity_at) <= _as_utc(activity_at):
                row.last_activity_at = activity_at
                row.expires_at = expires_at
            await session.flush()
            return _sandbox_contract(row)

    async def delete(self, sandbox_id: str) -> None:
        now = datetime.now(timezone.utc)
        async with self._factory() as session, session.begin():
            row = await session.get(SandboxRow, sandbox_id)
            if row is None:
                return
            row.status = SandboxStatus.DELETED.value
            row.deleted_at = now
            row.runtime_reference = None
            row.retention_expires_at = now + timedelta(days=RETAINED_METADATA_DAYS)
            row.deletion_reason = "explicit_delete"


class PostgresSessionRepository:
    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def get(self, session_id: str) -> SessionResponse | None:
        async with self._factory() as session:
            row = await session.get(SessionRow, session_id)
            if row is None or row.status == SessionStatus.EXPIRED.value:
                return None
            return _session_contract(row)

    async def put(self, item: SessionResponse) -> None:
        async with self._factory() as session, session.begin():
            row = await session.get(SessionRow, item.id)
            if row is None:
                session.add(
                    SessionRow(
                        id=item.id,
                        sandbox_id=item.sandbox_id,
                        owner_id=item.owner_id,
                        status=item.status,
                        last_sequence=item.last_sequence,
                        compacted_summary_count=item.compacted_summary_count,
                        settings={},
                        created_at=item.created_at,
                    )
                )
            else:
                row.status = item.status
                row.last_sequence = item.last_sequence
                row.compacted_summary_count = item.compacted_summary_count

    async def list_for_sandbox(self, sandbox_id: str) -> tuple[SessionResponse, ...]:
        async with self._factory() as session:
            rows = (
                await session.scalars(
                    select(SessionRow)
                    .where(
                        SessionRow.sandbox_id == sandbox_id,
                        SessionRow.status != SessionStatus.EXPIRED.value,
                    )
                    .order_by(SessionRow.created_at, SessionRow.id)
                    .limit(100)
                )
            ).all()
            return tuple(_session_contract(row) for row in rows)

    async def delete_for_sandbox(self, sandbox_id: str) -> None:
        now = datetime.now(timezone.utc)
        async with self._factory() as session, session.begin():
            await session.execute(
                update(SessionRow)
                .where(SessionRow.sandbox_id == sandbox_id)
                .values(
                    status=SessionStatus.EXPIRED.value,
                    settings={},
                    closed_at=now,
                    retention_expires_at=now + timedelta(days=RETAINED_METADATA_DAYS),
                )
            )


class PostgresPreviewRepository:
    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def get(self, preview_id: str) -> PreviewResponse | None:
        async with self._factory() as session:
            row = await session.get(PreviewRow, preview_id)
            if row is None:
                return None
            return PreviewResponse(
                id=row.id,
                sandbox_id=row.sandbox_id,
                owner_id=row.owner_id,
                port=row.port,
                status=row.status,
                created_at=_as_utc(row.created_at),
                expires_at=_as_utc(row.expires_at),
            )


class PostgresAdminSettingsRepository:
    _KILL_SWITCH = "sandbox_kill_switch_enabled"
    _OWNER_FUNDED = "owner_funded_enabled"

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    @staticmethod
    def _enabled(rows: dict[str, AdminSettingRow], key: str, default: bool) -> bool:
        row = rows.get(key)
        return default if row is None else row.value.get("enabled") is True

    async def get(self) -> AdminSettingsRecord:
        async with self._factory() as session:
            selected = (
                await session.scalars(
                    select(AdminSettingRow).where(
                        AdminSettingRow.key.in_([self._KILL_SWITCH, self._OWNER_FUNDED])
                    )
                )
            ).all()
            rows = {row.key: row for row in selected}
            return AdminSettingsRecord(
                sandbox_kill_switch_enabled=self._enabled(
                    rows, self._KILL_SWITCH, False
                ),
                owner_funded_enabled=self._enabled(rows, self._OWNER_FUNDED, True),
            )

    async def update(
        self,
        *,
        sandbox_kill_switch_enabled: bool | None = None,
        owner_funded_enabled: bool | None = None,
    ) -> AdminSettingsRecord:
        values = {
            self._KILL_SWITCH: sandbox_kill_switch_enabled,
            self._OWNER_FUNDED: owner_funded_enabled,
        }
        async with self._factory() as session, session.begin():
            for key, enabled in values.items():
                if enabled is None:
                    continue
                row = await session.get(AdminSettingRow, key)
                if row is None:
                    session.add(AdminSettingRow(key=key, value={"enabled": enabled}))
                else:
                    row.value = {"enabled": enabled}
                    row.updated_at = datetime.now(timezone.utc)
        return await self.get()


class PostgresQuotaRepository:
    def __init__(
        self,
        factory: SessionFactory,
        admin_settings: PostgresAdminSettingsRepository,
    ) -> None:
        self._factory = factory
        self._admin_settings = admin_settings

    @staticmethod
    async def _ensure_counter(
        session: AsyncSession, *, scope_key: str, user_id: str | None, day: str
    ) -> None:
        values = {
            "id": f"quota_{uuid4().hex}",
            "scope_key": scope_key,
            "user_id": user_id,
            "day": day,
            "turns": 0,
            "estimated_cost_microusd": 0,
            "reserved_cost_microusd": 0,
        }
        dialect = session.get_bind().dialect.name
        statement = (
            postgresql_insert(DailyQuotaCounterRow)
            if dialect == "postgresql"
            else sqlite_insert(DailyQuotaCounterRow)
        )
        await session.execute(
            statement.values(**values).on_conflict_do_nothing(
                index_elements=["scope_key", "day"]
            )
        )

    @classmethod
    async def _locked_counters(
        cls, session: AsyncSession, user_id: str, day: str
    ) -> tuple[DailyQuotaCounterRow, DailyQuotaCounterRow]:
        await cls._ensure_counter(
            session, scope_key="global", user_id=None, day=day
        )
        await cls._ensure_counter(
            session, scope_key=f"user:{user_id}", user_id=user_id, day=day
        )
        rows = (
            await session.scalars(
                select(DailyQuotaCounterRow)
                .where(
                    DailyQuotaCounterRow.scope_key.in_(
                        ["global", f"user:{user_id}"]
                    ),
                    DailyQuotaCounterRow.day == day,
                )
                .order_by(DailyQuotaCounterRow.scope_key)
                .with_for_update()
            )
        ).all()
        mapped = {row.scope_key: row for row in rows}
        return mapped[f"user:{user_id}"], mapped["global"]

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
        current_day = _as_utc(now).date()
        day_text = current_day.isoformat()
        async with self._factory() as session, session.begin():
            selected_settings = (
                await session.scalars(
                    select(AdminSettingRow)
                    .where(
                        AdminSettingRow.key.in_(
                            [
                                PostgresAdminSettingsRepository._KILL_SWITCH,
                                PostgresAdminSettingsRepository._OWNER_FUNDED,
                            ]
                        )
                    )
                    .with_for_update()
                )
            ).all()
            setting_rows = {row.key: row for row in selected_settings}
            if PostgresAdminSettingsRepository._enabled(
                setting_rows,
                PostgresAdminSettingsRepository._KILL_SWITCH,
                False,
            ):
                raise QuotaLimitError(
                    "sandbox_kill_switch", "Sandbox use is disabled."
                )
            if not PostgresAdminSettingsRepository._enabled(
                setting_rows,
                PostgresAdminSettingsRepository._OWNER_FUNDED,
                True,
            ):
                raise QuotaLimitError(
                    "owner_funded_disabled", "Owner-funded mode is disabled."
                )
            existing = await session.get(QuotaReservationRow, turn_id)
            if existing is not None:
                if existing.status == "reserved" and existing.user_id == user_id:
                    return QuotaReservation(
                        turn_id=existing.turn_id,
                        user_id=existing.user_id,
                        day=date.fromisoformat(existing.day),
                        reserved_cost_microusd=existing.reserved_cost_microusd,
                    )
                raise RepositoryStateError("Quota reservation is already finalized.")
            user, global_counter = await self._locked_counters(
                session, user_id, day_text
            )
            if user.turns >= OWNER_FUNDED_TURNS_PER_USER_PER_DAY:
                raise QuotaLimitError("daily_turn_limit", "Daily turn limit reached.")
            user_available = (
                OWNER_FUNDED_USER_DAILY_COST_MICROUSD
                - user.estimated_cost_microusd
                - user.reserved_cost_microusd
            )
            global_available = (
                OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD
                - global_counter.estimated_cost_microusd
                - global_counter.reserved_cost_microusd
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
            for counter in (user, global_counter):
                counter.turns += 1
                counter.reserved_cost_microusd += selected_reservation
                counter.updated_at = now
            session.add(
                QuotaReservationRow(
                    turn_id=turn_id,
                    user_id=user_id,
                    day=day_text,
                    reserved_cost_microusd=selected_reservation,
                    status="reserved",
                    created_at=now,
                )
            )
        return QuotaReservation(
            turn_id=turn_id,
            user_id=user_id,
            day=current_day,
            reserved_cost_microusd=selected_reservation,
        )

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
        async with self._factory() as session, session.begin():
            reservation = await session.scalar(
                select(QuotaReservationRow)
                .where(QuotaReservationRow.turn_id == turn_id)
                .with_for_update()
            )
            if reservation is None:
                raise RepositoryStateError("Quota reservation was not found.")
            if reservation.status == "settled":
                row = await session.scalar(
                    select(UsageLedgerRow).where(UsageLedgerRow.turn_id == turn_id)
                )
                if row is None:
                    raise RepositoryStateError("Settled usage record was not found.")
                return self._usage_record(row)
            if reservation.status != "reserved":
                raise RepositoryStateError("Quota reservation is not active.")
            if actual_cost_microusd > reservation.reserved_cost_microusd:
                raise QuotaLimitError(
                    "reservation_exceeded", "Actual cost exceeds the hard reservation."
                )
            user, global_counter = await self._locked_counters(
                session, reservation.user_id, reservation.day
            )
            for counter in (user, global_counter):
                counter.reserved_cost_microusd -= reservation.reserved_cost_microusd
                counter.estimated_cost_microusd += actual_cost_microusd
                counter.updated_at = now
            retention = now + timedelta(days=RETAINED_METADATA_DAYS)
            usage_row = UsageLedgerRow(
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
                retention_expires_at=retention,
            )
            session.add(usage_row)
            reservation.status = "settled"
            reservation.settled_cost_microusd = actual_cost_microusd
            reservation.completed_at = now
            turn = await session.get(TurnRow, turn_id)
            if turn is not None:
                turn.input_tokens = input_tokens
                turn.output_tokens = output_tokens
                turn.estimated_cost_microusd = actual_cost_microusd
            await session.flush()
            return self._usage_record(usage_row)

    async def release_owner_funded_reservation(
        self, turn_id: str, now: datetime
    ) -> None:
        async with self._factory() as session, session.begin():
            reservation = await session.scalar(
                select(QuotaReservationRow)
                .where(QuotaReservationRow.turn_id == turn_id)
                .with_for_update()
            )
            if reservation is None or reservation.status != "reserved":
                return
            user, global_counter = await self._locked_counters(
                session, reservation.user_id, reservation.day
            )
            for counter in (user, global_counter):
                counter.reserved_cost_microusd -= reservation.reserved_cost_microusd
                counter.updated_at = now
            reservation.status = "released"
            reservation.completed_at = now

    async def snapshot(self, user_id: str, day: date) -> QuotaSnapshot:
        async with self._factory() as session:
            rows = (
                await session.scalars(
                    select(DailyQuotaCounterRow).where(
                        DailyQuotaCounterRow.scope_key.in_(
                            ["global", f"user:{user_id}"]
                        ),
                        DailyQuotaCounterRow.day == day.isoformat(),
                    )
                )
            ).all()
            mapped = {row.scope_key: row for row in rows}
            user = mapped.get(f"user:{user_id}")
            global_counter = mapped.get("global")
            return QuotaSnapshot(
                user_id=user_id,
                day=day,
                turns=user.turns if user else 0,
                settled_cost_microusd=(
                    user.estimated_cost_microusd if user else 0
                ),
                reserved_cost_microusd=user.reserved_cost_microusd if user else 0,
                global_settled_cost_microusd=(
                    global_counter.estimated_cost_microusd if global_counter else 0
                ),
                global_reserved_cost_microusd=(
                    global_counter.reserved_cost_microusd if global_counter else 0
                ),
            )

    @staticmethod
    def _usage_record(row: UsageLedgerRow) -> UsageRecord:
        return UsageRecord(
            id=row.id,
            user_id=row.user_id,
            sandbox_id=row.sandbox_id,
            turn_id=row.turn_id,
            day=date.fromisoformat(row.day),
            funding_mode=row.funding_mode,
            provider=row.provider,
            model=row.model,
            input_tokens=row.input_tokens,
            output_tokens=row.output_tokens,
            estimated_cost_microusd=row.estimated_cost_microusd,
            created_at=_as_utc(row.created_at),
            retention_expires_at=_as_utc(row.retention_expires_at),
        )


class PostgresCleanupRepository:
    """Claims expiry work and scrubs content while retaining bounded metadata."""

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory

    async def claim_expired(
        self, now: datetime, limit: int
    ) -> tuple[CleanupClaim, ...]:
        if not 1 <= limit <= 100:
            raise ValueError("Cleanup claim limit must be between 1 and 100.")
        async with self._factory() as session, session.begin():
            statement = (
                select(SandboxRow)
                .where(
                    SandboxRow.deleted_at.is_(None),
                    SandboxRow.expires_at <= now,
                    SandboxRow.status.in_(
                        [
                            SandboxStatus.CREATING.value,
                            SandboxStatus.READY.value,
                            SandboxStatus.BUSY.value,
                            SandboxStatus.EXPIRED.value,
                            SandboxStatus.FAILED.value,
                        ]
                    ),
                )
                .order_by(SandboxRow.expires_at, SandboxRow.id)
                .limit(limit)
                .with_for_update(skip_locked=True)
            )
            rows = (await session.scalars(statement)).all()
            claims: list[CleanupClaim] = []
            for row in rows:
                row.status = SandboxStatus.DELETING.value
                session_rows = (
                    await session.scalars(
                        select(SessionRow).where(SessionRow.sandbox_id == row.id)
                    )
                ).all()
                job_id = f"cleanup_{uuid4().hex}"
                session.add(
                    CleanupJobRow(
                        id=job_id,
                        sandbox_id=row.id,
                        status="running",
                        attempts=1,
                        created_at=now,
                    )
                )
                claims.append(
                    CleanupClaim(
                        job_id=job_id,
                        sandbox=_sandbox_contract(row),
                        session_ids=tuple(item.id for item in session_rows),
                    )
                )
            return tuple(claims)

    async def complete(self, claim: CleanupClaim, now: datetime) -> None:
        retention = now + timedelta(days=RETAINED_METADATA_DAYS)
        async with self._factory() as session, session.begin():
            sandbox = await session.get(SandboxRow, claim.sandbox.id)
            job = await session.get(CleanupJobRow, claim.job_id)
            if sandbox is None or job is None:
                raise RepositoryStateError("Cleanup claim no longer exists.")
            session_ids = list(claim.session_ids)
            turn_ids: list[str] = []
            if session_ids:
                turn_ids = list(
                    await session.scalars(
                        select(TurnRow.id).where(TurnRow.session_id.in_(session_ids))
                    )
                )
                await session.execute(
                    delete(ArtifactRow).where(ArtifactRow.session_id.in_(session_ids))
                )
                await session.execute(
                    delete(EventOffsetRow).where(EventOffsetRow.session_id.in_(session_ids))
                )
                await session.execute(
                    update(SessionRow)
                    .where(SessionRow.id.in_(session_ids))
                    .values(
                        status=SessionStatus.EXPIRED.value,
                        settings={},
                        closed_at=now,
                        retention_expires_at=retention,
                    )
                )
            await session.execute(
                delete(PreviewRow).where(PreviewRow.sandbox_id == sandbox.id)
            )
            await session.execute(
                update(ApprovalRow)
                .where(ApprovalRow.sandbox_id == sandbox.id)
                .values(
                    status=func.coalesce(
                        func.nullif(ApprovalRow.status, ApprovalStatus.PENDING.value),
                        ApprovalStatus.EXPIRED.value,
                    ),
                    detail={},
                    retention_expires_at=retention,
                )
            )
            if turn_ids:
                await session.execute(
                    update(TurnRow)
                    .where(TurnRow.id.in_(turn_ids))
                    .values(prompt=None, retention_expires_at=retention)
                )
            if sandbox.project_source_id is not None:
                project_source_id = sandbox.project_source_id
                sandbox.project_source_id = None
                await session.flush()
                await session.execute(
                    delete(ProjectSourceRow).where(
                        ProjectSourceRow.id == project_source_id
                    )
                )
            sandbox.status = SandboxStatus.DELETED.value
            sandbox.runtime_reference = None
            sandbox.deleted_at = now
            sandbox.retention_expires_at = retention
            sandbox.deletion_reason = "inactivity_expired"
            job.status = "completed"
            job.result_code = "content_deleted"
            job.completed_at = now
            job.retention_expires_at = retention
            session.add(
                AuditEventRow(
                    id=f"audit_{uuid4().hex}",
                    actor_id=None,
                    event_type="sandbox.cleanup_completed",
                    resource_id=sandbox.id,
                    detail={"cleanup_job_id": job.id, "result": "content_deleted"},
                    created_at=now,
                    retention_expires_at=retention,
                )
            )

    async def fail(
        self, claim: CleanupClaim, result_code: str, now: datetime
    ) -> None:
        if not result_code or len(result_code) > 200:
            raise ValueError("Cleanup result code must contain at most 200 characters.")
        async with self._factory() as session, session.begin():
            job = await session.get(CleanupJobRow, claim.job_id)
            sandbox = await session.get(SandboxRow, claim.sandbox.id)
            if job is not None:
                job.status = "failed"
                job.result_code = result_code
                job.completed_at = now
                job.retention_expires_at = now + timedelta(
                    days=RETAINED_METADATA_DAYS
                )
            if sandbox is not None:
                sandbox.status = SandboxStatus.FAILED.value

    async def purge_retained(self, now: datetime, limit: int) -> int:
        if not 1 <= limit <= 1_000:
            raise ValueError("Retention purge limit must be between 1 and 1,000.")
        purged = 0
        async with self._factory() as session, session.begin():
            sandbox_ids = list(
                await session.scalars(
                    select(SandboxRow.id)
                    .where(SandboxRow.retention_expires_at <= now)
                    .order_by(SandboxRow.retention_expires_at, SandboxRow.id)
                    .limit(limit)
                )
            )
            for sandbox_id in sandbox_ids:
                session_ids = list(
                    await session.scalars(
                        select(SessionRow.id).where(
                            SessionRow.sandbox_id == sandbox_id
                        )
                    )
                )
                turn_ids = (
                    list(
                        await session.scalars(
                            select(TurnRow.id).where(
                                TurnRow.session_id.in_(session_ids)
                            )
                        )
                    )
                    if session_ids
                    else []
                )
                if turn_ids:
                    await session.execute(
                        delete(QuotaReservationRow).where(
                            QuotaReservationRow.turn_id.in_(turn_ids)
                        )
                    )
                    await session.execute(
                        delete(UsageLedgerRow).where(
                            UsageLedgerRow.turn_id.in_(turn_ids)
                        )
                    )
                    await session.execute(
                        delete(ApprovalRow).where(ApprovalRow.turn_id.in_(turn_ids))
                    )
                    await session.execute(
                        delete(TurnRow).where(TurnRow.id.in_(turn_ids))
                    )
                if session_ids:
                    await session.execute(
                        delete(SessionRow).where(SessionRow.id.in_(session_ids))
                    )
                await session.execute(
                    delete(SandboxRow).where(SandboxRow.id == sandbox_id)
                )
                purged += 1

            for model in (UsageLedgerRow, AuditEventRow, CleanupJobRow):
                id_column = model.id
                ids = list(
                    await session.scalars(
                        select(id_column)
                        .where(model.retention_expires_at <= now)
                        .limit(max(0, limit - purged))
                    )
                )
                if ids:
                    await session.execute(delete(model).where(id_column.in_(ids)))
                    purged += len(ids)
            cutoff = (_as_utc(now).date() - timedelta(days=RETAINED_METADATA_DAYS))
            await session.execute(
                delete(DailyQuotaCounterRow).where(
                    DailyQuotaCounterRow.day < cutoff.isoformat()
                )
            )
        return purged
