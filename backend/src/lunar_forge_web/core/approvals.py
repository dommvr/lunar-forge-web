"""Approval bridge from the synchronous public core API to Redis controls."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from threading import Event
from typing import Protocol

from lunar_forge import ApprovalDecision, ApprovalRequest

from lunar_forge_web.security.redaction import redact_text
from lunar_forge_web.storage.redis import ControlMessage


@dataclass(frozen=True, slots=True)
class ApprovalContext:
    session_id: str
    turn_id: str
    owner_id: str
    cancellation_requested: Event


class ApprovalBroker(Protocol):
    async def decide(
        self,
        request: ApprovalRequest,
        context: ApprovalContext,
    ) -> ApprovalDecision: ...


class ApprovalControlStore(Protocol):
    async def replay_controls(
        self,
        session_id: str,
        after_id: str = "0-0",
        limit: int = 100,
    ) -> tuple[ControlMessage, ...]: ...


class DenyApprovalBroker:
    """Fail closed when no interactive approval channel is configured."""

    async def decide(
        self,
        request: ApprovalRequest,
        context: ApprovalContext,
    ) -> ApprovalDecision:
        del context
        return ApprovalDecision.create(
            request.id,
            approved=False,
            reason="No web approval channel is configured.",
            source="deny",
        )


class RedisApprovalBroker:
    """Resolve one core approval from bounded per-session Redis controls."""

    def __init__(
        self,
        controls: ApprovalControlStore,
        *,
        timeout_seconds: float = 900,
        poll_interval_seconds: float = 0.1,
    ) -> None:
        if not 1 <= timeout_seconds <= 900:
            raise ValueError("Approval timeout must be between 1 and 900 seconds.")
        if not 0.01 <= poll_interval_seconds <= 5:
            raise ValueError("Approval polling interval is out of bounds.")
        self._controls = controls
        self._timeout_seconds = timeout_seconds
        self._poll_interval_seconds = poll_interval_seconds

    async def decide(
        self,
        request: ApprovalRequest,
        context: ApprovalContext,
    ) -> ApprovalDecision:
        loop = asyncio.get_running_loop()
        deadline = loop.time() + self._timeout_seconds
        cursor = "0-0"
        while loop.time() < deadline:
            if context.cancellation_requested.is_set():
                return self._denied(request, "The turn was cancelled.")
            messages = await self._controls.replay_controls(
                context.session_id,
                after_id=cursor,
                limit=100,
            )
            for message in messages:
                cursor = message.id
                if (
                    message.kind == "cancel"
                    and message.action_id == context.turn_id
                ):
                    context.cancellation_requested.set()
                    return self._denied(request, "The turn was cancelled.")
                if (
                    message.kind != "approval"
                    or message.action_id != request.id
                ):
                    continue
                approved = message.payload.get("approved")
                if not isinstance(approved, bool):
                    continue
                raw_reason = message.payload.get("reason", "")
                reason = (
                    redact_text(raw_reason)[:1_000]
                    if isinstance(raw_reason, str)
                    else ""
                )
                if not reason:
                    reason = "Approved by user." if approved else "Denied by user."
                return ApprovalDecision.create(
                    request.id,
                    approved=approved,
                    reason=reason,
                    # The core public enum has no web source yet. "textual" is
                    # its only interactive UI source and is documented as a gap.
                    source="textual",
                )
            await asyncio.sleep(self._poll_interval_seconds)
        return self._denied(request, "The approval request expired.")

    @staticmethod
    def _denied(request: ApprovalRequest, reason: str) -> ApprovalDecision:
        return ApprovalDecision.create(
            request.id,
            approved=False,
            reason=reason,
            source="deny",
        )
