"""Process-local state used only by the deterministic fake service phase."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass, field

from lunar_forge_web.domain.models import (
    ApprovalResponse,
    ArtifactResponse,
    TurnResponse,
)


@dataclass(slots=True)
class InMemoryFakeFlowStore:
    turns: dict[str, TurnResponse] = field(default_factory=dict)
    active_turns: dict[str, str] = field(default_factory=dict)
    approvals: dict[str, ApprovalResponse] = field(default_factory=dict)
    artifacts: dict[str, list[ArtifactResponse]] = field(default_factory=dict)
    changed_sandboxes: set[str] = field(default_factory=set)
    lock: asyncio.Lock = field(default_factory=asyncio.Lock)

    def clear_sandbox(self, sandbox_id: str, session_ids: tuple[str, ...]) -> None:
        self.changed_sandboxes.discard(sandbox_id)
        for session_id in session_ids:
            turn_id = self.active_turns.pop(session_id, None)
            if turn_id is not None:
                self.turns.pop(turn_id, None)
            self.artifacts.pop(session_id, None)
        for approval_id, approval in tuple(self.approvals.items()):
            if approval.sandbox_id == sandbox_id:
                self.turns.pop(approval.turn_id, None)
                self.approvals.pop(approval_id, None)
