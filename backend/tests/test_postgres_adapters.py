from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from lunar_forge_web.domain.enums import SandboxStatus, SessionStatus
from lunar_forge_web.domain.models import SandboxResponse, SessionResponse, UserRecord
from lunar_forge_web.security.limits import (
    OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD,
    OWNER_FUNDED_TURNS_PER_USER_PER_DAY,
    OWNER_FUNDED_USER_DAILY_COST_MICROUSD,
    RETAINED_METADATA_DAYS,
)
from lunar_forge_web.storage.orm import (
    ApprovalRow,
    ArtifactRow,
    Base,
    EventOffsetRow,
    PreviewRow,
    ProjectSourceRow,
    SandboxRow,
    SessionRow,
    TurnRow,
)
from lunar_forge_web.storage.postgres import (
    PostgresAdminSettingsRepository,
    PostgresCleanupRepository,
    PostgresQuotaRepository,
    PostgresSandboxRepository,
    PostgresSessionRepository,
    PostgresUserRepository,
)
from lunar_forge_web.storage.repositories import (
    QuotaLimitError,
    RepositoryConflictError,
)


@pytest.fixture
async def database():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as connection:
        await connection.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    try:
        yield factory
    finally:
        await engine.dispose()


async def _put_users(factory, *user_ids: str) -> None:
    repository = PostgresUserRepository(factory)
    for user_id in user_ids:
        await repository.put(UserRecord(id=user_id, email=f"{user_id}@example.com"))


async def test_postgres_identity_sandbox_and_session_contract(database):
    await _put_users(database, "user-a")
    users = PostgresUserRepository(database)
    sandboxes = PostgresSandboxRepository(database)
    sessions = PostgresSessionRepository(database)
    now = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)

    user = await users.get("user-a")
    assert user is not None and user.email == "user-a@example.com"
    first = SandboxResponse(
        id="sandbox-a",
        owner_id="user-a",
        template_id="python-cli",
        runtime_provider="e2b",
        runtime_reference="runtime-a",
        status=SandboxStatus.READY,
        created_at=now,
        last_activity_at=now,
        expires_at=now + timedelta(minutes=30),
    )
    await sandboxes.put(first)
    with pytest.raises(RepositoryConflictError, match="one active sandbox"):
        await sandboxes.put(
            first.model_copy(
                update={"id": "sandbox-b", "runtime_reference": "runtime-b"}
            )
        )

    activity_at = now + timedelta(minutes=5)
    extended = await sandboxes.extend_activity(
        first.id, activity_at, activity_at + timedelta(minutes=30)
    )
    assert extended is not None
    assert extended.last_activity_at == activity_at
    assert extended.expires_at == activity_at + timedelta(minutes=30)

    session = SessionResponse(
        id="session-a",
        sandbox_id=first.id,
        owner_id="user-a",
        status=SessionStatus.ACTIVE,
        created_at=now,
    )
    await sessions.put(session)
    assert await sessions.get(session.id) == session

    await sandboxes.delete(first.id)
    assert await sandboxes.get(first.id) is None
    await sandboxes.put(
        first.model_copy(
            update={"id": "sandbox-b", "runtime_reference": "runtime-b"}
        )
    )


