from collections.abc import AsyncIterator

from lunar_forge_web.core.adapter import CoreAgentAdapter
from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import WorkerTurnRequest


class TurnService:
    def __init__(self, agent: CoreAgentAdapter) -> None:
        self._agent = agent

    def run(self, request: WorkerTurnRequest) -> AsyncIterator[AgentEventContract]:
        return self._agent.run_turn(request)
