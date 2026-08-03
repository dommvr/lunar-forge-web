import os
from pathlib import Path

import pytest

from lunar_forge_web.core.adapter import CoreAgentAdapter
from lunar_forge_web.domain.models import WorkerTurnRequest
from lunar_forge_web.storage.repositories import InMemoryEventRepository


@pytest.mark.live_model
@pytest.mark.skipif(
    os.getenv("LUNAR_FORGE_WEB_RUN_LIVE_MODEL_TESTS") != "1",
    reason=(
        "set LUNAR_FORGE_WEB_RUN_LIVE_MODEL_TESTS=1 and configure the core "
        "provider credentials to run the live model contract"
    ),
)
async def test_live_public_event_runner_is_opt_in(tmp_path: Path):
    adapter = CoreAgentAdapter(
        InMemoryEventRepository(),
        lambda _: tmp_path,
        runtime_mode="no-command",
    )
    request = WorkerTurnRequest(
        sandbox_id="sandbox-live",
        session_id="session-live",
        turn_id="turn-live",
        owner_id="user-live",
        message="Reply with exactly: live adapter ok. Do not use tools.",
    )

    events = [event async for event in adapter.run_turn(request)]

    assert any(event.type == "assistant.message.completed" for event in events)
    assert events[-1].type == "turn.finished"
