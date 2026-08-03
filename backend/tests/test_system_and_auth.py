from fastapi.testclient import TestClient


def test_health_version_and_capabilities_are_truthful(client: TestClient):
    health = client.get("/api/v1/health")
    version = client.get("/api/v1/version")
    capabilities = client.get("/api/v1/capabilities")
    templates = client.get("/api/v1/templates")

    assert health.status_code == 200
    assert health.json() == {"status": "ok", "service": "api", "environment": "test"}
    assert version.json()["core_version"] == "0.1.0"
    assert version.json()["event_schema_version"] == 1
    assert capabilities.json()["runtimes"] == [
        {
            "provider": "fake",
            "status": "fake",
            "network_policy": "offline",
            "supports_preview": False,
            "supports_command_cancellation": True,
        }
    ]
    features = {item["id"]: item["status"] for item in capabilities.json()["features"]}
    assert features["hosted-runtime"] == "planned"
    assert features["real-model"] == "unavailable"
    assert {item["id"] for item in templates.json()["items"]} == {
        "python-cli",
        "static-site",
        "vite-react",
    }


def test_me_uses_verified_identity_and_server_role(client, auth_headers):
    response = client.get("/api/v1/me", headers=auth_headers())

    assert response.status_code == 200
    assert response.json()["user"] == {
        "id": "user-a",
        "email": "user-a@example.com",
        "role": "user",
        "suspended": False,
        "assurance_level": "aal1",
    }


def test_missing_invalid_unprovisioned_and_suspended_auth_use_envelopes(
    client,
    auth_headers,
):
    missing = client.get("/api/v1/me", headers={"X-Request-ID": "req-test"})
    invalid = client.get("/api/v1/me", headers={"Authorization": "Bearer invalid"})
    unknown = client.get("/api/v1/me", headers=auth_headers("unknown-a"))
    suspended = client.get("/api/v1/me", headers=auth_headers("suspended-a"))

    assert missing.status_code == 401
    assert missing.json() == {
        "error": {
            "code": "authentication_required",
            "message": "Authentication is required.",
            "request_id": "req-test",
        }
    }
    assert invalid.json()["error"]["code"] == "invalid_token"
    assert unknown.json()["error"]["code"] == "account_not_provisioned"
    assert suspended.json()["error"]["code"] == "account_suspended"


def test_admin_role_is_server_controlled_and_requires_aal2(client, auth_headers):
    ordinary = client.get("/api/v1/admin/overview", headers=auth_headers("user-a", aal="aal2"))
    aal1 = client.get("/api/v1/admin/overview", headers=auth_headers("admin-a", aal="aal1"))
    aal2 = client.get("/api/v1/admin/overview", headers=auth_headers("admin-a", aal="aal2"))

    assert ordinary.status_code == 403
    assert ordinary.json()["error"]["code"] == "admin_required"
    assert aal1.status_code == 403
    assert aal2.status_code == 200
    assert aal2.json()["users_total"] == 0


def test_cors_is_allowlisted(client):
    allowed = client.options(
        "/api/v1/me",
        headers={
            "Origin": "https://web.example.test",
            "Access-Control-Request-Method": "GET",
        },
    )
    denied = client.options(
        "/api/v1/me",
        headers={
            "Origin": "https://evil.example",
            "Access-Control-Request-Method": "GET",
        },
    )

    assert allowed.status_code == 200
    assert allowed.headers["access-control-allow-origin"] == "https://web.example.test"
    assert denied.status_code == 400
    assert denied.headers.get("access-control-allow-origin") is None
