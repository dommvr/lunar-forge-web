"""Stable LunarForge package adapter and deterministic test fake."""

from __future__ import annotations

import asyncio
import hashlib
import inspect
import re
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator, Mapping
from concurrent.futures import TimeoutError as FutureTimeoutError
from datetime import datetime, timezone
from pathlib import Path
from threading import Event
from typing import Any, Protocol
from uuid import uuid4

from lunar_forge import (
    AgentEvent,
    AgentRequest,
    ApprovalDecision,
    ApprovalRequest,
    run_agent_events,
)
from pydantic import ValidationError

from lunar_forge_web.core.approvals import (
    ApprovalBroker,
    ApprovalContext,
    DenyApprovalBroker,
)
from lunar_forge_web.domain.events import AgentEventContract
from lunar_forge_web.domain.models import WorkerTurnRequest
from lunar_forge_web.security.redaction import redact, redact_text
from lunar_forge_web.storage.repositories import EventRepository


ProjectRootResult = Path | str | Awaitable[Path | str]
ProjectRootResolver = Callable[[WorkerTurnRequest], ProjectRootResult]
EventRunner = Callable[..., Iterator[AgentEvent]]

_END = object()
_SAFE_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,199}$")


class AgentAdapter(Protocol):
    def run_turn(
        self, request: WorkerTurnRequest
    ) -> AsyncIterator[AgentEventContract]: ...

    async def cancel_turn(self, session_id: str, turn_id: str) -> bool: ...

    async def compact_session(self, session_id: str) -> bool: ...


class CoreAdapterError(RuntimeError):
    """Safe error mapped from the public package boundary."""

    def __init__(self, code: str, message: str, *, retryable: bool = False) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class _SessionEventPublisher:
    def __init__(
        self,
        events: EventRepository,
        request: WorkerTurnRequest,
    ) -> None:
        self._events = events
        self._request = request
        self._sequence = 0
        self._lock = asyncio.Lock()
        self._generated: asyncio.Queue[AgentEventContract] = asyncio.Queue(
            maxsize=200
        )
        self._bridged_approvals: set[str] = set()

    async def initialize(self) -> None:
        self._sequence = await self._events.last_sequence(self._request.session_id)

    async def publish_core(
        self, event: AgentEvent
    ) -> AgentEventContract | None:
        if not isinstance(event, AgentEvent):
            raise TypeError("The public event runner returned a non-AgentEvent value.")
        record = event.to_dict()
        event_type = record.get("type")
        payload = record.get("payload")
        if not isinstance(event_type, str) or not isinstance(payload, Mapping):
            raise ValueError("The public AgentEvent envelope is invalid.")
        request_id = payload.get("request_id") or payload.get("id")
        if (
            event_type in {"permission.requested", "permission.resolved"}
            and isinstance(request_id, str)
            and request_id in self._bridged_approvals
        ):
            return None
        return await self._publish(
            schema_version=record.get("schema_version"),
            event_id=_safe_identifier(record.get("event_id"), "core-event"),
            timestamp=record.get("timestamp"),
            event_type=event_type,
            payload=payload,
            parent_event_id=(
                _safe_identifier(record["parent_event_id"], "core-parent")
                if record.get("parent_event_id") is not None
                else None
            ),
            enqueue=False,
        )

    async def publish_approval_request(
        self, request: ApprovalRequest
    ) -> AgentEventContract:
        self._bridged_approvals.add(request.id)
        return await self.publish_generated(
            "permission.requested",
            request.to_dict(),
            enqueue=True,
        )

    async def publish_approval_decision(
        self,
        decision: ApprovalDecision,
        parent_event_id: str,
    ) -> AgentEventContract:
        return await self.publish_generated(
            "permission.resolved",
            decision.to_dict(),
            parent_event_id=parent_event_id,
            enqueue=True,
        )

    async def publish_generated(
        self,
        event_type: str,
        payload: Mapping[str, Any],
        *,
        parent_event_id: str | None = None,
        enqueue: bool = False,
    ) -> AgentEventContract:
        return await self._publish(
            schema_version=1,
            event_id=f"evt_web_{uuid4().hex}",
            timestamp=_timestamp(),
            event_type=event_type,
            payload=payload,
            parent_event_id=parent_event_id,
            enqueue=enqueue,
        )

    async def _publish(
        self,
        *,
        schema_version: Any,
        event_id: str,
        timestamp: Any,
        event_type: str,
        payload: Mapping[str, Any],
        parent_event_id: str | None,
        enqueue: bool,
    ) -> AgentEventContract:
        safe_payload = redact(dict(payload))
        if not isinstance(safe_payload, dict):
            raise ValueError("The redacted event payload must be an object.")
        async with self._lock:
            sequence = self._sequence + 1
            event = AgentEventContract(
                schema_version=schema_version,
                event_id=event_id,
                session_id=self._request.session_id,
                turn_id=self._request.turn_id,
                sequence=sequence,
                timestamp=str(timestamp),
                type=event_type,
                payload=safe_payload,
                parent_event_id=parent_event_id,
            )
            await self._events.append(event)
            self._sequence = sequence
        if enqueue:
            await self._generated.put(event)
        return event

    async def next_generated(self, timeout: float = 0.05) -> AgentEventContract | None:
        try:
            return await asyncio.wait_for(self._generated.get(), timeout=timeout)
        except TimeoutError:
            return None

    def drain_generated(self) -> tuple[AgentEventContract, ...]:
        events: list[AgentEventContract] = []
        while True:
            try:
                events.append(self._generated.get_nowait())
            except asyncio.QueueEmpty:
                return tuple(events)


