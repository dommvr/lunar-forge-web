import asyncio
import json
from collections.abc import Iterator
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any

import pytest
from lunar_forge import (
    AgentEvent,
    AgentRequest,
    ApprovalDecision,
    ApprovalRequest,
)

from lunar_forge_web.core.adapter import CoreAdapterError, CoreAgentAdapter
from lunar_forge_web.core.approvals import ApprovalContext, RedisApprovalBroker
from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import SessionSettings, WorkerTurnRequest
from lunar_forge_web.storage.redis import ControlMessage, UpstashRedisStore
from lunar_forge_web.storage.repositories import InMemoryEventRepository


def worker_request(**settings: Any) -> WorkerTurnRequest:
    return WorkerTurnRequest(
        sandbox_id="sandbox-core",
        session_id="session-core",
        turn_id="turn-core",
        owner_id="user-core",
        message="Inspect this project safely.",
        settings=SessionSettings(**settings),
    )


def core_event(
    sequence: int,
    event_type: str,
    payload: dict[str, Any],
    *,
    event_id: str | None = None,
    parent_event_id: str | None = None,
) -> AgentEvent:
    return AgentEvent(
        schema_version=1,
        event_id=event_id or f"evt_core_{sequence}",
        session_id="session-from-core",
        turn_id="turn-from-core",
        sequence=sequence,
        timestamp=f"2026-08-03T12:00:{sequence:02d}Z",
        type=event_type,
        payload=payload,
        parent_event_id=parent_event_id,
    )


async def collect(adapter: CoreAgentAdapter, request: WorkerTurnRequest):
    return [event async for event in adapter.run_turn(request)]


async def test_constructs_public_request_and_maps_full_fake_model_lifecycle(
    tmp_path: Path,
):
    repository = InMemoryEventRepository()
    await repository.append(
        AgentEventContract(
            event_id="evt_existing",
            session_id="session-core",
            turn_id="turn-earlier",
            sequence=1,
            timestamp="2026-08-03T11:59:59Z",
            type="turn.finished",
            payload={"status": "completed"},
        )
    )
    observed: dict[str, Any] = {}

    def fake_model_events(
        request: AgentRequest,
        *,
        approval_provider: Any,
    ) -> Iterator[AgentEvent]:
        observed["request"] = request
        observed["approval_provider"] = approval_provider
        yield core_event(1, "turn.started", {"status": "running"})
        yield core_event(
            2,
            "tool.started",
            {"tool_name": "read_file", "args_preview": {"path": "README.md"}},
        )
        yield core_event(
            3,
            "tool.finished",
            {"tool_name": "read_file", "ok": True},
        )
        yield core_event(4, "validation.started", {"command": "pytest -q"})
        yield core_event(5, "validation.finished", {"ok": True})
        yield core_event(
            6,
            "assistant.message.completed",
            {"text": "Inspection complete.", "final": True},
        )
        yield core_event(7, "turn.finished", {"status": "completed"})

    adapter = CoreAgentAdapter(
        repository,
        lambda _: tmp_path,
        event_runner=fake_model_events,
    )
    request = worker_request(
        reasoning_effort="high",
        plan_mode=True,
        show_usage=False,
        model="gpt-test",
    )
    events = await collect(adapter, request)

    public_request = observed["request"]
    assert isinstance(public_request, AgentRequest)
    assert public_request.project_root == tmp_path.resolve()
    assert public_request.message == request.message
    assert public_request.runtime_mode == "local"
    assert public_request.permission_mode == "plan"
    assert public_request.allow_network is False
    assert public_request.model == "gpt-test"
    assert public_request.reasoning_effort == "high"
    assert public_request.show_usage is False
    assert [event.sequence for event in events] == list(range(2, 9))
    assert [event.type for event in events] == [
        "turn.started",
        "tool.started",
        "tool.finished",
        "validation.started",
        "validation.finished",
        "assistant.message.completed",
        "turn.finished",
    ]
    assert all(event.session_id == request.session_id for event in events)
    assert all(event.turn_id == request.turn_id for event in events)
    assert events[0].event_id == "evt_core_1"
    replay = await repository.replay("session-core", after_sequence=1, limit=20)
    assert tuple(events) == replay


class ApproveBroker:
    def __init__(self) -> None:
        self.requests: list[tuple[ApprovalRequest, ApprovalContext]] = []

    async def decide(
        self,
        request: ApprovalRequest,
        context: ApprovalContext,
    ) -> ApprovalDecision:
        self.requests.append((request, context))
        return ApprovalDecision.create(
            request.id,
            approved=True,
            reason="Approved by the deterministic fake web client.",
            source="textual",
        )


