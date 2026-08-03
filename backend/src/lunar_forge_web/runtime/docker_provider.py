"""Disabled future admin-only Docker provider."""

from lunar_forge_web.domain.enums import Availability
from lunar_forge_web.domain.models import RuntimeCapability
from lunar_forge_web.runtime.base import RuntimeSandbox
from lunar_forge_web.runtime.e2b_provider import RuntimeUnavailableError


class DockerRuntimeProvider:
    def capability(self) -> RuntimeCapability:
        return RuntimeCapability(
            provider="docker",
            status=Availability.PLANNED,
            network_policy="unavailable",
            supports_preview=False,
            supports_command_cancellation=False,
        )

    async def create(self, **_: str) -> RuntimeSandbox:
        raise RuntimeUnavailableError("Hosted Docker is disabled in this phase.")

    async def terminate(self, sandbox: RuntimeSandbox) -> None:
        del sandbox
        raise RuntimeUnavailableError("Hosted Docker is disabled in this phase.")

    async def cancel_active_command(self, sandbox: RuntimeSandbox) -> bool:
        del sandbox
        return False
