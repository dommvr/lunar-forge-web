"""Execute one owned turn and persist bounded terminal metadata."""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone
from lunar_forge_web.config import Settings
from lunar_forge_web.core.adapter import AgentAdapter, CoreAdapterError
from lunar_forge_web.core.approvals import ApprovalControlStore
from lunar_forge_web.domain.enums import FundingMode, TurnStatus
from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import (
    ApprovalResponse,
    WorkerTurnRequest,
    WorkerTurnResponse,
)
from lunar_forge_web.runtime.base import RuntimeProvider
from lunar_forge_web.security.limits import OWNER_FUNDED_TURN_TIMEOUT_SECONDS
from lunar_forge_web.services.sandbox_service import (
    MeaningfulActivity,
    SandboxService,
    runtime_sandbox,
)
from lunar_forge_web.services.usage_service import UsageService
from lunar_forge_web.storage.repositories import (
    ApprovalRepository,
    EventRepository,
    QuotaRepository,
    SandboxRepository,
    SessionRepository,
    TurnRepository,
)


class TurnRunnerError(RuntimeError):
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


class TurnRunner:
    def __init__(
        self,
        agent: AgentAdapter,
        *,
        settings: Settings,
        turns: TurnRepository,
        approvals: ApprovalRepository,
        events: EventRepository,
        sessions: SessionRepository,
        sandboxes: SandboxRepository,
        runtime: RuntimeProvider,
        quotas: QuotaRepository,
        controls: ApprovalControlStore,
        max_events: int = 2_000,
        timeout_seconds: int = OWNER_FUNDED_TURN_TIMEOUT_SECONDS,
        cleanup_margin_seconds: int = 45,
    ) -> None:
        self._agent = agent
        self._settings = settings
        self._turns = turns
        self._approvals = approvals
        self._events = events
        self._sessions = sessions
        self._sandboxes = sandboxes
        self._runtime = runtime
        self._quotas = quotas
        self._controls = controls
        self._max_events = max_events
        self._timeout_seconds = timeout_seconds
        self._cleanup_margin_seconds = cleanup_margin_seconds

    async def run(self, request: WorkerTurnRequest) -> WorkerTurnResponse:
        sandbox = await self._sandboxes.get(request.sandbox_id)
        session = await self._sessions.get(request.session_id)
        turn = await self._turns.get(request.turn_id)
        if (
            sandbox is None
            or session is None
            or turn is None
            or sandbox.owner_id != request.owner_id
            or session.owner_id != request.owner_id
            or turn.turn.owner_id != request.owner_id
            or session.sandbox_id != sandbox.id
            or turn.sandbox_id != sandbox.id
            or turn.turn.session_id != session.id
        ):
            raise TurnRunnerError(
                "worker_ownership_mismatch",
                "The turn does not match an owned active sandbox.",
            )
        await self._runtime.connect(runtime_sandbox(sandbox))
        await self._turns.mark_running(request.turn_id, datetime.now(timezone.utc))

        observed = 0
        input_tokens = 0
        output_tokens = 0
        terminal_status = TurnStatus.COMPLETED
        error_code: str | None = None
        finished = asyncio.Event()

        async def consume() -> None:
            nonlocal observed, input_tokens, output_tokens, terminal_status, error_code
            last_activity_extension = 0.0
            async for event in self._agent.run_turn(request):
                await self._ensure_event_persisted(event)
                observed += 1
                if observed > self._max_events:
                    raise TurnRunnerError(
                        "worker_event_limit", "The worker event limit was exceeded."
                    )
                await self._record_approval(request, event)
                if event.type == "model.usage":
                    input_tokens += _bounded_usage(event.payload.get("input_tokens"))
                    output_tokens += _bounded_usage(event.payload.get("output_tokens"))
                elif event.type == "turn.cancelled":
                    terminal_status = TurnStatus.CANCELLED
                elif event.type == "turn.finished":
                    status = event.payload.get("status")
                    if status == "cancelled":
                        terminal_status = TurnStatus.CANCELLED
                    elif status == "failed":
                        terminal_status = TurnStatus.FAILED
                elif event.type == "error":
                    terminal_status = TurnStatus.FAILED
                    value = event.payload.get("code")
                    error_code = str(value)[:200] if value else "core_execution_failed"
                if event.type in {
                    "status.updated",
                    "model.call.started",
                    "tool.started",
                    "validation.started",
                }:
                    now = asyncio.get_running_loop().time()
                    if now - last_activity_extension >= 60:
                        await SandboxService(
                            self._sandboxes, self._runtime
                        ).record_activity(
                            sandbox.id, MeaningfulActivity.AGENT_PROGRESS
                        )
                        last_activity_extension = now

        execution = asyncio.create_task(consume())
        control = asyncio.create_task(
            self._listen_for_cancel(request, finished)
        )
        try:
            try:
                await asyncio.wait_for(
                    asyncio.shield(execution), timeout=self._timeout_seconds
                )
            except TimeoutError:
                error_code = "turn_timeout"
                await self._agent.cancel_turn(request.session_id, request.turn_id)
                try:
                    await asyncio.wait_for(
                        execution, timeout=self._cleanup_margin_seconds
                    )
                except TimeoutError:
                    execution.cancel()
                    await asyncio.gather(execution, return_exceptions=True)
                    terminal_status = TurnStatus.FAILED
                else:
                    terminal_status = TurnStatus.CANCELLED
            except CoreAdapterError as exc:
                terminal_status = TurnStatus.FAILED
                error_code = exc.code
            except TurnRunnerError as exc:
                terminal_status = TurnStatus.FAILED
                error_code = exc.code
            except Exception:
                terminal_status = TurnStatus.FAILED
                error_code = "worker_execution_failed"
        finally:
            finished.set()
            control.cancel()
            await asyncio.gather(control, return_exceptions=True)

        owner_funded = (
            str(request.settings.funding_mode) == FundingMode.OWNER_FUNDED.value
        )
        estimated_cost = (
            self._estimated_cost(input_tokens, output_tokens) if owner_funded else 0
        )
        finished_at = datetime.now(timezone.utc)
        terminal = await self._turns.finish(
            request.turn_id,
            status=terminal_status,
            finished_at=finished_at,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_microusd=estimated_cost,
            error_code=error_code,
        )
        if owner_funded:
            try:
                await UsageService(self._quotas).settle(
                    turn_id=request.turn_id,
                    actual_cost_microusd=estimated_cost,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    sandbox_id=request.sandbox_id,
                    model=self._settings.owner_funded_model,
                )
            except Exception:
                if terminal_status is TurnStatus.COMPLETED:
                    terminal_status = TurnStatus.FAILED
                    error_code = "usage_settlement_failed"
                    terminal = await self._turns.finish(
                        request.turn_id,
                        status=terminal_status,
                        finished_at=finished_at,
                        input_tokens=input_tokens,
                        output_tokens=output_tokens,
                        estimated_cost_microusd=estimated_cost,
                        error_code=error_code,
                    )

        return WorkerTurnResponse(
            turn_id=request.turn_id,
            status=terminal.turn.status,
            last_sequence=await self._events.last_sequence(request.session_id),
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            estimated_cost_microusd=estimated_cost,
            error_code=error_code,
        )

    async def _listen_for_cancel(
        self, request: WorkerTurnRequest, finished: asyncio.Event
    ) -> None:
        cursor = "0-0"
        while not finished.is_set():
            messages = await self._controls.replay_controls(
                request.session_id, after_id=cursor, limit=100
            )
            for message in messages:
                cursor = message.id
                if message.kind == "cancel" and message.action_id == request.turn_id:
                    await self._agent.cancel_turn(request.session_id, request.turn_id)
            try:
                await asyncio.wait_for(finished.wait(), timeout=0.1)
            except TimeoutError:
                pass

    async def _record_approval(
        self, request: WorkerTurnRequest, event: AgentEventContract
    ) -> None:
        if event.type != "permission.requested":
            return
        payload = event.payload
        approval_id = payload.get("request_id") or payload.get("id")
        if not isinstance(approval_id, str):
            return
        risk = payload.get("risk")
        if risk not in {"low", "medium", "high"}:
            risk = "medium"
        await self._approvals.put(
            ApprovalResponse(
                id=approval_id,
                sandbox_id=request.sandbox_id,
                session_id=request.session_id,
                turn_id=request.turn_id,
                owner_id=request.owner_id,
                kind=str(payload.get("kind") or "action")[:200],
                title=str(payload.get("title") or "Approval required")[:500],
                summary=str(payload.get("summary") or "Review this action.")[:500],
                details=str(
                    payload.get("details") or "Review the bounded action details."
                )[:50_000],
                risk=risk,
                expires_at=datetime.now(timezone.utc)
                + timedelta(seconds=self._timeout_seconds),
            )
        )

    async def _ensure_event_persisted(self, event: AgentEventContract) -> None:
        current = await self._events.last_sequence(event.session_id)
        if current < event.sequence:
            await self._events.append(event)
            return
        existing = await self._events.replay(
            event.session_id, event.sequence - 1, 1
        )
        if not existing or existing[0].event_id != event.event_id:
            raise TurnRunnerError(
                "worker_event_conflict", "The persisted event stream conflicted."
            )

    def _estimated_cost(self, input_tokens: int, output_tokens: int) -> int:
        numerator = (
            input_tokens
            * self._settings.owner_funded_input_cost_microusd_per_million
            + output_tokens
            * self._settings.owner_funded_output_cost_microusd_per_million
        )
        return (numerator + 999_999) // 1_000_000

def _bounded_usage(value: object) -> int:
    if isinstance(value, bool) or not isinstance(value, int):
        return 0
    return min(max(value, 0), 10_000_000_000)