async def test_bridges_approval_and_suppresses_duplicate_core_events(tmp_path: Path):
    repository = InMemoryEventRepository()
    broker = ApproveBroker()
    observed: dict[str, Any] = {}

    def fake_model_events(
        request: AgentRequest,
        *,
        approval_provider: Any,
    ) -> Iterator[AgentEvent]:
        del request
        approval = ApprovalRequest.create(
            kind="write",
            title="Write file",
            summary="Create a bounded marker file.",
            details="Create marker.txt.",
            risk="low",
            mode="local",
            file_path="marker.txt",
            metadata={"api_key": "sk-adapter-secret-12345678"},
        )
        decision = approval_provider.request_approval(approval)
        observed["approval"] = approval
        observed["decision"] = decision
        yield core_event(1, "permission.requested", approval.to_dict())
        yield core_event(
            2,
            "permission.resolved",
            decision.to_dict(),
            parent_event_id="evt_core_1",
        )
        yield core_event(
            3,
            "assistant.message.completed",
            {"text": "The approved write completed.", "final": True},
        )

    adapter = CoreAgentAdapter(
        repository,
        lambda _: tmp_path,
        approval_broker=broker,
        event_runner=fake_model_events,
        approval_wait_timeout_seconds=5,
    )
    events = await collect(adapter, worker_request())

    assert [event.type for event in events] == [
        "permission.requested",
        "permission.resolved",
        "assistant.message.completed",
    ]
    requested, resolved = events[:2]
    assert requested.payload["request_id"] == observed["approval"].id
    assert requested.payload["metadata"]["api_key"] == "[REDACTED]"
    assert resolved.payload["approved"] is True
    assert resolved.parent_event_id == requested.event_id
    assert observed["decision"].request_id == observed["approval"].id
    assert broker.requests[0][1].session_id == "session-core"


class ApprovalControlFixture:
    def __init__(self, request_id: str) -> None:
        self.request_id = request_id

    async def replay_controls(
        self,
        session_id: str,
        after_id: str = "0-0",
        limit: int = 100,
    ) -> tuple[ControlMessage, ...]:
        del session_id, limit
        if after_id != "0-0":
            return ()
        return (
            ControlMessage(
                id="1-0",
                kind="approval",
                action_id=self.request_id,
                payload={"approved": True, "reason": "Approved in Redis."},
                created_at=datetime.now(timezone.utc),
            ),
        )


async def test_redis_approval_broker_maps_control_to_public_decision():
    request = ApprovalRequest.create(
        kind="command",
        title="Run validation",
        summary="Run a bounded validation command.",
        details="Run pytest -q.",
        risk="medium",
        mode="local",
        command="pytest -q",
    )
    broker = RedisApprovalBroker(
        ApprovalControlFixture(request.id),
        timeout_seconds=1,
        poll_interval_seconds=0.01,
    )

    decision = await broker.decide(
        request,
        ApprovalContext(
            session_id="session-core",
            turn_id="turn-core",
            owner_id="user-core",
            cancellation_requested=Event(),
        ),
    )

    assert decision.request_id == request.id
    assert decision.approved is True
    assert decision.reason == "Approved in Redis."
    assert decision.source == "textual"


async def test_cancellation_is_cooperative_and_does_not_claim_rollback(
    tmp_path: Path,
):
    repository = InMemoryEventRepository()
    release_second_event = Event()

    def blocking_fake_model(
        request: AgentRequest,
        *,
        approval_provider: Any,
    ) -> Iterator[AgentEvent]:
        del request, approval_provider
        yield core_event(1, "turn.started", {"status": "running"})
        assert release_second_event.wait(timeout=5)
        yield core_event(2, "status.updated", {"message": "late result"})

    adapter = CoreAgentAdapter(
        repository,
        lambda _: tmp_path,
        event_runner=blocking_fake_model,
    )
    task = asyncio.create_task(collect(adapter, worker_request()))
    while await repository.last_sequence("session-core") < 1:
        await asyncio.sleep(0.01)

    assert await adapter.cancel_turn("session-core", "turn-core") is True
    release_second_event.set()
    events = await task

    assert [event.type for event in events] == ["turn.started", "turn.cancelled"]
    assert events[-1].payload["rollback_status"] == "unavailable"
    assert not any(event.type == "rollback.finished" for event in events)
    assert await adapter.cancel_turn("session-core", "turn-core") is False


