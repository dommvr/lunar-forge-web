"""Explicit dependency container for API/worker factories and tests."""

from __future__ import annotations

from dataclasses import dataclass

from lunar_forge_web.auth.supabase import (
    DeterministicFakeTokenVerifier,
    JWKSProvider,
    SupabaseJWTVerifier,
    TokenVerifier,
)
from lunar_forge_web.config import Settings
from lunar_forge_web.core.adapter import CoreAgentAdapter, FakeCoreAgentAdapter
from lunar_forge_web.domain.enums import Availability, UserRole
from lunar_forge_web.domain.models import CapabilityItem, TemplateResponse, UserRecord
from lunar_forge_web.runtime.base import RuntimeProvider
from lunar_forge_web.runtime.fake import FakeRuntimeProvider
from lunar_forge_web.security.tickets import InMemoryWebSocketTicketStore
from lunar_forge_web.storage.repositories import (
    EventRepository,
    InMemoryEventRepository,
    InMemorySandboxRepository,
    InMemorySessionRepository,
    InMemoryUserRepository,
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
    tickets: InMemoryWebSocketTicketStore
    jwt_verifier: TokenVerifier
    runtime: RuntimeProvider
    agent: CoreAgentAdapter
    templates: tuple[TemplateResponse, ...]
    features: tuple[CapabilityItem, ...]
    fake_flows: InMemoryFakeFlowStore


def build_container(
    settings: Settings,
    *,
    jwks_provider: JWKSProvider | None = None,
) -> ApplicationContainer:
    runtime = FakeRuntimeProvider()
    templates = (
        TemplateResponse(
            id="python-cli",
            name="Python CLI",
            description="Deterministic contract fixture; hosted execution is not connected.",
            runtime_provider="fake",
            status=Availability.FAKE,
        ),
        TemplateResponse(
            id="static-site",
            name="Static site",
            description="Deterministic contract fixture; hosted execution is not connected.",
            runtime_provider="fake",
            status=Availability.FAKE,
        ),
        TemplateResponse(
            id="vite-react",
            name="Vite React",
            description="Deterministic contract fixture; hosted execution is not connected.",
            runtime_provider="fake",
            status=Availability.FAKE,
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
            status=Availability.FAKE,
            description="One-time tickets are hashed and process-local until Redis integration.",
        ),
        CapabilityItem(
            id="hosted-runtime",
            status=Availability.PLANNED,
            description="E2B is intentionally not connected in this phase.",
        ),
        CapabilityItem(
            id="real-model",
            status=Availability.UNAVAILABLE,
            description="No real model client is called in this phase.",
        ),
    )
    users = InMemoryUserRepository()
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
    return ApplicationContainer(
        settings=settings,
        users=users,
        sandboxes=InMemorySandboxRepository(),
        sessions=InMemorySessionRepository(),
        events=InMemoryEventRepository(),
        tickets=InMemoryWebSocketTicketStore(settings.websocket_ticket_ttl_seconds),
        jwt_verifier=verifier,
        runtime=runtime,
        agent=FakeCoreAgentAdapter(),
        templates=templates,
        features=features,
        fake_flows=InMemoryFakeFlowStore(),
    )
