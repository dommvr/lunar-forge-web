import asyncio
import json

from fastapi.testclient import TestClient

from lunar_forge_web.domain.enums import TurnStatus
from lunar_forge_web.domain.models import SessionSettings, TurnResponse
from lunar_forge_web.worker.main import create_worker_app


TURN = {
    "sandbox_id": "sandbox-a",
    "session_id": "session-a",
    "turn_id": "turn-a",
    "owner_id": "user-a",
    "message": "Inspect the project without external calls.",
    "settings": {
        "funding_mode": "byok",
        "provider": "openai",
        "model": "server-default",
    },
    "provider_credential": "sk-byok-ephemeral-proof-123456789",
}


def test_private_worker_rejects_missing_and_wrong_tokens(settings, container):
    with TestClient(create_worker_app(settings, container), raise_server_exceptions=False) as client:
        missing = client.post("/internal/v1/turns:run", json=TURN)
        wrong = client.post(
            "/internal/v1/turns:run",
            json=TURN,
            headers={"Authorization": "Bearer wrong"},
        )

    assert missing.status_code == 401
    assert wrong.status_code == 401
    assert missing.json()["error"]["code"] == "worker_authentication_required"


def test_private_worker_returns_deterministic_core_event_contract(settings, container):
    asyncio.run(
        container.turns.create(
            TurnResponse(
                id="turn-a",
                session_id="session-a",
                owner_id="user-a",
                status=TurnStatus.QUEUED,
            ),
            sandbox_id="sandbox-a",
            prompt=TURN["message"],
            settings=SessionSettings(**TURN["settings"]),
        )
    )
    secret = settings.worker_shared_secret.get_secret_value()
    with TestClient(create_worker_app(settings, container)) as client:
        response = client.post(
            "/internal/v1/turns:run",
            json=TURN,
            headers={"Authorization": f"Bearer {secret}"},
        )

    assert response.status_code == 200
    payload = response.json()
    assert payload["status"] == "completed"
    assert payload["last_sequence"] == 4
    replay = asyncio.run(container.events.replay("session-a", 0, 10))
    assert [event.sequence for event in replay] == [1, 2, 3, 4]
    assert [event.type for event in replay] == [
        "turn.started",
        "status.updated",
        "assistant.message.completed",
        "turn.finished",
    ]
    assert "Inspect the project" not in response.text
    assert TURN["provider_credential"] not in response.text
    assert TURN["provider_credential"] not in json.dumps(
        [event.model_dump(mode="json") for event in replay]
    )
