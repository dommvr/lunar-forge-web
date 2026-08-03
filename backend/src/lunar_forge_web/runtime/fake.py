"""Deterministic offline runtime used by contract tests."""

from lunar_forge_web.domain.enums import Availability
from lunar_forge_web.domain.models import RuntimeCapability
from lunar_forge_web.runtime.base import RuntimeSandbox


class FakeRuntimeProvider:
    def capability(self) -> RuntimeCapability:
        return RuntimeCapability(
            provider="fake",
            status=Availability.FAKE,
            network_policy="offline",
            supports_preview=False,
            supports_command_cancellation=True,
        )

    async def create(
        self,
        *,
        owner_id: str,
        sandbox_id: str,
        template_id: str,
    ) -> RuntimeSandbox:
        del owner_id, template_id
        return RuntimeSandbox(
            provider="fake",
            reference=f"runtime_{sandbox_id}",
            workspace_root="/workspace",
        )

    async def terminate(self, sandbox: RuntimeSandbox) -> None:
        del sandbox

    async def cancel_active_command(self, sandbox: RuntimeSandbox) -> bool:
        del sandbox
        return True
