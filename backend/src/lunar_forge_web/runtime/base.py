"""Provider-neutral runtime protocol."""

from __future__ import annotations

from typing import Protocol

from pydantic import Field

from lunar_forge_web.domain.base import ContractModel, Identifier
from lunar_forge_web.domain.models import RuntimeCapability


class RuntimeSandbox(ContractModel):
    provider: Identifier
    reference: Identifier
    workspace_root: str = Field(min_length=1, max_length=4_096)


class RuntimeProvider(Protocol):
    def capability(self) -> RuntimeCapability: ...

    async def create(
        self,
        *,
        owner_id: str,
        sandbox_id: str,
        template_id: str,
    ) -> RuntimeSandbox: ...

    async def terminate(self, sandbox: RuntimeSandbox) -> None: ...

    async def cancel_active_command(self, sandbox: RuntimeSandbox) -> bool: ...
