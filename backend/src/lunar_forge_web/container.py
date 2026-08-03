"""Explicit dependency container for API/worker factories and tests."""

from __future__ import annotations

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
    Settings,
)
from lunar_forge_web.core.adapter import AgentAdapter, FakeCoreAgentAdapter
from lunar_forge_web.domain.enums import Availability, UserRole
from lunar_forge_web.domain.models import CapabilityItem, TemplateResponse, UserRecord
from lunar_forge_web.runtime.base import RuntimeProvider
from lunar_forge_web.runtime.e2b_provider import E2BRuntimeProvider
from lunar_forge_web.runtime.fake import FakeRuntimeProvider
from lunar_forge_web.security.tickets import (
    InMemoryWebSocketTicketStore,
    WebSocketTicketStore,
)
from lunar_forge_web.storage.database import create_database_engine, create_session_factory
from lunar_forge_web.storage.postgres import (
    PostgresAdminSettingsRepository,
    PostgresCleanupRepository,
    PostgresQuotaRepository,
    PostgresSandboxRepository,
    PostgresSessionRepository,
    PostgresUserRepository,
)
from lunar_forge_web.storage.redis import (
    RedisWebSocketTicketStore,
    UpstashRedisStore,
    create_redis_client,
)
from lunar_forge_web.storage.repositories import (
    AdminSettingsRepository,
    CleanupRepository,
    EventRepository,
    InMemoryAdminSettingsRepository,
    InMemoryEventRepository,
    InMemoryQuotaRepository,
    InMemorySandboxRepository,
    InMemorySessionRepository,
    InMemoryUserRepository,
    QuotaRepository,
    SandboxRepository,
    SessionRepository,
    UserRepository,
)
from lunar_forge_web.storage.fake_state import InMemoryFakeFlowStore


@dataclass(slots=True)
class ApplicationContainer:
    settings: Settings
    users: UserRepository
    sandboxes: SandboxRepository
    sessions: SessionRepository
    events: EventRepository
    tickets: WebSocketTicketStore
    admin_settings: AdminSettingsRepository
    quotas: QuotaRepository
    cleanup: CleanupRepository | None
    coordination: UpstashRedisStore | None
    database_engine: AsyncEngine | None
    jwt_verifier: TokenVerifier
    runtime: RuntimeProvider
    agent: AgentAdapter
    templates: tuple[TemplateResponse, ...]
    features: tuple[CapabilityItem, ...]
    fake_flows: InMemoryFakeFlowStore

    async def close(self) -> None:
        if self.coordination is not None:
            await self.coordination.close()
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
            status=Availability.FAKE,
            description="Schema-v1 event envelopes are emitted by a deterministic fake agent.",
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
            status=Availability.UNAVAILABLE,
            description="No real model client is called in this phase.",
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
        tickets = RedisWebSocketTicketStore(
            coordination, settings.websocket_ticket_ttl_seconds
        )
        admin_settings = PostgresAdminSettingsRepository(factory)
        quotas = PostgresQuotaRepository(factory, admin_settings)
        cleanup = PostgresCleanupRepository(factory)

    return ApplicationContainer(
        settings=settings,
        users=users,
        sandboxes=sandboxes,
        sessions=sessions,
        events=events,
        tickets=tickets,
        admin_settings=admin_settings,
        quotas=quotas,
        cleanup=cleanup,
        coordination=coordination,
        database_engine=database_engine,
        jwt_verifier=verifier,
        runtime=runtime,
        agent=FakeCoreAgentAdapter(),
        templates=templates,
        features=features,
        fake_flows=InMemoryFakeFlowStore(),
    )
