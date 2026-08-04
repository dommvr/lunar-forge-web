"""Explicit dependency container for API/worker factories and tests."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

from sqlalchemy.ext.asyncio import AsyncEngine

from lunar_forge_web.auth.supabase import (
    DeterministicFakeTokenVerifier,
    JWKSProvider,
    SupabaseJWTVerifier,
    TokenVerifier,
)
from lunar_forge_web.config import (
    DeploymentEnvironment,
    InfrastructureBackend,
    RuntimeBackend,
    ServiceRole,
    Settings,
    TurnExecutionBackend,
)
from lunar_forge_web.core.adapter import AgentAdapter, CoreAgentAdapter, FakeCoreAgentAdapter
from lunar_forge_web.core.approvals import ApprovalControlStore, RedisApprovalBroker
from lunar_forge_web.core.runtime import HostedWorkspaceRuntime
from lunar_forge_web.domain.enums import Availability, UserRole
from lunar_forge_web.domain.models import CapabilityItem, TemplateResponse, UserRecord
from lunar_forge_web.runtime.base import RuntimeProvider
from lunar_forge_web.runtime.e2b_provider import E2BRuntimeProvider
from lunar_forge_web.runtime.fake import FakeRuntimeProvider
from lunar_forge_web.services.sandbox_service import runtime_sandbox
from lunar_forge_web.providers.credentials import create_turn_model_client
from lunar_forge_web.security.tickets import (
    InMemoryWebSocketTicketStore,
    WebSocketTicketStore,
)
from lunar_forge_web.storage.database import create_database_engine, create_session_factory
from lunar_forge_web.storage.postgres import (
    PostgresAdminSettingsRepository,
    PostgresApprovalRepository,
    PostgresCleanupRepository,
    PostgresQuotaRepository,
    PostgresSandboxRepository,
    PostgresSessionRepository,
    PostgresTurnRepository,
    PostgresUserRepository,
)
from lunar_forge_web.storage.redis import (
    InMemoryControlStore,
    RedisWebSocketTicketStore,
    UpstashRedisStore,
    create_redis_client,
)
from lunar_forge_web.storage.repositories import (
    AdminSettingsRepository,
    ApprovalRepository,
    CleanupRepository,
    EventRepository,
    InMemoryAdminSettingsRepository,
    InMemoryApprovalRepository,
    InMemoryEventRepository,
    InMemoryQuotaRepository,
    InMemorySandboxRepository,
    InMemorySessionRepository,
    InMemoryTurnRepository,
    InMemoryUserRepository,
    QuotaRepository,
    SandboxRepository,
    SessionRepository,
    TurnRepository,
    UserRepository,
)
from lunar_forge_web.storage.fake_state import InMemoryFakeFlowStore
from lunar_forge_web.worker.client import CloudRunWorkerClient, WorkerClient


@dataclass(slots=True)
class ApplicationContainer:
    settings: Settings
    users: UserRepository
    sandboxes: SandboxRepository
    sessions: SessionRepository
    events: EventRepository
    controls: ApprovalControlStore
    turns: TurnRepository
    approvals: ApprovalRepository
    tickets: WebSocketTicketStore
    admin_settings: AdminSettingsRepository
    quotas: QuotaRepository
    cleanup: CleanupRepository | None
    coordination: UpstashRedisStore | None
    database_engine: AsyncEngine | None
    jwt_verifier: TokenVerifier
    runtime: RuntimeProvider
    agent: AgentAdapter
    worker_client: WorkerClient | None
    templates: tuple[TemplateResponse, ...]
    features: tuple[CapabilityItem, ...]
    fake_flows: InMemoryFakeFlowStore

    async def close(self) -> None:
        if self.coordination is not None:
            await self.coordination.close()
        if self.worker_client is not None:
            await self.worker_client.close()
        if self.database_engine is not None:
            await self.database_engine.dispose()


def build_container(
    settings: Settings,
    *,
    jwks_provider: JWKSProvider | None = None,
) -> ApplicationContainer:
    use_fake_runtime = (
        settings.environment is DeploymentEnvironment.TEST
        or settings.runtime_backend is RuntimeBackend.FAKE
    )
    if use_fake_runtime:
        runtime: RuntimeProvider = FakeRuntimeProvider()
    else:
        runtime = E2BRuntimeProvider(
            api_key=(
                settings.e2b_api_key.get_secret_value()
                if settings.e2b_api_key is not None
                else None
            ),
            template_ids={
                "python-cli": settings.e2b_python_cli_template,
                "static-site": settings.e2b_static_site_template,
                "vite-react": settings.e2b_vite_react_template,
            },
            request_timeout_seconds=settings.e2b_request_timeout_seconds,
        )
    runtime_capability = runtime.capability()
    template_status = runtime_capability.status
    template_provider = runtime_capability.provider
    templates = (
        TemplateResponse(
            id="python-cli",
            name="Python CLI",
            description="Python project tools with the pinned LunarForge core package.",
            runtime_provider=template_provider,
            status=template_status,
        ),
        TemplateResponse(
            id="static-site",
            name="Static site",
            description="Offline static-site workspace with bounded project tools.",
            runtime_provider=template_provider,
            status=template_status,
        ),
        TemplateResponse(
            id="vite-react",
            name="Vite React",
            description="Offline Vite and React workspace with pinned Node tooling.",
            runtime_provider=template_provider,
            status=template_status,
        ),
    )
    features = (
        CapabilityItem(
            id="structured-events",
            status=(
                Availability.AVAILABLE
                if settings.turn_execution_backend is TurnExecutionBackend.PRIVATE_WORKER
                else Availability.FAKE
            ),
            description="Schema-v1 event envelopes are persisted to a bounded ordered stream.",
        ),
        CapabilityItem(
            id="websocket-tickets",
            status=(
                Availability.AVAILABLE
                if settings.infrastructure_backend
                is InfrastructureBackend.NEON_UPSTASH
                else Availability.FAKE
            ),
            description=(
                "One-time tickets are hashed and consumed atomically in Redis."
                if settings.infrastructure_backend
                is InfrastructureBackend.NEON_UPSTASH
                else "One-time tickets are hashed in the deterministic process-local store."
            ),
        ),
        CapabilityItem(
            id="hosted-runtime",
            status=runtime_capability.status,
            description=(
                "E2B uses secure access, kill-on-timeout, and provider-enforced egress rules."
                if runtime_capability.provider == "e2b"
                else "The deterministic test runtime is selected explicitly."
            ),
        ),
        CapabilityItem(
            id="temporary-egress",
            status=(
                Availability.AVAILABLE
                if runtime_capability.supports_temporary_egress
                else Availability.UNAVAILABLE
            ),
            description=(
                "Approved operations use atomically replaced E2B hostname allowlists."
                if runtime_capability.supports_temporary_egress
                else "The selected runtime cannot enforce temporary egress."
            ),
        ),
        CapabilityItem(
            id="public-git-clone",
            status=(
                Availability.AVAILABLE
                if runtime_capability.supports_public_git_clone
                else Availability.UNAVAILABLE
            ),
            description="Credential-free, shallow HTTPS github.com clones only.",
        ),
        CapabilityItem(
            id="external-browser-egress",
            status=Availability.UNAVAILABLE,
            description=(
                "Arbitrary external browser validation remains disabled pending "
                "redirect-safe destination enforcement."
            ),
        ),
        CapabilityItem(
            id="real-model",
            status=(
                Availability.AVAILABLE
                if settings.turn_execution_backend is TurnExecutionBackend.PRIVATE_WORKER
                else Availability.UNAVAILABLE
            ),
            description="The private worker injects one in-memory model client per turn.",
        ),
    )
    users: UserRepository = InMemoryUserRepository()
    verifier: TokenVerifier = SupabaseJWTVerifier(settings, jwks_provider)
    if settings.fake_auth_enabled:
        verifier = DeterministicFakeTokenVerifier()
        users = InMemoryUserRepository(
            (
                UserRecord(id="user-e2e", email="user-e2e@example.com"),
                UserRecord(
                    id="admin-e2e",
                    email="admin-e2e@example.com",
                    role=UserRole.ADMIN,
                ),
            )
        )
    sandboxes: SandboxRepository = InMemorySandboxRepository()
    sessions: SessionRepository = InMemorySessionRepository()
    events: EventRepository = InMemoryEventRepository()
    controls: ApprovalControlStore = InMemoryControlStore()
    turns: TurnRepository = InMemoryTurnRepository()
    approvals: ApprovalRepository = InMemoryApprovalRepository()
    tickets: WebSocketTicketStore = InMemoryWebSocketTicketStore(
        settings.websocket_ticket_ttl_seconds
    )
    admin_settings: AdminSettingsRepository = InMemoryAdminSettingsRepository()
    quotas: QuotaRepository = InMemoryQuotaRepository(admin_settings)
    cleanup: CleanupRepository | None = None
    coordination: UpstashRedisStore | None = None
    database_engine: AsyncEngine | None = None
    if settings.infrastructure_backend is InfrastructureBackend.NEON_UPSTASH:
        database_engine = create_database_engine(settings.database_url)
        factory = create_session_factory(database_engine)
        coordination = UpstashRedisStore(
            create_redis_client(
                settings.redis_url.get_secret_value(),
                max_connections=settings.redis_max_connections,
                socket_timeout_seconds=settings.redis_socket_timeout_seconds,
            ),
            key_prefix=settings.redis_key_prefix,
            event_ttl_seconds=settings.event_stream_ttl_seconds,
            control_ttl_seconds=settings.control_stream_ttl_seconds,
        )
        users = PostgresUserRepository(factory)
        sandboxes = PostgresSandboxRepository(factory)
        sessions = PostgresSessionRepository(factory)
        events = coordination
        controls = coordination
        tickets = RedisWebSocketTicketStore(
            coordination, settings.websocket_ticket_ttl_seconds
        )
        admin_settings = PostgresAdminSettingsRepository(factory)
        quotas = PostgresQuotaRepository(factory, admin_settings)
        cleanup = PostgresCleanupRepository(factory)
        turns = PostgresTurnRepository(factory)
        approvals = PostgresApprovalRepository(factory)

    agent: AgentAdapter = FakeCoreAgentAdapter()
    if settings.service_role is ServiceRole.WORKER:
        async def resolve_runtime(request):
            sandbox = await sandboxes.get(request.sandbox_id)
            if sandbox is None or sandbox.owner_id != request.owner_id:
                raise PermissionError("Owned sandbox runtime was not found.")
            selected = runtime_sandbox(sandbox)
            await runtime.connect(selected)
            return HostedWorkspaceRuntime(runtime, selected, asyncio.get_running_loop())

        agent = CoreAgentAdapter(
            events,
            runtime_resolver=resolve_runtime,
            model_client_resolver=lambda request: create_turn_model_client(
                request, settings
            ),
            approval_broker=RedisApprovalBroker(controls),
        )

    worker_client: WorkerClient | None = None
    if (
        settings.service_role is ServiceRole.API
        and settings.turn_execution_backend is TurnExecutionBackend.PRIVATE_WORKER
        and settings.worker_url is not None
        and settings.worker_audience is not None
    ):
        worker_client = CloudRunWorkerClient(
            worker_url=settings.worker_url,
            audience=settings.worker_audience,
            shared_secret=settings.worker_shared_secret,
            request_timeout_seconds=settings.worker_request_timeout_seconds,
            identity_timeout_seconds=settings.worker_identity_token_timeout_seconds,
        )

    return ApplicationContainer(
        settings=settings,
        users=users,
        sandboxes=sandboxes,
        sessions=sessions,
        events=events,
        controls=controls,
        turns=turns,
        approvals=approvals,
        tickets=tickets,
        admin_settings=admin_settings,
        quotas=quotas,
        cleanup=cleanup,
        coordination=coordination,
        database_engine=database_engine,
        jwt_verifier=verifier,
        runtime=runtime,
        agent=agent,
        worker_client=worker_client,
        templates=templates,
        features=features,
        fake_flows=InMemoryFakeFlowStore(),
    )
