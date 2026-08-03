"""Deterministic fake vertical slice using the production-shaped contracts."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from uuid import uuid4

from lunar_forge_web.domain.enums import (
    ApprovalStatus,
    SandboxStatus,
    TurnStatus,
)
from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import (
    ApprovalResponse,
    ArtifactResponse,
    ArtifactsResponse,
    CancelResponse,
    CompactionResponse,
    EventReplayResponse,
    FileEntry,
    FileContentResponse,
    FilesResponse,
    SandboxResponse,
    SessionResponse,
    TurnCreateRequest,
    TurnResponse,
)
from lunar_forge_web.storage.fake_state import InMemoryFakeFlowStore
from lunar_forge_web.storage.repositories import EventRepository, SessionRepository


class FakeFlowStateError(ValueError):
    pass


class FakeFlowNotFoundError(LookupError):
    pass


class FakeFlowService:
    def __init__(
        self,
        store: InMemoryFakeFlowStore,
        events: EventRepository,
        sessions: SessionRepository,
    ) -> None:
        self._store = store
        self._events = events
        self._sessions = sessions

    async def session_started(self, session: SessionResponse) -> None:
        await self._emit(
            session,
            "session-bootstrap",
            "session.started",
            {
                "runtime_provider": "fake",
                "workspace": "/workspace/sample-app",
                "status": "ready",
            },
        )

    async def submit_turn(
        self,
        session: SessionResponse,
        sandbox: SandboxResponse,
        body: TurnCreateRequest,
        turn_id: str | None = None,
    ) -> TurnResponse:
        async with self._store.lock:
            active_id = self._store.active_turns.get(session.id)
            if active_id is not None:
                active = self._store.turns.get(active_id)
                if active is not None and active.status in {
                    TurnStatus.RUNNING.value,
                    TurnStatus.WAITING_FOR_APPROVAL.value,
                }:
                    raise FakeFlowStateError("A turn is already active.")

            now = datetime.now(timezone.utc)
            turn = TurnResponse(
                id=turn_id or f"turn_{uuid4().hex}",
                session_id=session.id,
                owner_id=session.owner_id,
                status=TurnStatus.RUNNING,
                created_at=now,
                started_at=now,
            )
            self._store.turns[turn.id] = turn
            self._store.active_turns[session.id] = turn.id
            self._store.changed_sandboxes.add(sandbox.id)

            await self._emit(session, turn.id, "turn.started", {"source": "fake"})
            await self._emit(
                session,
                turn.id,
                "status.updated",
                {"message": "Inspecting project · 12 files matched · reading AGENTS.md"},
            )
            await self._emit(
                session,
                turn.id,
                "tool.started",
                {"tool_name": "read_file", "path": "AGENTS.md", "kind": "read"},
            )
            await self._emit(
                session,
                turn.id,
                "tool.finished",
                {"tool_name": "read_file", "path": "AGENTS.md", "status": "ok"},
            )
            await self._emit(
                session,
                turn.id,
                "tool.started",
                {
                    "tool_name": "apply_patch",
                    "path": "components/Pricing.tsx",
                    "kind": "edit",
                },
            )
            await self._emit(
                session,
                turn.id,
                "tool.finished",
                {
                    "tool_name": "apply_patch",
                    "path": "components/Pricing.tsx",
                    "status": "ok",
                    "changed_files": [
                        "components/Pricing.tsx",
                        "app/page.tsx",
                        "package.json",
                    ],
                },
            )
            await self._emit(
                session,
                turn.id,
                "assistant.message.completed",
                {
                    "text": (
                        "I read AGENTS.md and the marketing route, added a three-tier "
                        "pricing section with a mobile stack, and wired it into the page. "
                        "Next I need to run the project's validation command."
                    ),
                    "final": False,
                },
            )
            await self._emit(
                session,
                turn.id,
                "tool.started",
                {
                    "tool_name": "run_command",
                    "command": "npm run validate",
                    "kind": "run",
                },
            )
            approval = ApprovalResponse(
                id=f"approval_{uuid4().hex}",
                sandbox_id=sandbox.id,
                session_id=session.id,
                turn_id=turn.id,
                owner_id=session.owner_id,
                kind="command.run",
                title="Run command in sandbox",
                summary="Run the project's validation command without network access.",
                details=(
                    "npm run validate -- --reporter=json --max-warnings=0 "
                    "--project /workspace/sample-app"
                ),
                risk="medium",
                expires_at=now + timedelta(minutes=15),
            )
            self._store.approvals[approval.id] = approval
            await self._emit(
                session,
                turn.id,
                "permission.requested",
                {
                    "request_id": approval.id,
                    "id": approval.id,
                    "permission": approval.kind,
                    "description": approval.summary,
                    "details": approval.details,
                    "risk": approval.risk,
                },
            )
            waiting = turn.model_copy(update={"status": TurnStatus.WAITING_FOR_APPROVAL})
            self._store.turns[turn.id] = waiting
            return waiting

    async def resolve_approval(
        self,
        session: SessionResponse,
        approval_id: str,
        approved: bool,
    ) -> ApprovalResponse:
        async with self._store.lock:
            approval = self._store.approvals.get(approval_id)
            if approval is None or approval.session_id != session.id:
                raise FakeFlowNotFoundError("Approval was not found.")
            if approval.status != ApprovalStatus.PENDING.value:
                raise FakeFlowStateError("Approval was already resolved.")
            resolved = approval.model_copy(
                update={
                    "status": (
                        ApprovalStatus.APPROVED
                        if approved
                        else ApprovalStatus.DENIED
                    )
                }
            )
            self._store.approvals[approval_id] = resolved
            await self._emit(
                session,
                approval.turn_id,
                "permission.resolved",
                {
                    "request_id": approval.id,
                    "approved": approved,
                    "allowed": approved,
                },
            )
            turn = self._store.turns[approval.turn_id]
            if not approved:
                cancelled = turn.model_copy(
                    update={
                        "status": TurnStatus.CANCELLED,
                        "finished_at": datetime.now(timezone.utc),
                    }
                )
                self._store.turns[turn.id] = cancelled
                self._store.active_turns.pop(session.id, None)
                await self._emit(
                    session,
                    turn.id,
                    "assistant.message.completed",
                    {
                        "text": (
                            "Denied. Nothing was executed; the three file edits are "
                            "kept so you can review them."
                        ),
                        "final": True,
                    },
                )
                await self._emit(
                    session,
                    turn.id,
                    "turn.cancelled",
                    {"status": "cancelled", "reason": "Approval denied."},
                )
                return resolved

            await self._emit(
                session,
                turn.id,
                "validation.started",
                {"command": "npm run validate", "step_count": 5},
            )
            await self._emit(
                session,
                turn.id,
                "status.updated",
                {"message": "Running validation · step 4 of 5"},
            )
            await self._emit(
                session,
                turn.id,
                "validation.finished",
                {
                    "status": "passed",
                    "steps": ["typecheck", "lint", "unit tests", "build", "browser check"],
                },
            )
            artifact = ArtifactResponse(
                id=f"artifact_{uuid4().hex}",
                sandbox_id=approval.sandbox_id,
                session_id=session.id,
                owner_id=session.owner_id,
                name="validation-report.json",
                media_type="application/json",
                size_bytes=4_198,
                expires_at=datetime.now(timezone.utc) + timedelta(minutes=30),
            )
            self._store.artifacts.setdefault(session.id, []).append(artifact)
            await self._emit(
                session,
                turn.id,
                "assistant.message.completed",
                {"text": "Edited 3 files. Validation passed in 41s.", "final": True},
            )
            await self._emit(
                session,
                turn.id,
                "turn.finished",
                {
                    "status": "completed",
                    "changed_files": [
                        "components/Pricing.tsx",
                        "app/page.tsx",
                        "package.json",
                    ],
                },
            )
            completed = turn.model_copy(
                update={
                    "status": TurnStatus.COMPLETED,
                    "finished_at": datetime.now(timezone.utc),
                }
            )
            self._store.turns[turn.id] = completed
            self._store.active_turns.pop(session.id, None)
            return resolved

    async def cancel(self, session: SessionResponse) -> CancelResponse:
        async with self._store.lock:
            turn_id = self._store.active_turns.get(session.id)
            if turn_id is None:
                raise FakeFlowStateError("No active turn can be cancelled.")
            turn = self._store.turns[turn_id]
            cancelled_event = await self._emit(
                session,
                turn.id,
                "turn.cancelled",
                {
                    "status": "cancelled",
                    "reason": "User requested cancellation.",
                    "active_tool_count": 0,
                    "pending_approval_count": 1,
                },
            )
            rollback_started = await self._emit(
                session,
                turn.id,
                "rollback.started",
                {
                    "reason": "Revoking current-turn changes after cancellation.",
                    "tracked_file_count": 3,
                },
                parent_event_id=cancelled_event.event_id,
            )
            report = (
                "Pricing.tsx removed; app/page.tsx and package.json restored."
            )
            await self._emit(
                session,
                turn.id,
                "rollback.finished",
                {
                    "status": "completed",
                    "restored_files": ["app/page.tsx", "package.json"],
                    "removed_files": ["components/Pricing.tsx"],
                    "skipped_files": [],
                    "errors": [],
                },
                parent_event_id=rollback_started.event_id,
            )
            cancelled = turn.model_copy(
                update={
                    "status": TurnStatus.CANCELLED,
                    "finished_at": datetime.now(timezone.utc),
                }
            )
            self._store.turns[turn.id] = cancelled
            self._store.active_turns.pop(session.id, None)
            self._store.changed_sandboxes.discard(
                next(
                    (
                        item.sandbox_id
                        for item in self._store.approvals.values()
                        if item.turn_id == turn.id
                    ),
                    "",
                )
            )
            return CancelResponse(turn=cancelled, rollback_report=report)

    async def compact(self, session: SessionResponse) -> CompactionResponse:
        async with self._store.lock:
            if session.id in self._store.active_turns:
                raise FakeFlowStateError("Compaction is deferred during an active turn.")
            turn_id = f"compaction_{uuid4().hex}"
            started = await self._emit(
                session,
                turn_id,
                "memory.compaction.started",
                {"trigger": "manual", "messages_before": 8},
            )
            await self._emit(
                session,
                turn_id,
                "memory.compaction.finished",
                {
                    "status": "completed",
                    "summary_path": ".agent/sessions/fake-summary.md",
                    "messages_before": 8,
                    "messages_after": 3,
                    "trigger": "manual",
                },
                parent_event_id=started.event_id,
            )
            updated = session.model_copy(
                update={
                    "compacted_summary_count": session.compacted_summary_count + 1,
                    "last_sequence": await self._events.last_sequence(session.id),
                }
            )
            await self._sessions.put(updated)
            return CompactionResponse(
                session=updated,
                compacted=True,
                summary="Older context compacted into a safe public summary.",
            )

    async def replay(
        self,
        session: SessionResponse,
        after_sequence: int,
        limit: int,
    ) -> EventReplayResponse:
        events = await self._events.replay(session.id, after_sequence, limit)
        last = await self._events.last_sequence(session.id)
        return EventReplayResponse(
            session_id=session.id,
            after_sequence=after_sequence,
            last_sequence=last,
            has_more=bool(events and events[-1].sequence < last),
            events=list(events),
        )

    def files(self, sandbox: SandboxResponse) -> FilesResponse:
        changed = sandbox.id in self._store.changed_sandboxes
        base = [
            FileEntry(path="AGENTS.md", kind="file", size_bytes=1_024),
            FileEntry(path="README.md", kind="file", size_bytes=2_048),
            FileEntry(path="app", kind="directory"),
            FileEntry(path="app/page.tsx", kind="file", size_bytes=6_200),
            FileEntry(path="components", kind="directory"),
            FileEntry(path="components/Hero.tsx", kind="file", size_bytes=2_400),
            FileEntry(path="package.json", kind="file", size_bytes=890),
        ]
        if changed:
            base.append(
                FileEntry(
                    path="components/Pricing.tsx",
                    kind="file",
                    size_bytes=2_980,
                )
            )
        return FilesResponse(sandbox_id=sandbox.id, items=base)

    def file_content(self, sandbox: SandboxResponse, path: str) -> FileContentResponse:
        known = {item.path for item in self.files(sandbox).items if item.kind == "file"}
        if path not in known:
            raise FakeFlowNotFoundError("File was not found.")
        content = {
            "components/Pricing.tsx": (
                "export function Pricing() {\n"
                "  return <section className=\"pricing\">Pricing</section>;\n"
                "}\n"
            ),
            "AGENTS.md": "# Sample project instructions\n",
            "README.md": "# Sample app\n",
        }.get(path, f"// Deterministic fake content for {path}\n")
        return FileContentResponse(
            sandbox_id=sandbox.id,
            path=path,
            content=content,
        )

    def artifacts(self, session: SessionResponse) -> ArtifactsResponse:
        return ArtifactsResponse(items=list(self._store.artifacts.get(session.id, [])))

    async def clear_sandbox(self, sandbox_id: str) -> None:
        sessions = await self._sessions.list_for_sandbox(sandbox_id)
        session_ids = tuple(session.id for session in sessions)
        async with self._store.lock:
            self._store.clear_sandbox(sandbox_id, session_ids)
        for session_id in session_ids:
            await self._events.clear_session(session_id)
        await self._sessions.delete_for_sandbox(sandbox_id)

    async def _emit(
        self,
        session: SessionResponse,
        turn_id: str,
        event_type: str,
        payload: dict[str, object],
        *,
        parent_event_id: str | None = None,
    ) -> AgentEventContract:
        sequence = await self._events.last_sequence(session.id) + 1
        event = AgentEventContract(
            event_id=f"evt_{uuid4().hex}",
            session_id=session.id,
            turn_id=turn_id,
            sequence=sequence,
            timestamp=datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
            type=event_type,
            payload=payload,
            parent_event_id=parent_event_id,
        )
        await self._events.append(event)
        current_session = await self._sessions.get(session.id)
        if current_session is not None and sequence > current_session.last_sequence:
            await self._sessions.put(
                current_session.model_copy(update={"last_sequence": sequence})
            )
        return event
