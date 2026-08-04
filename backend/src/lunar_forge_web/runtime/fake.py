"""Deterministic offline runtime used by unit and contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from difflib import unified_diff
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

from lunar_forge import (
    RuntimeCheckpoint as CoreRuntimeCheckpoint,
    RuntimeCommandResult as CoreRuntimeCommandResult,
    RuntimeFileInfo as CoreRuntimeFileInfo,
    RuntimeNetworkPolicy,
    RuntimeOperationResult as CoreRuntimeOperationResult,
    RuntimePathType,
    RuntimeRollbackResult,
    RuntimeRollbackStatus,
    RuntimeTextResult,
    RuntimeWriteResult,
)

from lunar_forge_web.domain.enums import Availability
from lunar_forge_web.domain.models import RuntimeCapability
from lunar_forge_web.runtime.base import (
    RuntimeArchive,
    RuntimeArtifact,
    RuntimeCommandResult,
    RuntimeFile,
    RuntimeFileContent,
    RuntimeSandbox,
    RuntimeStatus,
)
from lunar_forge_web.security.limits import SANDBOX_INACTIVITY_TTL_SECONDS
from lunar_forge_web.security.paths import normalize_workspace_path


class FakeRuntimeProvider:
    def __init__(self) -> None:
        self._sandboxes: dict[str, RuntimeSandbox] = {}
        self._expires_at: dict[str, datetime] = {}
        self._files: dict[str, dict[str, bytes]] = {}
        self._checkpoints: dict[tuple[str, str], dict[str, bytes]] = {}

    def capability(self) -> RuntimeCapability:
        return RuntimeCapability(
            provider="fake",
            status=Availability.FAKE,
            network_policy="offline",
            supports_preview=False,
            supports_command_cancellation=True,
            supports_ttl_extension=True,
            supports_temporary_egress=False,
            supports_public_git_clone=False,
            inactivity_ttl_seconds=SANDBOX_INACTIVITY_TTL_SECONDS,
            cpu_count=1,
            memory_mb=512,
        )

    async def create(
        self,
        *,
        owner_id: str,
        sandbox_id: str,
        template_id: str,
    ) -> RuntimeSandbox:
        runtime = RuntimeSandbox(
            provider="fake",
            reference=f"runtime_{sandbox_id}",
            workspace_root="/workspace",
            sandbox_id=sandbox_id,
            owner_id=owner_id,
            template_id=template_id,
        )
        self._sandboxes[runtime.reference] = runtime
        self._expires_at[runtime.reference] = datetime.now(timezone.utc) + timedelta(
            seconds=SANDBOX_INACTIVITY_TTL_SECONDS
        )
        self._files[runtime.reference] = {
            "README.md": b"# Deterministic fake project\n",
            "src/main.py": b'print("hello from fake runtime")\n',
            ".lunar-forge/artifacts/validation.txt": b"validation passed\n",
        }
        return runtime

    async def connect(self, sandbox: RuntimeSandbox) -> RuntimeSandbox:
        return self._sandboxes.get(sandbox.reference, sandbox)

    async def status(self, sandbox: RuntimeSandbox) -> RuntimeStatus:
        running = sandbox.reference in self._sandboxes
        return RuntimeStatus(
            state="running" if running else "stopped",
            expires_at=self._expires_at.get(sandbox.reference),
            cpu_count=1,
            memory_mb=512,
            secure_access=True,
            internet_access=False,
            metadata={"runtime": "fake"},
        )

    async def reset(self, sandbox: RuntimeSandbox) -> RuntimeSandbox:
        await self.terminate(sandbox)
        if not sandbox.owner_id or not sandbox.sandbox_id or not sandbox.template_id:
            raise ValueError("Sandbox identity is required for reset.")
        return await self.create(
            owner_id=sandbox.owner_id,
            sandbox_id=sandbox.sandbox_id,
            template_id=sandbox.template_id,
        )

    async def extend_timeout(
        self, sandbox: RuntimeSandbox, timeout_seconds: int
    ) -> None:
        if sandbox.reference in self._sandboxes:
            self._expires_at[sandbox.reference] = datetime.now(timezone.utc) + timedelta(
                seconds=timeout_seconds
            )

    async def terminate(self, sandbox: RuntimeSandbox) -> None:
        self._sandboxes.pop(sandbox.reference, None)
        self._expires_at.pop(sandbox.reference, None)
        self._files.pop(sandbox.reference, None)

    async def run_command(
        self,
        sandbox: RuntimeSandbox,
        command: str,
        *,
        timeout_seconds: int,
    ) -> RuntimeCommandResult:
        del timeout_seconds
        await self.connect(sandbox)
        return RuntimeCommandResult(
            command_id=f"cmd_{uuid4().hex}",
            exit_code=0,
            stdout=f"fake: {command}\n",
            stderr="",
        )

    async def cancel_active_command(self, sandbox: RuntimeSandbox) -> bool:
        del sandbox
        return True

    async def list_files(self, sandbox: RuntimeSandbox) -> tuple[RuntimeFile, ...]:
        files = self._files.get(sandbox.reference, {})
        directories = {part for path in files for part in _parent_paths(path)}
        items = [RuntimeFile(path=path, kind="directory") for path in directories]
        items.extend(
            RuntimeFile(path=path, kind="file", size_bytes=len(content))
            for path, content in files.items()
            if not path.startswith(".lunar-forge/")
        )
        return tuple(sorted(items, key=lambda item: item.path))

    async def read_file(
        self, sandbox: RuntimeSandbox, path: str
    ) -> RuntimeFileContent:
        normalized = normalize_workspace_path(path)
        content = self._files.get(sandbox.reference, {}).get(normalized)
        if content is None or normalized.startswith(".lunar-forge/"):
            raise FileNotFoundError(normalized)
        return RuntimeFileContent(path=normalized, content=content.decode("utf-8"))

    async def archive_project(self, sandbox: RuntimeSandbox) -> RuntimeArchive:
        output = BytesIO()
        with ZipFile(output, "w", ZIP_DEFLATED) as archive:
            for path, content in self._files.get(sandbox.reference, {}).items():
                if not path.startswith(".lunar-forge/"):
                    archive.writestr(path, content)
        return RuntimeArchive(
            filename=f"{sandbox.sandbox_id or 'project'}.zip",
            content=output.getvalue(),
        )

    async def list_artifacts(
        self, sandbox: RuntimeSandbox
    ) -> tuple[RuntimeArtifact, ...]:
        prefix = ".lunar-forge/artifacts/"
        return tuple(
            RuntimeArtifact(
                id=f"artifact_{index}",
                path=path,
                name=path.removeprefix(prefix),
                media_type="text/plain",
                size_bytes=len(content),
            )
            for index, (path, content) in enumerate(
                sorted(self._files.get(sandbox.reference, {}).items()), start=1
            )
            if path.startswith(prefix)
        )

    async def clone_public_git(
        self, sandbox: RuntimeSandbox, repository_url: str
    ) -> RuntimeCommandResult:
        del repository_url
        return await self.run_command(
            sandbox,
            "fake public Git clone",
            timeout_seconds=120,
        )

    async def core_list_directory(
        self, sandbox: RuntimeSandbox, path: str
    ) -> tuple[CoreRuntimeFileInfo, ...]:
        prefix = "" if path == "." else f"{path}/"
        entries: dict[str, CoreRuntimeFileInfo] = {}
        for file_path, content in self._files.get(sandbox.reference, {}).items():
            if file_path.startswith(".lunar-forge/") or not file_path.startswith(prefix):
                continue
            remainder = file_path[len(prefix) :]
            name, separator, _ = remainder.partition("/")
            entry_path = f"{prefix}{name}" if prefix else name
            entries[entry_path] = CoreRuntimeFileInfo(
                entry_path,
                RuntimePathType.DIRECTORY if separator else RuntimePathType.FILE,
                size_bytes=None if separator else len(content),
            )
        return tuple(entries[key] for key in sorted(entries))

    async def core_stat(
        self, sandbox: RuntimeSandbox, path: str
    ) -> CoreRuntimeFileInfo | None:
        files = self._files.get(sandbox.reference, {})
        if path in files and not path.startswith(".lunar-forge/"):
            return CoreRuntimeFileInfo(path, RuntimePathType.FILE, len(files[path]))
        prefix = "" if path == "." else f"{path}/"
        if path == "." or any(item.startswith(prefix) for item in files):
            return CoreRuntimeFileInfo(path, RuntimePathType.DIRECTORY)
        return None

    async def core_read_text(
        self,
        sandbox: RuntimeSandbox,
        path: str,
        *,
        start_line: int,
        end_line: int | None,
        max_characters: int,
    ) -> RuntimeTextResult:
        content = (await self.read_file(sandbox, path)).content
        selected = "".join(content.splitlines(keepends=True)[start_line - 1 : end_line])
        return RuntimeTextResult(
            path,
            selected[:max_characters],
            truncated=len(selected) > max_characters,
            start_line=start_line,
            end_line=end_line,
        )

    async def core_write_text(
        self,
        sandbox: RuntimeSandbox,
        path: str,
        content: str,
        *,
        overwrite: bool,
    ) -> RuntimeWriteResult:
        files = self._files.setdefault(sandbox.reference, {})
        existing = files.get(path)
        if existing is not None and not overwrite:
            return RuntimeWriteResult(False, path, error="File already exists.")
        before = existing.decode("utf-8", errors="replace") if existing else ""
        files[path] = content.encode("utf-8")
        diff = "".join(
            unified_diff(
                before.splitlines(keepends=True),
                content.splitlines(keepends=True),
                fromfile=f"a/{path}",
                tofile=f"b/{path}",
            )
        )
        return RuntimeWriteResult(
            True,
            path,
            created=existing is None,
            overwritten=existing is not None,
            diff=diff,
        )

    async def core_create_directory(
        self, sandbox: RuntimeSandbox, path: str
    ) -> CoreRuntimeOperationResult:
        del sandbox
        return CoreRuntimeOperationResult(True, path)

    async def core_delete_path(
        self, sandbox: RuntimeSandbox, path: str, *, recursive: bool
    ) -> CoreRuntimeOperationResult:
        files = self._files.setdefault(sandbox.reference, {})
        if path in files:
            del files[path]
            return CoreRuntimeOperationResult(True, path)
        nested = [item for item in files if item.startswith(f"{path}/")]
        if nested and not recursive:
            return CoreRuntimeOperationResult(False, path, error="Directory is not empty.")
        for item in nested:
            del files[item]
        return CoreRuntimeOperationResult(bool(nested), path, error=None if nested else "Path not found.")

    async def core_move_path(
        self,
        sandbox: RuntimeSandbox,
        source: str,
        destination: str,
        *,
        overwrite: bool,
    ) -> CoreRuntimeOperationResult:
        files = self._files.setdefault(sandbox.reference, {})
        if source not in files:
            return CoreRuntimeOperationResult(False, source, destination=destination, error="Path not found.")
        if destination in files and not overwrite:
            return CoreRuntimeOperationResult(False, source, destination=destination, error="Destination exists.")
        files[destination] = files.pop(source)
        return CoreRuntimeOperationResult(True, source, destination=destination)

    async def core_execute(
        self,
        sandbox: RuntimeSandbox,
        command: str,
        *,
        timeout_ms: int,
        max_output_characters: int,
    ) -> CoreRuntimeCommandResult:
        result = await self.run_command(
            sandbox, command, timeout_seconds=max(1, min(900, timeout_ms // 1_000))
        )
        return CoreRuntimeCommandResult(
            ok=result.exit_code == 0,
            command=command,
            exit_code=result.exit_code,
            stdout=result.stdout[:max_output_characters],
            stderr=result.stderr[:max_output_characters],
        )

    async def core_checkpoint_turn(
        self, sandbox: RuntimeSandbox, turn_id: str
    ) -> CoreRuntimeCheckpoint:
        checkpoint_id = f"checkpoint_{turn_id}"
        self._checkpoints[(sandbox.reference, checkpoint_id)] = dict(
            self._files.get(sandbox.reference, {})
        )
        return CoreRuntimeCheckpoint(True, checkpoint_id=checkpoint_id)

    async def core_rollback_turn(
        self, sandbox: RuntimeSandbox, checkpoint_id: str
    ) -> RuntimeRollbackResult:
        before = self._checkpoints.pop((sandbox.reference, checkpoint_id), None)
        if before is None:
            return RuntimeRollbackResult(
                RuntimeRollbackStatus.FAILED, errors=("Checkpoint was not found.",)
            )
        current = self._files.get(sandbox.reference, {})
        restored = tuple(
            path for path, content in before.items() if current.get(path) != content
        )
        removed = tuple(path for path in current if path not in before)
        self._files[sandbox.reference] = dict(before)
        return RuntimeRollbackResult(
            RuntimeRollbackStatus.COMPLETED,
            restored_files=restored,
            removed_files=removed,
        )


def _parent_paths(path: str) -> set[str]:
    parts = path.split("/")[:-1]
    return {"/".join(parts[:index]) for index in range(1, len(parts) + 1)}
