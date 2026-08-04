"""Synchronous LunarForge runtime facade over the async hosted provider."""

from __future__ import annotations

import asyncio
from pathlib import Path

from lunar_forge import (
    MAX_RUNTIME_OUTPUT_CHARACTERS,
    MAX_RUNTIME_TEXT_CHARACTERS,
    RuntimeCheckpoint,
    RuntimeCommandResult,
    RuntimeFileInfo,
    RuntimeNetworkPolicy,
    RuntimeOperationResult,
    RuntimeRollbackResult,
    RuntimeTextResult,
    RuntimeWriteResult,
    normalize_workspace_path,
)

from lunar_forge_web.runtime.base import RuntimeProvider, RuntimeSandbox


class HostedWorkspaceRuntime:
    """Implement the stable public core protocol without exposing E2B to core."""

    def __init__(
        self,
        provider: RuntimeProvider,
        sandbox: RuntimeSandbox,
        loop: asyncio.AbstractEventLoop,
    ) -> None:
        self._provider = provider
        self._sandbox = sandbox
        self._loop = loop

    @property
    def workspace_id(self) -> str:
        return self._sandbox.reference

    @property
    def local_project_root(self) -> Path | None:
        return None

    @property
    def network_policy(self) -> RuntimeNetworkPolicy:
        return RuntimeNetworkPolicy.DENIED

    def list_directory(self, path: str = ".") -> tuple[RuntimeFileInfo, ...]:
        relative = normalize_workspace_path(path, allow_root=True)
        return self._call(self._provider.core_list_directory(self._sandbox, relative))

    def stat(self, path: str) -> RuntimeFileInfo | None:
        relative = normalize_workspace_path(path, allow_root=True)
        return self._call(self._provider.core_stat(self._sandbox, relative))

    def read_text(
        self,
        path: str,
        *,
        start_line: int = 1,
        end_line: int | None = None,
        max_characters: int = MAX_RUNTIME_TEXT_CHARACTERS,
    ) -> RuntimeTextResult:
        relative = normalize_workspace_path(path)
        return self._call(
            self._provider.core_read_text(
                self._sandbox,
                relative,
                start_line=start_line,
                end_line=end_line,
                max_characters=max_characters,
            )
        )

    def write_text(
        self, path: str, content: str, *, overwrite: bool = False
    ) -> RuntimeWriteResult:
        relative = normalize_workspace_path(path)
        return self._call(
            self._provider.core_write_text(
                self._sandbox, relative, content, overwrite=overwrite
            )
        )

    def create_directory(self, path: str) -> RuntimeOperationResult:
        relative = normalize_workspace_path(path)
        return self._call(
            self._provider.core_create_directory(self._sandbox, relative)
        )

    def delete_path(
        self, path: str, *, recursive: bool = False
    ) -> RuntimeOperationResult:
        relative = normalize_workspace_path(path)
        return self._call(
            self._provider.core_delete_path(
                self._sandbox, relative, recursive=recursive
            )
        )

    def move_path(
        self,
        source: str,
        destination: str,
        *,
        overwrite: bool = False,
    ) -> RuntimeOperationResult:
        source_path = normalize_workspace_path(source)
        destination_path = normalize_workspace_path(destination)
        return self._call(
            self._provider.core_move_path(
                self._sandbox,
                source_path,
                destination_path,
                overwrite=overwrite,
            )
        )

    def execute(
        self,
        command: str,
        *,
        timeout_ms: int,
        max_output_characters: int = MAX_RUNTIME_OUTPUT_CHARACTERS,
    ) -> RuntimeCommandResult:
        return self._call(
            self._provider.core_execute(
                self._sandbox,
                command,
                timeout_ms=timeout_ms,
                max_output_characters=max_output_characters,
            )
        )

    def cancel_active_command(self) -> bool:
        return self._call(self._provider.cancel_active_command(self._sandbox))

    def checkpoint_turn(self, turn_id: str) -> RuntimeCheckpoint:
        return self._call(
            self._provider.core_checkpoint_turn(self._sandbox, turn_id)
        )

    def rollback_turn(self, checkpoint_id: str) -> RuntimeRollbackResult:
        return self._call(
            self._provider.core_rollback_turn(self._sandbox, checkpoint_id)
        )

    def _call(self, awaitable):
        return asyncio.run_coroutine_threadsafe(awaitable, self._loop).result()
