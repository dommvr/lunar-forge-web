"""Collect one bounded fake turn from the CoreAgentAdapter protocol."""

from lunar_forge_web.core.adapter import CoreAgentAdapter
from lunar_forge_web.domain.enums import TurnStatus
from lunar_forge_web.domain.models import WorkerTurnRequest, WorkerTurnResponse


class TurnRunner:
    def __init__(self, agent: CoreAgentAdapter, max_events: int = 2_000) -> None:
        self._agent = agent
        self._max_events = max_events

    async def run(self, request: WorkerTurnRequest) -> WorkerTurnResponse:
        events = []
        async for event in self._agent.run_turn(request):
            if len(events) >= self._max_events:
                raise RuntimeError("Worker event limit was exceeded.")
            events.append(event)
        return WorkerTurnResponse(
            turn_id=request.turn_id,
            status=TurnStatus.COMPLETED,
            events=events,
        )
