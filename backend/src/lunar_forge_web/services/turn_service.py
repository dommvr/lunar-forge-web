from collections.abc import AsyncIterator

from lunar_forge_web.core.adapter import AgentAdapter
from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import WorkerTurnRequest


class TurnService:
    def __init__(self, agent: AgentAdapter) -> None:
        self._agent = agent

    def run(self, request: WorkerTurnRequest) -> AsyncIterator[AgentEventContract]:
        return self._agent.run_turn(request)