async def test_forwards_confirmed_rollback_and_automatic_compaction_events(
    tmp_path: Path,
):
    repository = InMemoryEventRepository()

    def fake_model_events(
        request: AgentRequest,
        *,
        approval_provider: Any,
    ) -> Iterator[AgentEvent]:
        del request, approval_provider
        yield core_event(1, "memory.compaction.started", {"status": "running"})
        yield core_event(2, "memory.compaction.finished", {"status": "completed"})
        yield core_event(3, "rollback.started", {"reason": "cancelled"})
        yield core_event(
            4,
            "rollback.finished",
            {
                "status": "completed",
                "restored_files": ["app.py"],
                "removed_files": ["generated.py"],
                "skipped_files": [],
                "errors": [],
            },
            parent_event_id="evt_core_3",
        )

    adapter = CoreAgentAdapter(
        repository,
        lambda _: tmp_path,
        event_runner=fake_model_events,
    )
    events = await collect(adapter, worker_request())

    assert events[-1].type == "rollback.finished"
    assert events[-1].payload["restored_files"] == ["app.py"]
    assert events[-1].parent_event_id == "evt_core_3"
    assert await adapter.compact_session("session-core") is False


async def test_publishes_bounded_redacted_error_then_maps_public_exception(
    tmp_path: Path,
):
    repository = InMemoryEventRepository()

    def failing_fake_model(
        request: AgentRequest,
        *,
        approval_provider: Any,
    ) -> Iterator[AgentEvent]:
        del request, approval_provider
        yield core_event(1, "turn.started", {"status": "running"})
        raise ValueError("api_key=sk-adapter-secret-12345678 invalid")

    adapter = CoreAgentAdapter(
        repository,
        lambda _: tmp_path,
        event_runner=failing_fake_model,
    )
    yielded: list[AgentEventContract] = []

    with pytest.raises(CoreAdapterError) as raised:
        async for event in adapter.run_turn(worker_request()):
            yielded.append(event)

    assert raised.value.code == "core_request_invalid"
    assert "sk-adapter-secret-12345678" not in raised.value.message
    assert [event.type for event in yielded] == ["turn.started", "error"]
    assert yielded[-1].payload["code"] == "core_request_invalid"
    serialized = json.dumps(yielded[-1].payload)
    assert "sk-adapter-secret-12345678" not in serialized
    assert len(serialized) <= 100_000


async def test_maps_invalid_project_without_invoking_runner(tmp_path: Path):
    missing = tmp_path / "missing"
    adapter = CoreAgentAdapter(
        InMemoryEventRepository(),
        lambda _: missing,
        event_runner=lambda *_args, **_kwargs: iter(()),
    )

    with pytest.raises(CoreAdapterError) as raised:
        await adapter.construct_request(worker_request())

    assert raised.value.code == "core_project_unavailable"


class MinimalRedisClient:
    def __init__(self) -> None:
        self.sequence = 0
        self.rows: list[tuple[str, dict[str, str]]] = []

    async def get(self, key: str) -> str | None:
        del key
        return str(self.sequence) if self.sequence else None

    async def eval(self, script: str, numkeys: int, *values: Any) -> int:
        del script, numkeys
        incoming = int(values[2])
        assert incoming == self.sequence + 1
        self.sequence = incoming
        self.rows.append((f"{incoming}-0", {"event": values[3]}))
        return incoming

    async def xrange(
        self, name: str, min: str, max: str, count: int
    ) -> list[tuple[str, dict[str, str]]]:
        del name, max
        after = int(min.removeprefix("(").split("-", 1)[0])
        return [row for row in self.rows if int(row[0].split("-", 1)[0]) > after][
            :count
        ]


async def test_production_redis_event_repository_contract(tmp_path: Path):
    client = MinimalRedisClient()
    redis = UpstashRedisStore(
        client,  # type: ignore[arg-type]
        key_prefix="lfw:test",
        event_ttl_seconds=1_800,
        control_ttl_seconds=900,
    )

    def fake_model_events(
        request: AgentRequest,
        *,
        approval_provider: Any,
    ) -> Iterator[AgentEvent]:
        del request, approval_provider
        yield core_event(1, "turn.started", {"status": "running"})
        yield core_event(2, "turn.finished", {"status": "completed"})

    adapter = CoreAgentAdapter(
        redis,
        lambda _: tmp_path,
        event_runner=fake_model_events,
    )
    events = await collect(adapter, worker_request())
    replay = await redis.replay("session-core", after_sequence=0, limit=20)

    assert [event.sequence for event in events] == [1, 2]
    assert replay == tuple(events)