class _WebApprovalProvider:
    """Synchronous provider consumed by the public LunarForge event runner."""

    def __init__(
        self,
        broker: ApprovalBroker,
        context: ApprovalContext,
        publisher: _SessionEventPublisher,
        loop: asyncio.AbstractEventLoop,
        *,
        wait_timeout_seconds: float,
    ) -> None:
        self._broker = broker
        self._context = context
        self._publisher = publisher
        self._loop = loop
        self._wait_timeout_seconds = wait_timeout_seconds

    def request_approval(self, request: ApprovalRequest) -> ApprovalDecision:
        requested = asyncio.run_coroutine_threadsafe(
            self._publisher.publish_approval_request(request),
            self._loop,
        ).result(timeout=10)
        decision_future = asyncio.run_coroutine_threadsafe(
            self._broker.decide(request, self._context),
            self._loop,
        )
        try:
            decision = decision_future.result(timeout=self._wait_timeout_seconds)
        except FutureTimeoutError:
            decision_future.cancel()
            decision = ApprovalDecision.create(
                request.id,
                approved=False,
                reason="The web approval channel timed out.",
                source="deny",
            )
        except Exception:
            decision = ApprovalDecision.create(
                request.id,
                approved=False,
                reason="The web approval channel failed closed.",
                source="deny",
            )
        if decision.request_id != request.id:
            decision = ApprovalDecision.create(
                request.id,
                approved=False,
                reason="The approval decision did not match the request.",
                source="deny",
            )
        asyncio.run_coroutine_threadsafe(
            self._publisher.publish_approval_decision(
                decision,
                requested.event_id,
            ),
            self._loop,
        ).result(timeout=10)
        return decision


