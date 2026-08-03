"""Deterministic offline runtime used by unit and contract tests."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from io import BytesIO
from uuid import uuid4
from zipfile import ZIP_DEFLATED, ZipFile

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


def _parent_paths(path: str) -> set[str]:
    parts = path.split("/")[:-1]
    return {"/".join(parts[:index]) for index in range(1, len(parts) + 1)}
