"""Core agent protocol and deterministic transport-neutral fake."""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol

from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import WorkerTurnRequest


class CoreAgentAdapter(Protocol):
    def run_turn(self, request: WorkerTurnRequest) -> AsyncIterator[AgentEventContract]: ...
    async def cancel_turn(self, session_id: str, turn_id: str) -> bool: ...
    async def compact_session(self, session_id: str) -> bool: ...


class FakeCoreAgentAdapter:
    """Emit the core schema-v1 envelope without importing or running core."""

    def run_turn(self, request: WorkerTurnRequest) -> AsyncIterator[AgentEventContract]:
        return self._events(request)

    async def _events(self, request: WorkerTurnRequest) -> AsyncIterator[AgentEventContract]:
        event_types = (
            ("turn.started", {"source": "fake"}),
            ("status.updated", {"message": "Deterministic fake turn is running."}),
            (
                "assistant.message.completed",
                {"text": "Fake turn completed without calling a model.", "final": True},
            ),
            ("turn.finished", {"status": "completed"}),
        )
        for sequence, (event_type, payload) in enumerate(event_types, start=1):
            yield AgentEventContract(
                schema_version=1,
                event_id=f"evt_{request.turn_id}_{sequence}",
                session_id=request.session_id,
                turn_id=request.turn_id,
                sequence=sequence,
                timestamp=f"2026-01-01T00:00:0{sequence}Z",
                type=event_type,
                payload=payload,
            )

    async def cancel_turn(self, session_id: str, turn_id: str) -> bool:
        del session_id, turn_id
        return True

    async def compact_session(self, session_id: str) -> bool:
        del session_id
        return True