async def test_postgres_owner_funded_quota_is_atomic_and_exact(database):
    await _put_users(database, "user-a", "user-b", "user-c", "user-d", "user-e")
    admin = PostgresAdminSettingsRepository(database)
    quotas = PostgresQuotaRepository(database, admin)
    now = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)

    defaults = await admin.get()
    assert defaults.sandbox_kill_switch_enabled is False
    assert defaults.owner_funded_enabled is True
    await admin.update(owner_funded_enabled=False)
    with pytest.raises(QuotaLimitError) as disabled:
        await quotas.reserve_owner_funded_turn(
            user_id="user-a",
            turn_id="disabled-turn",
            reserved_cost_microusd=1,
            now=now,
        )
    assert disabled.value.code == "owner_funded_disabled"
    await admin.update(owner_funded_enabled=True)

    for index in range(OWNER_FUNDED_TURNS_PER_USER_PER_DAY):
        turn_id = f"count-turn-{index}"
        await quotas.reserve_owner_funded_turn(
            user_id="user-a",
            turn_id=turn_id,
            reserved_cost_microusd=1,
            now=now,
        )
        await quotas.release_owner_funded_reservation(turn_id, now)
    with pytest.raises(QuotaLimitError) as turns:
        await quotas.reserve_owner_funded_turn(
            user_id="user-a",
            turn_id="count-turn-over",
            reserved_cost_microusd=1,
            now=now,
        )
    assert turns.value.code == "daily_turn_limit"

    cost_day = now + timedelta(days=1)
    await quotas.reserve_owner_funded_turn(
        user_id="user-a",
        turn_id="user-cap",
        reserved_cost_microusd=OWNER_FUNDED_USER_DAILY_COST_MICROUSD,
        now=cost_day,
    )
    with pytest.raises(QuotaLimitError) as user_cost:
        await quotas.reserve_owner_funded_turn(
            user_id="user-a",
            turn_id="user-cap-over",
            reserved_cost_microusd=1,
            now=cost_day,
        )
    assert user_cost.value.code == "daily_user_cost_limit"

    global_day = now + timedelta(days=2)
    for user_id in ("user-a", "user-b", "user-c"):
        await quotas.reserve_owner_funded_turn(
            user_id=user_id,
            turn_id=f"global-{user_id}",
            reserved_cost_microusd=OWNER_FUNDED_USER_DAILY_COST_MICROUSD,
            now=global_day,
        )
    await quotas.reserve_owner_funded_turn(
        user_id="user-d",
        turn_id="global-user-d",
        reserved_cost_microusd=(
            OWNER_FUNDED_GLOBAL_DAILY_COST_MICROUSD
            - 3 * OWNER_FUNDED_USER_DAILY_COST_MICROUSD
        ),
        now=global_day,
    )
    with pytest.raises(QuotaLimitError) as global_cost:
        await quotas.reserve_owner_funded_turn(
            user_id="user-e",
            turn_id="global-over",
            reserved_cost_microusd=1,
            now=global_day,
        )
    assert global_cost.value.code == "daily_global_cost_limit"

    settle_day = now + timedelta(days=3)
    async with database() as session, session.begin():
        session.add(
            SandboxRow(
                id="quota-sandbox",
                owner_id="user-e",
                template_id="python-cli",
                runtime_provider="e2b",
                runtime_reference="runtime-quota",
                status="ready",
                last_activity_at=settle_day,
                expires_at=settle_day + timedelta(minutes=30),
                created_at=settle_day,
            )
        )
        session.add(
            SessionRow(
                id="quota-session",
                sandbox_id="quota-sandbox",
                owner_id="user-e",
                status="active",
                last_sequence=0,
                compacted_summary_count=0,
                settings={},
                created_at=settle_day,
            )
        )
        session.add(
            TurnRow(
                id="settled-turn",
                session_id="quota-session",
                owner_id="user-e",
                status="completed",
                prompt=None,
                funding_mode="owner_funded",
                provider="openai",
                model="approved-model",
                reasoning_effort="high",
                created_at=settle_day,
            )
        )
    await quotas.reserve_owner_funded_turn(
        user_id="user-e",
        turn_id="settled-turn",
        reserved_cost_microusd=1_000_000,
        now=settle_day,
    )
    usage = await quotas.settle_owner_funded_turn(
        turn_id="settled-turn",
        actual_cost_microusd=900_000,
        input_tokens=100,
        output_tokens=50,
        sandbox_id="quota-sandbox",
        provider="openai",
        model="approved-model",
        now=settle_day,
    )
    assert usage.estimated_cost_microusd == 900_000
    assert usage.retention_expires_at == settle_day + timedelta(
        days=RETAINED_METADATA_DAYS
    )
    settled_snapshot = await quotas.snapshot("user-e", settle_day.date())
    assert settled_snapshot.settled_cost_microusd == 900_000
    assert settled_snapshot.reserved_cost_microusd == 0


