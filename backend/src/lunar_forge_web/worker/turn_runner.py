"""Collect one bounded turn from the configured agent adapter."""

import asyncio

from lunar_forge_web.core.adapter import AgentAdapter
from lunar_forge_web.domain.enums import TurnStatus
from lunar_forge_web.domain.models import WorkerTurnRequest, WorkerTurnResponse
from lunar_forge_web.security.limits import OWNER_FUNDED_TURN_TIMEOUT_SECONDS


class TurnRunner:
    def __init__(
        self,
        agent: AgentAdapter,
        max_events: int = 2_000,
        timeout_seconds: int = OWNER_FUNDED_TURN_TIMEOUT_SECONDS,
    ) -> None:
        self._agent = agent
        self._max_events = max_events
        self._timeout_seconds = timeout_seconds

    async def run(self, request: WorkerTurnRequest) -> WorkerTurnResponse:
        events = []
        async with asyncio.timeout(self._timeout_seconds):
            async for event in self._agent.run_turn(request):
                if len(events) >= self._max_events:
                    raise RuntimeError("Worker event limit was exceeded.")
                events.append(event)
        status = (
            TurnStatus.CANCELLED
            if any(event.type == "turn.cancelled" for event in events)
            else TurnStatus.COMPLETED
        )
        return WorkerTurnResponse(
            turn_id=request.turn_id,
            status=status,
            events=events,
        )
