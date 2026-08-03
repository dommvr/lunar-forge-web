"""Future asynchronous bridge to LunarForge's public ApprovalProvider."""

from typing import Protocol

from lunar_forge_web.domain.models import ApprovalResponse


class ApprovalBroker(Protocol):
    async def request(self, approval: ApprovalResponse) -> bool: ...
