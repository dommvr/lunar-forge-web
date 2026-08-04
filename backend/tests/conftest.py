from __future__ import annotations

import json
from collections.abc import Callable, Iterator
from datetime import datetime, timedelta, timezone

import jwt
import pytest
from cryptography.hazmat.primitives.asymmetric import ec
from fastapi.testclient import TestClient
from jwt.algorithms import ECAlgorithm
from pydantic import SecretStr

from lunar_forge_web.api.main import create_app
from lunar_forge_web.auth.supabase import StaticJWKSProvider
from lunar_forge_web.config import DeploymentEnvironment, Settings
from lunar_forge_web.container import ApplicationContainer, build_container
from lunar_forge_web.domain.enums import SandboxStatus, SessionStatus, UserRole
from lunar_forge_web.domain.models import SandboxResponse, SessionResponse, UserRecord
from lunar_forge_web.storage.repositories import (
    InMemorySandboxRepository,
    InMemorySessionRepository,
    InMemoryUserRepository,
)


TEST_ISSUER = "https://test-project.supabase.co/auth/v1"
TEST_KID = "test-es256-key"
TEST_PRIVATE_KEY = ec.derive_private_key(1, ec.SECP256R1())
_PUBLIC_JWK = json.loads(ECAlgorithm.to_jwk(TEST_PRIVATE_KEY.public_key()))
_PUBLIC_JWK.update({"kid": TEST_KID, "alg": "ES256", "use": "sig"})
TEST_JWKS = {"keys": [_PUBLIC_JWK]}
NOW = datetime.now(timezone.utc)


@pytest.fixture
def settings() -> Settings:
    return Settings(
        environment=DeploymentEnvironment.TEST,
        cors_allowed_origins=("https://web.example.test",),
        supabase_issuer=TEST_ISSUER,
        supabase_jwks_url=f"{TEST_ISSUER}/.well-known/jwks.json",
        supabase_audience="authenticated",
        database_url="sqlite+aiosqlite:///:memory:",
        worker_shared_secret=SecretStr("test-worker-secret-with-at-least-32-characters"),
        log_level="WARNING",
    )


@pytest.fixture
def token_factory(settings: Settings) -> Callable[..., str]:
    def make_token(
        subject: str = "user-a",
        *,
        email: str = "user-a@example.com",
        aal: str = "aal1",
        role: str = "authenticated",
        issuer: str | None = None,
        audience: str | None = None,
        expires_delta: int = 3_600,
        private_key=TEST_PRIVATE_KEY,
        kid: str = TEST_KID,
    ) -> str:
        now = int(datetime.now(timezone.utc).timestamp())
        return jwt.encode(
            {
                "sub": subject,
                "email": email,
                "aal": aal,
                "role": role,
                "iss": issuer or settings.supabase_issuer,
                "aud": audience or settings.supabase_audience,
                "iat": now - 5,
                "exp": now + expires_delta,
            },
            private_key,
            algorithm="ES256",
            headers={"kid": kid, "typ": "JWT"},
        )

    return make_token


@pytest.fixture
def container(settings: Settings) -> ApplicationContainer:
    selected = build_container(settings, jwks_provider=StaticJWKSProvider(TEST_JWKS))
    selected.users = InMemoryUserRepository(
        (
            UserRecord(id="user-a", email="user-a@example.com"),
            UserRecord(id="user-b", email="user-b@example.com"),
            UserRecord(
                id="admin-a",
                email="admin-a@example.com",
                role=UserRole.ADMIN,
            ),
            UserRecord(
                id="suspended-a",
                email="suspended-a@example.com",
                suspended=True,
            ),
        )
    )
    selected.sandboxes = InMemorySandboxRepository(
        (
            SandboxResponse(
                id="sandbox-a",
                owner_id="user-a",
                template_id="python-cli",
                runtime_provider="fake",
                runtime_reference="runtime-a",
                status=SandboxStatus.READY,
                created_at=NOW,
                last_activity_at=NOW,
                expires_at=NOW + timedelta(minutes=30),
            ),
            SandboxResponse(
                id="sandbox-b",
                owner_id="user-b",
                template_id="static-site",
                runtime_provider="fake",
                runtime_reference="runtime-b",
                status=SandboxStatus.READY,
                created_at=NOW,
                last_activity_at=NOW,
                expires_at=NOW + timedelta(minutes=30),
            ),
        )
    )
    selected.sessions = InMemorySessionRepository(
        (
            SessionResponse(
                id="session-a",
                sandbox_id="sandbox-a",
                owner_id="user-a",
                status=SessionStatus.ACTIVE,
                created_at=NOW,
            ),
            SessionResponse(
                id="session-b",
                sandbox_id="sandbox-b",
                owner_id="user-b",
                status=SessionStatus.ACTIVE,
                created_at=NOW,
            ),
        )
    )
    return selected


@pytest.fixture
def client(settings: Settings, container: ApplicationContainer) -> Iterator[TestClient]:
    with TestClient(create_app(settings, container), raise_server_exceptions=False) as test_client:
        yield test_client


@pytest.fixture
def auth_headers(token_factory: Callable[..., str]) -> Callable[..., dict[str, str]]:
    def headers(subject: str = "user-a", **kwargs) -> dict[str, str]:
        if "email" not in kwargs:
            kwargs["email"] = f"{subject}@example.com"
        return {"Authorization": f"Bearer {token_factory(subject, **kwargs)}"}

    return headers
