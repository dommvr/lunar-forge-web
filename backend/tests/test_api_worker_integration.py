import asyncio

import lunar_forge.public_api as public_api
from lunar_forge import ModelResponse, ModelUsage, load_config

from lunar_forge_web.core.adapter import CoreAgentAdapter
from lunar_forge_web.core.runtime import HostedWorkspaceRuntime
from lunar_forge_web.services.sandbox_service import runtime_sandbox
from lunar_forge_web.worker.client import InProcessWorkerClient
from lunar_forge_web.worker.turn_runner import TurnRunner


class OneResponseModel:
    def __init__(self) -> None:
        self.calls = 0

    def complete(self, messages, tools=None):
        del messages, tools
        self.calls += 1
        return ModelResponse(
            text="The deterministic private worker turn completed.",
            usage=ModelUsage(
                input_tokens=120,
                output_tokens=30,
                total_tokens=150,
                model="openai/test-model",
                provider="openai",
                exact=True,
            ),
        )


def test_api_invokes_worker_while_events_are_persisted_for_replay(
    client, container, settings, auth_headers, monkeypatch, tmp_path
):
    model = OneResponseModel()
    clean_config = load_config(
        tmp_path,
        cli_overrides={
            "mcp": {"enabled": False},
            "plugins": {"enabled": False},
            "subagents": {"enabled": False},
        },
    )
    monkeypatch.setattr(public_api, "load_config", lambda *_args, **_kwargs: clean_config)

    async def resolve_runtime(request):
        sandbox = await container.sandboxes.get(request.sandbox_id)
        assert sandbox is not None
        return HostedWorkspaceRuntime(
            container.runtime,
            runtime_sandbox(sandbox),
            asyncio.get_running_loop(),
        )

    container.agent = CoreAgentAdapter(
        container.events,
        runtime_resolver=resolve_runtime,
        model_client_resolver=lambda _: model,
    )
    runner = TurnRunner(
        container.agent,
        settings=settings,
        turns=container.turns,
        approvals=container.approvals,
        events=container.events,
        sessions=container.sessions,
        sandboxes=container.sandboxes,
        runtime=container.runtime,
        quotas=container.quotas,
        controls=container.controls,
    )
    container.worker_client = InProcessWorkerClient(runner)

    response = client.post(
        "/api/v1/sessions/session-a/turns",
        headers=auth_headers("user-a"),
        json={
            "message": "Run a deterministic private worker turn.",
            "settings": {
                "funding_mode": "owner_funded",
                "provider": "openai",
                "model": "server-default",
                "show_usage": True,
            },
        },
    )

    assert response.status_code == 202, response.text
    replay = client.get(
        "/api/v1/sessions/session-a/events?after_sequence=0&limit=100",
        headers=auth_headers("user-a"),
    )
    assert replay.status_code == 200
    events = replay.json()["events"]
    assert response.json()["status"] == "completed", [
        event["payload"] for event in events if event["type"] == "error"
    ]
    usage_events = [event for event in events if event["type"] == "model.usage"]
    assert usage_events[0]["payload"]["input_tokens"] == 120
    assert response.json()["input_tokens"] == 120, [
        event["payload"] for event in usage_events
    ]
    assert [event["sequence"] for event in events] == list(
        range(1, len(events) + 1)
    )
    assert any(event["type"] == "model.usage" for event in events)
    assert any(event["type"] == "assistant.message.completed" for event in events)
    assert events[-1]["type"] == "turn.finished"
    assert model.calls == 1
