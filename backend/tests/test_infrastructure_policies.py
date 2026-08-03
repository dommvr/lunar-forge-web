from pydantic import SecretStr

from lunar_forge_web.config import InfrastructureBackend
from lunar_forge_web.container import build_container
from lunar_forge_web.storage.postgres import (
    PostgresSandboxRepository,
    PostgresSessionRepository,
    PostgresUserRepository,
)
from lunar_forge_web.storage.redis import RedisWebSocketTicketStore, UpstashRedisStore


async def test_container_selects_shared_adapters_explicitly(settings):
    production_shaped = settings.model_copy(
        update={
            "infrastructure_backend": InfrastructureBackend.NEON_UPSTASH,
            "redis_url": SecretStr("redis://127.0.0.1:6379/15"),
            "redis_key_prefix": "lfw:contract",
        }
    )
    container = build_container(production_shaped)
    try:
        assert isinstance(container.users, PostgresUserRepository)
        assert isinstance(container.sandboxes, PostgresSandboxRepository)
        assert isinstance(container.sessions, PostgresSessionRepository)
        assert isinstance(container.events, UpstashRedisStore)
        assert isinstance(container.tickets, RedisWebSocketTicketStore)
    finally:
        await container.close()


def test_admin_settings_enforce_kill_switch_and_owner_funded_disable(
    client, auth_headers
):
    admin_headers = auth_headers("admin-a", email="admin-a@example.com", aal="aal2")
    disabled = client.patch(
        "/api/v1/admin/settings",
        headers=admin_headers,
        json={"owner_funded_enabled": False},
    )
    assert disabled.status_code == 200
    assert disabled.json()["owner_funded_enabled"] is False

    turn = client.post(
        "/api/v1/sessions/session-a/turns",
        headers=auth_headers("user-a"),
        json={"message": "Use the owner-funded model."},
    )
    assert turn.status_code == 503
    assert turn.json()["error"]["code"] == "owner_funded_disabled"

    enabled = client.post(
        "/api/v1/admin/kill-switch/enable",
        headers=admin_headers,
    )
    assert enabled.status_code == 200
    create = client.post(
        "/api/v1/sandboxes",
        headers=auth_headers("user-b"),
        json={"template_id": "python-cli"},
    )
    assert create.status_code == 503
    assert create.json()["error"]["code"] == "sandbox_kill_switch"


def test_actual_request_body_is_bounded(settings):
    from fastapi.testclient import TestClient

    from lunar_forge_web.api.main import create_app

    selected = settings.model_copy(
        update={"fake_auth_enabled": True, "max_request_body_bytes": 16_384}
    )
    container = build_container(selected)
    with TestClient(create_app(selected, container)) as client:
        response = client.post(
            "/api/v1/realtime/tickets",
            headers={"Authorization": "Bearer e2e-user"},
            json={"padding": "x" * 20_000},
        )
    assert response.status_code == 413
    assert response.json()["error"]["code"] == "request_too_large"
