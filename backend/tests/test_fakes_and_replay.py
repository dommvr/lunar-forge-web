import pytest

from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import WorkerTurnRequest
from lunar_forge_web.runtime.fake import FakeRuntimeProvider
from lunar_forge_web.storage.repositories import (
    InMemoryEventRepository,
    RepositoryConflictError,
)


def event(sequence: int) -> AgentEventContract:
    return AgentEventContract(
        schema_version=1,
        event_id=f"evt-{sequence}",
        session_id="session-a",
        turn_id="turn-a",
        sequence=sequence,
        timestamp=f"2026-01-01T00:00:0{sequence}Z",
        type="status.updated",
        payload={"message": f"step {sequence}"},
    )


async def test_in_memory_event_replay_is_ordered_bounded_and_monotonic():
    repository = InMemoryEventRepository()
    await repository.append(event(1))
    await repository.append(event(2))
    await repository.append(event(3))

    replay = await repository.replay("session-a", after_sequence=1, limit=1)
    assert [item.sequence for item in replay] == [2]

    with pytest.raises(RepositoryConflictError, match="Expected event sequence 4"):
        await repository.append(event(5))


async def test_fake_runtime_and_agent_are_offline_and_deterministic(container):
    runtime = FakeRuntimeProvider()
    capability = runtime.capability()
    sandbox = await runtime.create(
        owner_id="user-a",
        sandbox_id="sandbox-a",
        template_id="python-cli",
    )

    request = WorkerTurnRequest(
        sandbox_id="sandbox-a",
        session_id="session-a",
        turn_id="turn-a",
        owner_id="user-a",
        message="Make a deterministic change.",
    )
    events = [item async for item in container.agent.run_turn(request)]

    assert capability.network_policy == "offline"
    assert capability.supports_preview is False
    assert sandbox.reference == "runtime_sandbox-a"
    assert [item.sequence for item in events] == [1, 2, 3, 4]
    assert await container.agent.cancel_turn("session-a", "turn-a") is True
    assert await container.agent.compact_session("session-a") is True