async def test_postgres_cleanup_scrubs_content_then_purges_tombstones(database):
    await _put_users(database, "user-a")
    now = datetime(2026, 8, 3, 12, tzinfo=timezone.utc)
    expired_at = now - timedelta(minutes=1)
    async with database() as session, session.begin():
        session.add(
            ProjectSourceRow(
                id="source-a",
                owner_id="user-a",
                kind="public_git",
                source_metadata={"url": "https://github.com/example/project"},
                created_at=now - timedelta(hours=1),
            )
        )
        session.add(
            SandboxRow(
                id="sandbox-a",
                owner_id="user-a",
                project_source_id="source-a",
                template_id="vite-react",
                runtime_provider="e2b",
                runtime_reference="runtime-secret-reference",
                status=SandboxStatus.READY.value,
                last_activity_at=now - timedelta(minutes=31),
                expires_at=expired_at,
                created_at=now - timedelta(hours=1),
            )
        )
        session.add(
            SessionRow(
                id="session-a",
                sandbox_id="sandbox-a",
                owner_id="user-a",
                status=SessionStatus.ACTIVE.value,
                last_sequence=5,
                compacted_summary_count=0,
                settings={"model": "server-default", "transcript": "content"},
                created_at=now - timedelta(hours=1),
            )
        )
        session.add(
            TurnRow(
                id="turn-a",
                session_id="session-a",
                owner_id="user-a",
                status="completed",
                prompt="private prompt",
                funding_mode="owner_funded",
                provider="openai",
                model="server-default",
                reasoning_effort="high",
                created_at=now - timedelta(minutes=20),
            )
        )
        session.add(
            ApprovalRow(
                id="approval-a",
                sandbox_id="sandbox-a",
                session_id="session-a",
                turn_id="turn-a",
                owner_id="user-a",
                kind="command.run",
                status="pending",
                detail={"command": "secret command payload"},
                expires_at=now,
                created_at=now - timedelta(minutes=15),
            )
        )
        session.add(
            ArtifactRow(
                id="artifact-a",
                sandbox_id="sandbox-a",
                session_id="session-a",
                owner_id="user-a",
                name="report.json",
                storage_reference="opaque-storage-reference",
                media_type="application/json",
                size_bytes=10,
                expires_at=expired_at,
                created_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            PreviewRow(
                id="preview-a",
                sandbox_id="sandbox-a",
                owner_id="user-a",
                port=4173,
                status="ready",
                expires_at=expired_at,
                created_at=now - timedelta(minutes=10),
            )
        )
        session.add(
            EventOffsetRow(
                session_id="session-a",
                stream_key="lfw:test:events:session-a",
                last_sequence=5,
            )
        )

    cleanup = PostgresCleanupRepository(database)
    claims = await cleanup.claim_expired(now, 10)
    assert len(claims) == 1
    await cleanup.complete(claims[0], now)

    async with database() as session:
        sandbox = await session.get(SandboxRow, "sandbox-a")
        stored_session = await session.get(SessionRow, "session-a")
        turn = await session.get(TurnRow, "turn-a")
        approval = await session.get(ApprovalRow, "approval-a")
        assert sandbox is not None
        assert sandbox.status == "deleted"
        assert sandbox.runtime_reference is None
        retention_expires_at = sandbox.retention_expires_at
        if retention_expires_at.tzinfo is None:
            retention_expires_at = retention_expires_at.replace(tzinfo=timezone.utc)
        assert retention_expires_at == now + timedelta(days=RETAINED_METADATA_DAYS)
        assert stored_session is not None and stored_session.settings == {}
        assert turn is not None and turn.prompt is None
        assert approval is not None and approval.detail == {}
        assert approval.status == "expired"
        assert await session.get(ArtifactRow, "artifact-a") is None
        assert await session.get(PreviewRow, "preview-a") is None
        assert await session.get(EventOffsetRow, "session-a") is None
        assert await session.get(ProjectSourceRow, "source-a") is None

    purged = await cleanup.purge_retained(now + timedelta(days=31), 100)
    assert purged >= 1
    async with database() as session:
        assert await session.get(SandboxRow, "sandbox-a") is None
        assert await session.get(SessionRow, "session-a") is None
        assert await session.get(TurnRow, "turn-a") is None
        assert await session.get(ApprovalRow, "approval-a") is None
