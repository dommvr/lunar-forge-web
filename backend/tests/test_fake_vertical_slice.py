from fastapi.testclient import TestClient

from lunar_forge_web.api.main import create_app
from lunar_forge_web.auth.supabase import DeterministicFakeTokenVerifier
from lunar_forge_web.config import DeploymentEnvironment, Settings
from lunar_forge_web.container import build_container


def test_fake_auth_is_explicitly_test_only(settings):
    fake_settings = settings.model_copy(update={"fake_auth_enabled": True})
    container = build_container(fake_settings)
    assert isinstance(container.jwt_verifier, DeterministicFakeTokenVerifier)


def test_fake_vertical_slice_and_replay(settings):
    fake_settings = settings.model_copy(update={"fake_auth_enabled": True})
    container = build_container(fake_settings)
    headers = {"Authorization": "Bearer e2e-user"}

    with TestClient(create_app(fake_settings, container)) as client:
        sandbox = client.post(
            "/api/v1/sandboxes",
            headers=headers,
            json={"template_id": "vite-react"},
        )
        assert sandbox.status_code == 201
        sandbox_id = sandbox.json()["id"]

        session = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/sessions",
            headers=headers,
            json={"settings": {"funding_mode": "owner_funded"}},
        )
        assert session.status_code == 201
        session_id = session.json()["id"]

        turn = client.post(
            f"/api/v1/sessions/{session_id}/turns",
            headers=headers,
            json={"message": "Add a responsive pricing section"},
        )
        assert turn.status_code == 202
        assert turn.json()["status"] == "waiting_for_approval"

        replay = client.get(
            f"/api/v1/sessions/{session_id}/events?after_sequence=0",
            headers=headers,
        ).json()
        sequences = [event["sequence"] for event in replay["events"]]
        assert sequences == list(range(1, len(sequences) + 1))
        approval_event = next(
            event for event in replay["events"] if event["type"] == "permission.requested"
        )
        approval_id = approval_event["payload"]["request_id"]

        ticket = client.post(
            "/api/v1/realtime/tickets",
            headers=headers,
            json={"session_id": session_id},
        ).json()["ticket"]
        with client.websocket_connect(
            f"/api/v1/sessions/{session_id}/stream?ticket={ticket}"
        ) as websocket:
            assert websocket.receive_json()["type"] == "stream.ready"
            assert websocket.receive_json()["type"] == "session.started"

        approval = client.post(
            f"/api/v1/sessions/{session_id}/approvals/{approval_id}",
            headers=headers,
            json={"approved": True, "reason": "Run validation"},
        )
        assert approval.status_code == 200

        final_replay = client.get(
            f"/api/v1/sessions/{session_id}/events?after_sequence={replay['last_sequence']}",
            headers=headers,
        ).json()
        assert [event["type"] for event in final_replay["events"]][-1] == "turn.finished"
        assert client.get(
            f"/api/v1/sandboxes/{sandbox_id}/files",
            headers=headers,
        ).status_code == 200
        artifacts = client.get(
            f"/api/v1/sessions/{session_id}/artifacts",
            headers=headers,
        ).json()["items"]
        assert artifacts[0]["name"] == "validation-report.json"

        compact = client.post(
            f"/api/v1/sessions/{session_id}/compact",
            headers=headers,
        )
        assert compact.status_code == 200
        assert compact.json()["compacted"] is True

        reset = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/reset",
            headers=headers,
        )
        assert reset.status_code == 200
        assert client.get(
            f"/api/v1/sessions/{session_id}",
            headers=headers,
        ).status_code == 404


def test_fake_cancellation_emits_confirmed_rollback(settings):
    fake_settings = settings.model_copy(update={"fake_auth_enabled": True})
    container = build_container(fake_settings)
    headers = {"Authorization": "Bearer e2e-user"}
    with TestClient(create_app(fake_settings, container)) as client:
        sandbox_id = client.post(
            "/api/v1/sandboxes",
            headers=headers,
            json={"template_id": "vite-react"},
        ).json()["id"]
        session_id = client.post(
            f"/api/v1/sandboxes/{sandbox_id}/sessions",
            headers=headers,
            json={},
        ).json()["id"]
        client.post(
            f"/api/v1/sessions/{session_id}/turns",
            headers=headers,
            json={"message": "Make a change"},
        )

        cancelled = client.post(
            f"/api/v1/sessions/{session_id}/cancel",
            headers=headers,
        )
        assert cancelled.status_code == 200
        assert "Pricing.tsx removed" in cancelled.json()["rollback_report"]
        events = client.get(
            f"/api/v1/sessions/{session_id}/events",
            headers=headers,
        ).json()["events"]
        rollback = next(event for event in events if event["type"] == "rollback.finished")
        assert rollback["payload"] == {
            "status": "completed",
            "restored_files": ["app/page.tsx", "package.json"],
            "removed_files": ["components/Pricing.tsx"],
            "skipped_files": [],
            "errors": [],
        }


def test_fake_auth_is_rejected_by_production_configuration():
    try:
        Settings(
            environment=DeploymentEnvironment.PRODUCTION,
            fake_auth_enabled=True,
            cors_allowed_origins=("https://app.example.com",),
            supabase_issuer="https://project.supabase.co/auth/v1",
            supabase_jwks_url="https://project.supabase.co/auth/v1/.well-known/jwks.json",
            database_url="postgresql+asyncpg://user:pass@db.example.com/app",
            worker_shared_secret="x" * 40,
        )
    except ValueError as exc:
        assert "Fake authentication" in str(exc)
    else:
        raise AssertionError("Production accepted deterministic fake authentication.")