class CoreAgentAdapter:
    """Run the stable public package API and publish bounded web events."""

    def __init__(
        self,
        events: EventRepository,
        project_root_resolver: ProjectRootResolver,
        *,
        approval_broker: ApprovalBroker | None = None,
        event_runner: EventRunner = run_agent_events,
        runtime_mode: str = "local",
        approval_wait_timeout_seconds: float = 905,
    ) -> None:
        if not 1 <= approval_wait_timeout_seconds <= 910:
            raise ValueError("Approval wait timeout must be between 1 and 910 seconds.")
        self._events = events
        self._project_root_resolver = project_root_resolver
        self._approval_broker = approval_broker or DenyApprovalBroker()
        self._event_runner = event_runner
        self._runtime_mode = runtime_mode
        self._approval_wait_timeout_seconds = approval_wait_timeout_seconds
        self._active: dict[tuple[str, str], Event] = {}
        self._active_lock = asyncio.Lock()

    async def construct_request(self, request: WorkerTurnRequest) -> AgentRequest:
        try:
            resolved = self._project_root_resolver(request)
            if inspect.isawaitable(resolved):
                resolved = await resolved
            model = request.settings.model
            return AgentRequest(
                project_root=Path(resolved),
                message=request.message,
                runtime_mode=self._runtime_mode,
                permission_mode=(
                    "plan" if request.settings.plan_mode else "default"
                ),
                allow_network=False,
                model=None if model == "server-default" else model,
                reasoning_effort=request.settings.reasoning_effort,
                offer_commit=False,
                show_usage=request.settings.show_usage,
                ui_metadata={
                    "transport": "lunar-forge-web",
                    "sandbox_id": request.sandbox_id,
                    "session_id": request.session_id,
                    "turn_id": request.turn_id,
                    "funding_mode": request.settings.funding_mode,
                    "provider": request.settings.provider,
                },
            )
        except Exception as exc:
            raise self.map_public_error(exc) from exc

    def run_turn(
        self, request: WorkerTurnRequest
    ) -> AsyncIterator[AgentEventContract]:
        return self._run_turn(request)

    async def _run_turn(
        self, request: WorkerTurnRequest
    ) -> AsyncIterator[AgentEventContract]:
        public_request = await self.construct_request(request)
        publisher = _SessionEventPublisher(self._events, request)
        try:
            await publisher.initialize()
        except Exception as exc:
            raise self.map_public_error(exc) from exc
        cancellation_requested = Event()
        key = (request.session_id, request.turn_id)
        async with self._active_lock:
            if key in self._active:
                raise CoreAdapterError(
                    "core_turn_already_active",
                    "This core turn is already active.",
                )
            self._active[key] = cancellation_requested

        loop = asyncio.get_running_loop()
        approval_provider = _WebApprovalProvider(
            self._approval_broker,
            ApprovalContext(
                session_id=request.session_id,
                turn_id=request.turn_id,
                owner_id=request.owner_id,
                cancellation_requested=cancellation_requested,
            ),
            publisher,
            loop,
            wait_timeout_seconds=self._approval_wait_timeout_seconds,
        )
        iterator: Iterator[AgentEvent] | None = None
        cancelled = False
        try:
            iterator = iter(
                self._event_runner(
                    public_request,
                    approval_provider=approval_provider,
                )
            )
            while True:
                next_task = asyncio.create_task(
                    asyncio.to_thread(_next_event, iterator)
                )
                while not next_task.done():
                    generated = await publisher.next_generated()
                    if generated is not None:
                        yield generated
                item = await next_task
                for generated in publisher.drain_generated():
                    yield generated
                if item is _END:
                    break
                if cancellation_requested.is_set():
                    cancelled = True
                    break
                mapped = await publisher.publish_core(item)
                if mapped is not None:
                    yield mapped
            if cancelled:
                cancelled_event = await publisher.publish_generated(
                    "turn.cancelled",
                    {
                        "status": "cancelled",
                        "reason": "Cancellation was requested through the web adapter.",
                        "rollback_status": "unavailable",
                    },
                )
                yield cancelled_event
        except asyncio.CancelledError:
            cancellation_requested.set()
            raise
        except CoreAdapterError:
            raise
        except Exception as exc:
            mapped_error = self.map_public_error(exc)
            try:
                error_event = await publisher.publish_generated(
                    "error",
                    {
                        "code": mapped_error.code,
                        "message": mapped_error.message,
                        "retryable": mapped_error.retryable,
                        "source": "core_public_api",
                    },
                )
            except Exception:
                raise mapped_error from exc
            yield error_event
            raise mapped_error from exc
        finally:
            if iterator is not None and cancelled:
                close = getattr(iterator, "close", None)
                if callable(close):
                    await asyncio.to_thread(close)
            async with self._active_lock:
                self._active.pop(key, None)

    async def cancel_turn(self, session_id: str, turn_id: str) -> bool:
        async with self._active_lock:
            cancellation = self._active.get((session_id, turn_id))
            if cancellation is None:
                return False
            cancellation.set()
            return True

    async def compact_session(self, session_id: str) -> bool:
        # The pinned public package has no manual compaction operation. Automatic
        # compaction events are still forwarded by run_turn.
        del session_id
        return False

    @staticmethod
    def map_public_error(exc: Exception) -> CoreAdapterError:
        if isinstance(exc, CoreAdapterError):
            return exc
        safe_detail = redact_text(str(exc))[:500].strip()
        if isinstance(exc, NotADirectoryError):
            return CoreAdapterError(
                "core_project_unavailable",
                safe_detail or "The core project root is unavailable.",
            )
        if isinstance(exc, (TypeError, ValueError, ValidationError)):
            return CoreAdapterError(
                "core_request_invalid",
                safe_detail or "The core request or event was invalid.",
            )
        if isinstance(exc, PermissionError):
            return CoreAdapterError(
                "core_permission_denied",
                "The core operation was denied by the runtime.",
            )
        if isinstance(exc, TimeoutError):
            return CoreAdapterError(
                "core_timeout",
                "The core operation timed out.",
                retryable=True,
            )
        if isinstance(exc, OSError):
            return CoreAdapterError(
                "core_io_error",
                safe_detail or "The core operation failed while accessing the project.",
                retryable=True,
            )
        return CoreAdapterError(
            "core_execution_failed",
            safe_detail or "The core operation failed.",
        )


class FakeCoreAgentAdapter:
    """Emit the core schema-v1 envelope without importing or running core."""

    def run_turn(
        self, request: WorkerTurnRequest
    ) -> AsyncIterator[AgentEventContract]:
        return self._events(request)

    async def _events(
        self, request: WorkerTurnRequest
    ) -> AsyncIterator[AgentEventContract]:
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


def _next_event(iterator: Iterator[AgentEvent]) -> AgentEvent | object:
    try:
        return next(iterator)
    except StopIteration:
        return _END


def _safe_identifier(value: Any, namespace: str) -> str:
    text = str(value)
    if _SAFE_IDENTIFIER.fullmatch(text):
        return text
    digest = hashlib.sha256(text.encode("utf-8", errors="replace")).hexdigest()
    return f"evt_{namespace}_{digest[:32]}"


def _timestamp() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )
