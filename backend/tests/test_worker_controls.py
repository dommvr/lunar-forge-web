import asyncio
from threading import Event

import lunar_forge.public_api as public_api
from lunar_forge import ModelResponse, ToolCall, load_config
from pydantic import SecretStr

from lunar_forge_web.core.adapter import CoreAgentAdapter
from lunar_forge_web.core.approvals import RedisApprovalBroker
from lunar_forge_web.core.runtime import HostedWorkspaceRuntime
from lunar_forge_web.domain.enums import TurnStatus
from lunar_forge_web.domain.models import (
    SessionSettings,
    TurnResponse,
    WorkerTurnRequest,
)
from lunar_forge_web.services.sandbox_service import runtime_sandbox
from lunar_forge_web.worker.turn_runner import TurnRunner


def _clean_public_config(monkeypatch, tmp_path) -> None:
    config = load_config(
        tmp_path,
        cli_overrides={
            "mcp": {"enabled": False},
            "plugins": {"enabled": False},
            "subagents": {"enabled": False},
        },
    )
    monkeypatch.setattr(public_api, "load_config", lambda *_args, **_kwargs: config)


async def _runtime(container, request):
    sandbox = await container.sandboxes.get(request.sandbox_id)
    assert sandbox is not None
    return HostedWorkspaceRuntime(
        container.runtime, runtime_sandbox(sandbox), asyncio.get_running_loop()
    )


async def _prepare_turn(container, turn_id: str) -> WorkerTurnRequest:
    settings = SessionSettings(
        funding_mode="byok",
        provider="openai",
        model="openai/test-model",
        show_usage=True,
    )
    await container.turns.create(
        TurnResponse(
            id=turn_id,
            session_id="session-a",
            owner_id="user-a",
            status=TurnStatus.QUEUED,
        ),
        sandbox_id="sandbox-a",
        prompt="Exercise the private worker control path.",
        settings=settings,
    )
    return WorkerTurnRequest(
        sandbox_id="sandbox-a",
        session_id="session-a",
        turn_id=turn_id,
        owner_id="user-a",
        message="Exercise the private worker control path.",
        settings=settings,
        provider_credential=SecretStr("sk-current-request-only"),
    )


def _runner(container, settings, agent) -> TurnRunner:
    return TurnRunner(
        agent,
        settings=settings,
        turns=container.turns,
        approvals=container.approvals,
        events=container.events,
        sessions=container.sessions,
        sandboxes=container.sandboxes,
        runtime=container.runtime,
        quotas=container.quotas,
        controls=container.controls,
        timeout_seconds=10,
        cleanup_margin_seconds=2,
    )


class ApprovalModel:
    def __init__(self) -> None:
        self.responses = [
            ModelResponse(
                text="",
                tool_calls=(
                    ToolCall(
                        "write-marker",
                        "write_file",
                        {"path": "marker.txt", "content": "approved\n"},
                    ),
                ),
            ),
            ModelResponse(text="The approved write completed."),
        ]

    def complete(self, messages, tools=None):
        del messages, tools
        return self.responses.pop(0)


async def test_worker_bridges_approval_control_and_finishes_in_order(
    container, settings, monkeypatch, tmp_path
):
    _clean_public_config(monkeypatch, tmp_path)
    request = await _prepare_turn(container, "turn-approval")
    agent = CoreAgentAdapter(
        container.events,
        runtime_resolver=lambda incoming: _runtime(container, incoming),
        model_client_resolver=lambda _: ApprovalModel(),
        approval_broker=RedisApprovalBroker(
            container.controls, timeout_seconds=5, poll_interval_seconds=0.01
        ),
    )
    task = asyncio.create_task(_runner(container, settings, agent).run(request))

    approval_id = None
    for _ in range(500):
        events = await container.events.replay("session-a", 0, 100)
        requested = [event for event in events if event.type == "permission.requested"]
        if requested:
            approval_id = requested[0].payload["request_id"]
            break
        await asyncio.sleep(0.01)
    assert isinstance(approval_id, str)
    for _ in range(100):
        if await container.approvals.get(approval_id) is not None:
            break
        await asyncio.sleep(0.01)
    stored = await container.approvals.resolve(approval_id, "user-a", True)
    await container.controls.publish_control(
        session_id="session-a",
        kind="approval",
        action_id=approval_id,
        payload={"approved": True, "reason": "Approved in integration test."},
    )

    response = await task
    events = await container.events.replay("session-a", 0, 100)
    assert stored.status == "approved"
    assert response.status == "completed"
    assert [event.sequence for event in events] == list(range(1, len(events) + 1))
    assert [event.type for event in events].count("permission.requested") == 1
    assert [event.type for event in events].count("permission.resolved") == 1
    sandbox = await container.sandboxes.get("sandbox-a")
    assert sandbox is not None
    content = await container.runtime.read_file(runtime_sandbox(sandbox), "marker.txt")
    assert content.content == "approved\n"


class BlockingCancellableModel:
    def __init__(self) -> None:
        self.started = Event()
        self.released = Event()

    def complete(self, messages, tools=None):
        del messages, tools
        self.started.set()
        self.released.wait(5)
        return ModelResponse(text="This result must be cancelled.")

    def cancel_active(self) -> bool:
        self.released.set()
        return True


async def test_worker_cancel_control_emits_confirmed_rollback_result(
    container, settings, monkeypatch, tmp_path
):
    _clean_public_config(monkeypatch, tmp_path)
    request = await _prepare_turn(container, "turn-cancel")
    model = BlockingCancellableModel()
    agent = CoreAgentAdapter(
        container.events,
        runtime_resolver=lambda incoming: _runtime(container, incoming),
        model_client_resolver=lambda _: model,
    )
    task = asyncio.create_task(_runner(container, settings, agent).run(request))
    assert await asyncio.to_thread(model.started.wait, 5)
    await container.controls.publish_control(
        session_id="session-a",
        kind="cancel",
        action_id="turn-cancel",
        payload={"rollback": True},
    )

    response = await task
    events = await container.events.replay("session-a", 0, 100)
    event_types = [event.type for event in events]
    assert response.status == "cancelled"
    assert "turn.cancelled" in event_types
    assert "rollback.started" in event_types
    rollback = next(event for event in events if event.type == "rollback.finished")
    assert rollback.payload["status"] == "completed"
    assert event_types[-1] == "turn.finished"
