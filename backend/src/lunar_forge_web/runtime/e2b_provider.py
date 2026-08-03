"""Disabled E2B boundary reserved for the later runtime phase."""

from lunar_forge_web.domain.enums import Availability
from lunar_forge_web.domain.models import RuntimeCapability
from lunar_forge_web.runtime.base import RuntimeSandbox


class RuntimeUnavailableError(RuntimeError):
    pass


class E2BRuntimeProvider:
    def capability(self) -> RuntimeCapability:
        return RuntimeCapability(
            provider="e2b",
            status=Availability.PLANNED,
            network_policy="unavailable",
            supports_preview=False,
            supports_command_cancellation=False,
        )

    async def create(self, **_: str) -> RuntimeSandbox:
        raise RuntimeUnavailableError("E2B is not connected in this phase.")

    async def terminate(self, sandbox: RuntimeSandbox) -> None:
        del sandbox
        raise RuntimeUnavailableError("E2B is not connected in this phase.")

    async def cancel_active_command(self, sandbox: RuntimeSandbox) -> bool:
        del sandbox
        return False
