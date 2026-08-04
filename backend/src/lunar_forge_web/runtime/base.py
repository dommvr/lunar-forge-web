"""Provider-neutral sandbox runtime protocol.

The agent/model process remains in the private worker.  Runtime providers only
manage the isolated project workspace and its tool execution surface.
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal, Protocol

from lunar_forge import (
    RuntimeCheckpoint as CoreRuntimeCheckpoint,
    RuntimeCommandResult as CoreRuntimeCommandResult,
    RuntimeFileInfo as CoreRuntimeFileInfo,
    RuntimeOperationResult as CoreRuntimeOperationResult,
    RuntimeRollbackResult as CoreRuntimeRollbackResult,
    RuntimeTextResult as CoreRuntimeTextResult,
    RuntimeWriteResult as CoreRuntimeWriteResult,
)
from pydantic import Field

from lunar_forge_web.domain.base import ContractModel, Identifier
from lunar_forge_web.domain.models import RuntimeCapability


class RuntimeSandbox(ContractModel):
    provider: Identifier
    reference: Identifier
    workspace_root: str = Field(min_length=1, max_length=4_096)
    sandbox_id: Identifier | None = None
    owner_id: Identifier | None = None
    template_id: Identifier | None = None


class RuntimeStatus(ContractModel):
    state: Literal["running", "paused", "stopped", "unknown"]
    started_at: datetime | None = None
    expires_at: datetime | None = None
    cpu_count: int | None = Field(default=None, ge=1, le=128)
    memory_mb: int | None = Field(default=None, ge=1)
    disk_size_mb: int | None = Field(default=None, ge=1)
    secure_access: bool
    internet_access: bool
    metadata: dict[str, str] = Field(default_factory=dict, max_length=50)


class RuntimeCommandResult(ContractModel):
    command_id: Identifier
    exit_code: int
    stdout: str = Field(max_length=100_000)
    stderr: str = Field(max_length=100_000)
    output_truncated: bool = False
    duration_ms: int = Field(default=0, ge=0)
    timed_out: bool = False
    cancelled: bool = False


class RuntimeFile(ContractModel):
    path: str = Field(min_length=1, max_length=4_096)
    kind: Literal["file", "directory"]
    size_bytes: int | None = Field(default=None, ge=0)


class RuntimeFileContent(ContractModel):
    path: str = Field(min_length=1, max_length=4_096)
    content: str = Field(max_length=1_000_000)
    truncated: bool = False


class RuntimeArchive(ContractModel):
    filename: str = Field(min_length=1, max_length=200)
    content: bytes = Field(max_length=10_485_760)


class RuntimeArtifact(ContractModel):
    id: Identifier
    path: str = Field(min_length=1, max_length=4_096)
    name: str = Field(min_length=1, max_length=500)
    media_type: str = Field(min_length=1, max_length=200)
    size_bytes: int = Field(ge=0, le=10_485_760)


class RuntimeProvider(Protocol):
    def capability(self) -> RuntimeCapability: ...

    async def create(
        self,
        *,
        owner_id: str,
        sandbox_id: str,
        template_id: str,
    ) -> RuntimeSandbox: ...

    async def connect(self, sandbox: RuntimeSandbox) -> RuntimeSandbox: ...

    async def status(self, sandbox: RuntimeSandbox) -> RuntimeStatus: ...

    async def reset(self, sandbox: RuntimeSandbox) -> RuntimeSandbox: ...

    async def extend_timeout(self, sandbox: RuntimeSandbox, timeout_seconds: int) -> None: ...

    async def terminate(self, sandbox: RuntimeSandbox) -> None: ...

    async def run_command(
        self,
        sandbox: RuntimeSandbox,
        command: str,
        *,
        timeout_seconds: int,
    ) -> RuntimeCommandResult: ...

    async def cancel_active_command(self, sandbox: RuntimeSandbox) -> bool: ...

    async def list_files(self, sandbox: RuntimeSandbox) -> tuple[RuntimeFile, ...]: ...

    async def read_file(
        self, sandbox: RuntimeSandbox, path: str
    ) -> RuntimeFileContent: ...

    async def archive_project(self, sandbox: RuntimeSandbox) -> RuntimeArchive: ...

    async def list_artifacts(
        self, sandbox: RuntimeSandbox
    ) -> tuple[RuntimeArtifact, ...]: ...

    async def clone_public_git(
        self, sandbox: RuntimeSandbox, repository_url: str
    ) -> RuntimeCommandResult: ...

    async def core_list_directory(
        self, sandbox: RuntimeSandbox, path: str
    ) -> tuple[CoreRuntimeFileInfo, ...]: ...

    async def core_stat(
        self, sandbox: RuntimeSandbox, path: str
    ) -> CoreRuntimeFileInfo | None: ...

    async def core_read_text(
        self,
        sandbox: RuntimeSandbox,
        path: str,
        *,
        start_line: int,
        end_line: int | None,
        max_characters: int,
    ) -> CoreRuntimeTextResult: ...

    async def core_write_text(
        self,
        sandbox: RuntimeSandbox,
        path: str,
        content: str,
        *,
        overwrite: bool,
    ) -> CoreRuntimeWriteResult: ...

    async def core_create_directory(
        self, sandbox: RuntimeSandbox, path: str
    ) -> CoreRuntimeOperationResult: ...

    async def core_delete_path(
        self, sandbox: RuntimeSandbox, path: str, *, recursive: bool
    ) -> CoreRuntimeOperationResult: ...

    async def core_move_path(
        self,
        sandbox: RuntimeSandbox,
        source: str,
        destination: str,
        *,
        overwrite: bool,
    ) -> CoreRuntimeOperationResult: ...

    async def core_execute(
        self,
        sandbox: RuntimeSandbox,
        command: str,
        *,
        timeout_ms: int,
        max_output_characters: int,
    ) -> CoreRuntimeCommandResult: ...

    async def core_checkpoint_turn(
        self, sandbox: RuntimeSandbox, turn_id: str
    ) -> CoreRuntimeCheckpoint: ...

    async def core_rollback_turn(
        self, sandbox: RuntimeSandbox, checkpoint_id: str
    ) -> CoreRuntimeRollbackResult: ...
