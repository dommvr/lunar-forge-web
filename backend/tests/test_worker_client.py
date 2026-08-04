import json

import httpx
import pytest
from pydantic import SecretStr

from lunar_forge_web.domain.models import SessionSettings, WorkerTurnRequest
from lunar_forge_web.worker.client import (
    CloudRunWorkerClient,
    WorkerInvocationError,
)


class StaticIdentityTokens:
    def __init__(self) -> None:
        self.audiences: list[str] = []

    async def token(self, audience: str) -> str:
        self.audiences.append(audience)
        return "google-signed-id-token"


def request() -> WorkerTurnRequest:
    return WorkerTurnRequest(
        sandbox_id="sandbox-a",
        session_id="session-a",
        turn_id="turn-a",
        owner_id="user-a",
        message="Inspect the project.",
        settings=SessionSettings(
            funding_mode="byok",
            provider="anthropic",
            model="anthropic/test-model",
        ),
        provider_credential=SecretStr("sk-ant-current-request-only"),
    )


async def test_cloud_run_client_uses_google_identity_and_server_secret_headers():
    observed: dict[str, object] = {}

    def handler(incoming: httpx.Request) -> httpx.Response:
        observed["headers"] = dict(incoming.headers)
        observed["payload"] = json.loads(incoming.content)
        return httpx.Response(
            200,
            json={
                "turn_id": "turn-a",
                "status": "completed",
                "last_sequence": 7,
                "input_tokens": 10,
                "output_tokens": 4,
                "estimated_cost_microusd": 0,
                "error_code": None,
            },
        )

    tokens = StaticIdentityTokens()
    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CloudRunWorkerClient(
        worker_url="https://worker.example.run.app",
        audience="https://worker.example.run.app",
        shared_secret=SecretStr("server-shared-secret"),
        request_timeout_seconds=960,
        identity_timeout_seconds=10,
        client=http,
        identity_tokens=tokens,
    )

    response = await client.run_turn(request())
    await http.aclose()

    headers = observed["headers"]
    payload = observed["payload"]
    assert tokens.audiences == ["https://worker.example.run.app"]
    assert headers["authorization"] == "Bearer server-shared-secret"
    assert headers["x-serverless-authorization"] == "Bearer google-signed-id-token"
    assert payload["provider_credential"] == "sk-ant-current-request-only"
    assert response.last_sequence == 7
    assert "sk-ant-current-request-only" not in repr(request())


async def test_worker_transport_errors_never_echo_private_request_credentials():
    def handler(_: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("synthetic transport failure")

    http = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    client = CloudRunWorkerClient(
        worker_url="https://worker.example.run.app",
        audience="https://worker.example.run.app",
        shared_secret=SecretStr("server-shared-secret"),
        request_timeout_seconds=960,
        identity_timeout_seconds=10,
        client=http,
        identity_tokens=StaticIdentityTokens(),
    )

    with pytest.raises(WorkerInvocationError) as raised:
        await client.run_turn(request())
    await http.aclose()

    assert raised.value.code == "worker_unavailable"
    assert "sk-ant-current-request-only" not in raised.value.message
