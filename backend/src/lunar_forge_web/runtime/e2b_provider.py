"""Production E2B runtime adapter for isolated project tools and execution."""

from __future__ import annotations

import asyncio
import hashlib
import mimetypes
import re
import shlex
from collections.abc import AsyncIterator, Iterable
from contextlib import asynccontextmanager
from pathlib import PurePosixPath
from typing import Any, Literal, Protocol
from uuid import uuid4

from e2b import (
    AsyncSandbox,
    CommandExitException,
    FileNotFoundException as E2BFileNotFoundException,
    FileType,
    SandboxNotFoundException,
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
from lunar_forge_web.security.git_urls import validate_public_github_url
from lunar_forge_web.security.limits import (
    MAX_FILE_RESPONSE_CHARACTERS,
    MAX_PUBLIC_GIT_CLONE_BYTES,
    MAX_PUBLIC_GIT_CLONE_SECONDS,
    MAX_RUNTIME_ARCHIVE_BYTES,
    MAX_RUNTIME_ARTIFACT_BYTES,
    MAX_RUNTIME_COMMAND_CHARACTERS,
    MAX_RUNTIME_COMMAND_OUTPUT_CHARACTERS,
    MAX_RUNTIME_FILE_ENTRIES,
    SANDBOX_INACTIVITY_TTL_SECONDS,
)
from lunar_forge_web.security.paths import normalize_workspace_path
from lunar_forge_web.security.redaction import redact_text


WORKSPACE_ROOT = "/home/user/project"
ARTIFACT_ROOT = f"{WORKSPACE_ROOT}/.lunar-forge/artifacts"
_DENY_ALL = "0.0.0.0/0"
_METADATA_OWNER = "lfw_owner_id"
_METADATA_SANDBOX = "lfw_sandbox_id"
_METADATA_TEMPLATE = "lfw_template_id"
_METADATA_NETWORK = "lfw_network_policy"
_HIDDEN_ROOTS = frozenset({".agent", ".git", ".lunar-forge", ".ssh"})
_SENSITIVE_NAMES = frozenset(
    {".env", ".npmrc", ".pypirc", ".git-credentials", "id_rsa", "id_ed25519"}
)
_CREDENTIAL_PATTERN = re.compile(
    r"(?i)(OPENAI_API_KEY|ANTHROPIC_API_KEY|E2B_API_KEY|sk-(?:ant-)?[A-Za-z0-9_-]{8,})"
)
_NETWORK_ALLOWLISTS: dict[str, tuple[str, ...]] = {
    "github": ("api.github.com", "github.com"),
    "npm": ("registry.npmjs.org",),
    "pip": ("pypi.org", "files.pythonhosted.org"),
}


class RuntimeUnavailableError(RuntimeError):
    pass


class RuntimeIdentityError(RuntimeError):
    pass


class RuntimeNetworkPolicyError(RuntimeError):
    pass


class RuntimeLimitError(RuntimeError):
    pass


class E2BClient(Protocol):
    async def create(self, **kwargs: Any) -> Any: ...
    async def connect(self, sandbox_id: str) -> Any: ...
    async def kill(self, sandbox_id: str) -> bool: ...


class E2BSDKClient:
    def __init__(self, api_key: str, request_timeout_seconds: float) -> None:
        self._options = {
            "api_key": api_key,
            "request_timeout": request_timeout_seconds,
        }

    async def create(self, **kwargs: Any) -> Any:
        return await AsyncSandbox.create(**kwargs, **self._options)

    async def connect(self, sandbox_id: str) -> Any:
        return await AsyncSandbox.connect(sandbox_id, **self._options)

    async def kill(self, sandbox_id: str) -> bool:
        return await AsyncSandbox.kill(sandbox_id, **self._options)


class E2BRuntimeProvider:
    def __init__(
        self,
        *,
        api_key: str | None,
        template_ids: dict[str, str],
        request_timeout_seconds: float = 20.0,
        client: E2BClient | None = None,
    ) -> None:
        self._client = client or (
            E2BSDKClient(api_key, request_timeout_seconds) if api_key else None
        )
        self._template_ids = dict(template_ids)
        self._request_timeout_seconds = request_timeout_seconds
        self._operation_locks: dict[str, asyncio.Lock] = {}
        self._active_commands: dict[str, Any] = {}

    def capability(self) -> RuntimeCapability:
        available = self._client is not None
        return RuntimeCapability(
            provider="e2b",
            status=Availability.AVAILABLE if available else Availability.UNAVAILABLE,
            network_policy="provider_enforced" if available else "unavailable",
            supports_preview=False,
            supports_command_cancellation=available,
            supports_ttl_extension=available,
            supports_temporary_egress=available,
            supports_public_git_clone=available,
            inactivity_ttl_seconds=SANDBOX_INACTIVITY_TTL_SECONDS,
            cpu_count=2,
            memory_mb=2_048,
        )

    async def create(
        self,
        *,
        owner_id: str,
        sandbox_id: str,
        template_id: str,
    ) -> RuntimeSandbox:
        client = self._require_client()
        e2b_template = self._template_ids.get(template_id)
        if not e2b_template:
            raise RuntimeUnavailableError(f"Unknown E2B template: {template_id}.")
        metadata = {
            _METADATA_OWNER: owner_id,
            _METADATA_SANDBOX: sandbox_id,
            _METADATA_TEMPLATE: template_id,
            _METADATA_NETWORK: "deny_all",
        }
        remote = await client.create(
            template=e2b_template,
            timeout=SANDBOX_INACTIVITY_TTL_SECONDS,
            metadata=metadata,
            envs={},
            secure=True,
            allow_internet_access=False,
            network={
                "deny_out": [_DENY_ALL],
                "allow_public_traffic": False,
            },
            lifecycle={"on_timeout": "kill", "auto_resume": False},
        )
        runtime = RuntimeSandbox(
            provider="e2b",
            reference=remote.sandbox_id,
            workspace_root=WORKSPACE_ROOT,
            sandbox_id=sandbox_id,
            owner_id=owner_id,
            template_id=template_id,
        )
        try:
            info = await remote.get_info()
            self._validate_identity(runtime, info.metadata)
            self._assert_offline(info)
            lifecycle = getattr(info, "lifecycle", None) or {}
            on_timeout = (
                lifecycle.get("on_timeout")
                if isinstance(lifecycle, dict)
                else getattr(lifecycle, "on_timeout", None)
            )
            if on_timeout != "kill":
                raise RuntimeNetworkPolicyError("E2B did not apply kill-on-timeout.")
        except Exception:
            await client.kill(remote.sandbox_id)
            raise
        return runtime

    async def connect(self, sandbox: RuntimeSandbox) -> RuntimeSandbox:
        async with self._lock(sandbox.reference):
            await self._connect_verified(sandbox)
        return sandbox

    async def status(self, sandbox: RuntimeSandbox) -> RuntimeStatus:
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            info = await remote.get_info()
            self._assert_offline(info)
            state = getattr(info.state, "value", str(info.state))
            return RuntimeStatus(
                state=state if state in {"running", "paused"} else "unknown",
                started_at=info.started_at,
                expires_at=info.end_at,
                cpu_count=info.cpu_count,
                memory_mb=info.memory_mb,
                disk_size_mb=getattr(info, "disk_size_mb", None),
                secure_access=True,
                internet_access=False,
                metadata=dict(info.metadata),
            )

    async def reset(self, sandbox: RuntimeSandbox) -> RuntimeSandbox:
        self._require_identity(sandbox)
        await self.terminate(sandbox)
        return await self.create(
            owner_id=sandbox.owner_id or "",
            sandbox_id=sandbox.sandbox_id or "",
            template_id=sandbox.template_id or "",
        )

    async def extend_timeout(
        self, sandbox: RuntimeSandbox, timeout_seconds: int
    ) -> None:
        if timeout_seconds != SANDBOX_INACTIVITY_TTL_SECONDS:
            raise RuntimeLimitError("Only the 30-minute inactivity TTL is allowed.")
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            await remote.set_timeout(timeout_seconds)

    async def terminate(self, sandbox: RuntimeSandbox) -> None:
        client = self._require_client()
        handle = self._active_commands.pop(sandbox.reference, None)
        if handle is not None:
            await handle.kill()
        try:
            await client.kill(sandbox.reference)
        except SandboxNotFoundException:
            pass
        self._operation_locks.pop(sandbox.reference, None)

    async def run_command(
        self,
        sandbox: RuntimeSandbox,
        command: str,
        *,
        timeout_seconds: int,
    ) -> RuntimeCommandResult:
        self._validate_command(command, timeout_seconds)
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            return await self._run_command_locked(
                sandbox, remote, command, timeout_seconds=timeout_seconds
            )

    async def run_approved_network_command(
        self,
        sandbox: RuntimeSandbox,
        command: str,
        *,
        operation: Literal["npm", "pip"],
        timeout_seconds: int,
    ) -> RuntimeCommandResult:
        """Run an already-approved install with a provider-enforced host allowlist."""

        self._validate_command(command, timeout_seconds)
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            async with self._temporary_egress(remote, _NETWORK_ALLOWLISTS[operation]):
                return await self._run_command_locked(
                    sandbox, remote, command, timeout_seconds=timeout_seconds
                )

    async def clone_public_git(
        self, sandbox: RuntimeSandbox, repository_url: str
    ) -> RuntimeCommandResult:
        repository = validate_public_github_url(repository_url)
        temp_root = f"/home/user/.lf-clone-{uuid4().hex}"
        quoted_url = shlex.quote(repository.url)
        quoted_temp = shlex.quote(temp_root)
        quoted_workspace = shlex.quote(WORKSPACE_ROOT)
        size_check = shlex.quote(
            _github_size_check_script(repository.owner, repository.repository)
        )
        command = (
            "set -eu; "
            f"python3 -c {size_check}; "
            f"git -c protocol.file.allow=never -c http.followRedirects=false clone "
            f"--depth 1 --single-branch --no-tags --filter=blob:none -- {quoted_url} {quoted_temp}; "
            f"test ! -e {quoted_temp}/.gitmodules; "
            f"test -z \"$(find {quoted_temp} -type l -print -quit)\"; "
            f"test \"$(find {quoted_temp} -xdev | wc -l)\" -le 50000; "
            f"size=$(du -sb {quoted_temp} | cut -f1); "
            f"test \"$size\" -le {MAX_PUBLIC_GIT_CLONE_BYTES}; "
            f"rm -rf -- {quoted_temp}/.git; "
            f"find {quoted_workspace} -mindepth 1 -maxdepth 1 -exec rm -rf -- {{}} +; "
            f"cp -a -- {quoted_temp}/. {quoted_workspace}/; "
            f"rm -rf -- {quoted_temp}"
        )
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            try:
                async with self._temporary_egress(
                    remote, _NETWORK_ALLOWLISTS["github"]
                ):
                    return await self._run_command_locked(
                        sandbox,
                        remote,
                        command,
                        timeout_seconds=MAX_PUBLIC_GIT_CLONE_SECONDS,
                    )
            finally:
                await remote.commands.run(
                    f"rm -rf -- {quoted_temp}",
                    timeout=10,
                    request_timeout=self._request_timeout_seconds,
                )

    async def cancel_active_command(self, sandbox: RuntimeSandbox) -> bool:
        handle = self._active_commands.get(sandbox.reference)
        if handle is None:
            return False
        return bool(await handle.kill())

    async def list_files(self, sandbox: RuntimeSandbox) -> tuple[RuntimeFile, ...]:
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            entries = await remote.files.list(
                WORKSPACE_ROOT,
                depth=20,
                request_timeout=self._request_timeout_seconds,
            )
            visible: list[RuntimeFile] = []
            for entry in entries:
                relative = self._relative_visible_path(entry.path)
                if relative is None or entry.type == FileType.SYMLINK:
                    continue
                kind = "directory" if entry.type == FileType.DIR else "file"
                visible.append(
                    RuntimeFile(
                        path=relative,
                        kind=kind,
                        size_bytes=entry.size if kind == "file" else None,
                    )
                )
                if len(visible) >= MAX_RUNTIME_FILE_ENTRIES:
                    break
            return tuple(sorted(visible, key=lambda item: item.path))

    async def read_file(
        self, sandbox: RuntimeSandbox, path: str
    ) -> RuntimeFileContent:
        normalized = self._visible_path(path)
        absolute = f"{WORKSPACE_ROOT}/{normalized}"
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            try:
                raw, truncated = await self._read_bounded(
                    remote, absolute, MAX_FILE_RESPONSE_CHARACTERS
                )
            except E2BFileNotFoundException as exc:
                raise FileNotFoundError(normalized) from exc
        return RuntimeFileContent(
            path=normalized,
            content=raw.decode("utf-8", errors="replace"),
            truncated=truncated,
        )

    async def archive_project(self, sandbox: RuntimeSandbox) -> RuntimeArchive:
        archive_path = f"/tmp/lf-project-{uuid4().hex}.zip"
        script = _archive_script(archive_path)
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            try:
                result = await remote.commands.run(
                    f"python3 -c {shlex.quote(script)}",
                    timeout=120,
                    request_timeout=self._request_timeout_seconds,
                )
                if result.exit_code != 0:
                    raise RuntimeLimitError("Project archive could not be created.")
                info = await remote.files.get_info(archive_path)
                if info.size > MAX_RUNTIME_ARCHIVE_BYTES:
                    raise RuntimeLimitError("Project archive exceeds the download limit.")
                content = bytes(
                    await remote.files.read(
                        archive_path,
                        format="bytes",
                        request_timeout=self._request_timeout_seconds,
                    )
                )
            finally:
                try:
                    await remote.files.remove(archive_path)
                except E2BFileNotFoundException:
                    pass
        return RuntimeArchive(
            filename=f"{sandbox.sandbox_id or 'project'}.zip",
            content=content,
        )

    async def list_artifacts(
        self, sandbox: RuntimeSandbox
    ) -> tuple[RuntimeArtifact, ...]:
        async with self._lock(sandbox.reference):
            remote = await self._connect_verified(sandbox)
            if not await remote.files.exists(ARTIFACT_ROOT):
                return ()
            entries = await remote.files.list(
                ARTIFACT_ROOT,
                depth=10,
                request_timeout=self._request_timeout_seconds,
            )
        artifacts: list[RuntimeArtifact] = []
        for entry in entries:
            if entry.type != FileType.FILE or entry.size > MAX_RUNTIME_ARTIFACT_BYTES:
                continue
            relative = PurePosixPath(entry.path).relative_to(ARTIFACT_ROOT).as_posix()
            safe = normalize_workspace_path(relative)
            artifact_digest = hashlib.sha256(
                f"{sandbox.sandbox_id}:{safe}".encode("utf-8")
            ).hexdigest()[:32]
            artifacts.append(
                RuntimeArtifact(
                    id=f"artifact_{artifact_digest}",
                    path=f".lunar-forge/artifacts/{safe}",
                    name=PurePosixPath(safe).name,
                    media_type=mimetypes.guess_type(safe)[0]
                    or "application/octet-stream",
                    size_bytes=entry.size,
                )
            )
            if len(artifacts) >= 1_000:
                break
        return tuple(artifacts)

    def _require_client(self) -> E2BClient:
        if self._client is None:
            raise RuntimeUnavailableError(
                "E2B is selected but LUNAR_FORGE_WEB_E2B_API_KEY is not configured."
            )
        return self._client

    async def _connect_verified(self, sandbox: RuntimeSandbox) -> Any:
        self._require_identity(sandbox)
        remote = await self._require_client().connect(sandbox.reference)
        info = await remote.get_info()
        self._validate_identity(sandbox, info.metadata)
        return remote

    @staticmethod
    def _require_identity(sandbox: RuntimeSandbox) -> None:
        if not sandbox.sandbox_id or not sandbox.owner_id or not sandbox.template_id:
            raise RuntimeIdentityError("Sandbox ownership metadata is required.")

    @staticmethod
    def _validate_identity(sandbox: RuntimeSandbox, metadata: dict[str, str]) -> None:
        expected = {
            _METADATA_OWNER: sandbox.owner_id,
            _METADATA_SANDBOX: sandbox.sandbox_id,
            _METADATA_TEMPLATE: sandbox.template_id,
            _METADATA_NETWORK: "deny_all",
        }
        if any(metadata.get(key) != value for key, value in expected.items()):
            raise RuntimeIdentityError("E2B sandbox metadata does not match ownership.")

    @staticmethod
    def _assert_offline(info: Any) -> None:
        network = getattr(info, "network", None) or {}
        denied = set(network.get("deny_out", []))
        allowed = set(network.get("allow_out", []))
        if (
            getattr(info, "allow_internet_access", None) is not False
            or _DENY_ALL not in denied
            or allowed
        ):
            raise RuntimeNetworkPolicyError("E2B sandbox is not deny-all.")

    @asynccontextmanager
    async def _temporary_egress(
        self, remote: Any, hosts: Iterable[str]
    ) -> AsyncIterator[None]:
        selected = sorted(set(hosts))
        await remote.update_network(
            {"allow_out": selected, "deny_out": [_DENY_ALL], "rules": {}}
        )
        info = await remote.get_info()
        network = getattr(info, "network", None) or {}
        if (
            set(network.get("allow_out", [])) != set(selected)
            or _DENY_ALL not in set(network.get("deny_out", []))
        ):
            await self._restore_offline(remote)
            raise RuntimeNetworkPolicyError("E2B did not apply the egress allowlist.")
        try:
            yield
        finally:
            await self._restore_offline(remote)

    async def _restore_offline(self, remote: Any) -> None:
        await remote.update_network(
            {
                "allow_internet_access": False,
                "allow_out": [],
                "deny_out": [_DENY_ALL],
                "rules": {},
            }
        )
        self._assert_offline(await remote.get_info())

    async def _run_command_locked(
        self,
        sandbox: RuntimeSandbox,
        remote: Any,
        command: str,
        *,
        timeout_seconds: int,
    ) -> RuntimeCommandResult:
        command_id = f"cmd_{uuid4().hex}"
        output_path = f"/tmp/{command_id}.out"
        error_path = f"/tmp/{command_id}.err"
        wrapper = (
            "set +e; "
            f"timeout -k 5s {timeout_seconds}s bash -lc \"$LFW_COMMAND\" "
            f"> {shlex.quote(output_path)} 2> {shlex.quote(error_path)}; "
            "code=$?; printf '%s' \"$code\"; exit 0"
        )
        handle = await remote.commands.run(
            wrapper,
            background=True,
            envs={"LFW_COMMAND": command},
            cwd=WORKSPACE_ROOT,
            stdin=False,
            timeout=timeout_seconds + 15,
            request_timeout=self._request_timeout_seconds,
        )
        self._active_commands[sandbox.reference] = handle
        try:
            try:
                wrapper_result = await handle.wait()
                exit_code = int(wrapper_result.stdout or "1")
            except CommandExitException as exc:
                exit_code = exc.exit_code
            stdout, stdout_truncated = await self._read_bounded(
                remote, output_path, MAX_RUNTIME_COMMAND_OUTPUT_CHARACTERS
            )
            stderr, stderr_truncated = await self._read_bounded(
                remote, error_path, MAX_RUNTIME_COMMAND_OUTPUT_CHARACTERS
            )
        finally:
            self._active_commands.pop(sandbox.reference, None)
            for path in (output_path, error_path):
                try:
                    await remote.files.remove(path)
                except E2BFileNotFoundException:
                    pass
        return RuntimeCommandResult(
            command_id=command_id,
            exit_code=exit_code,
            stdout=redact_text(stdout.decode("utf-8", errors="replace")),
            stderr=redact_text(stderr.decode("utf-8", errors="replace")),
            output_truncated=stdout_truncated or stderr_truncated,
        )

    async def _read_bounded(
        self, remote: Any, path: str, limit: int
    ) -> tuple[bytes, bool]:
        reader = await remote.files.read(
            path,
            format="stream",
            request_timeout=self._request_timeout_seconds,
            stream_idle_timeout=self._request_timeout_seconds,
        )
        content = bytearray()
        try:
            async for chunk in reader:
                remaining = (limit + 1) - len(content)
                if len(chunk) > remaining:
                    content.extend(chunk[:remaining])
                    break
                content.extend(chunk)
                if len(content) > limit:
                    break
        finally:
            close = getattr(reader, "aclose", None)
            if close is not None:
                await close()
        return bytes(content[:limit]), len(content) > limit

    def _lock(self, reference: str) -> asyncio.Lock:
        return self._operation_locks.setdefault(reference, asyncio.Lock())

    @staticmethod
    def _validate_command(command: str, timeout_seconds: int) -> None:
        if not command or len(command) > MAX_RUNTIME_COMMAND_CHARACTERS:
            raise RuntimeLimitError("Command exceeds the configured bound.")
        if not 1 <= timeout_seconds <= 15 * 60:
            raise RuntimeLimitError("Command timeout exceeds the turn limit.")
        if _CREDENTIAL_PATTERN.search(command):
            raise RuntimeLimitError("Provider credential material cannot enter E2B.")

    @staticmethod
    def _relative_visible_path(path: str) -> str | None:
        try:
            relative = PurePosixPath(path).relative_to(WORKSPACE_ROOT).as_posix()
        except ValueError:
            return None
        if relative == ".":
            return None
        try:
            return E2BRuntimeProvider._visible_path(relative)
        except ValueError:
            return None

    @staticmethod
    def _visible_path(path: str) -> str:
        normalized = normalize_workspace_path(path)
        parts = PurePosixPath(normalized).parts
        if parts[0] in _HIDDEN_ROOTS or any(part in _SENSITIVE_NAMES for part in parts):
            raise ValueError("Sensitive workspace paths are not browser-readable.")
        return normalized


def _archive_script(archive_path: str) -> str:
    return f"""
import os
import zipfile

root = {WORKSPACE_ROOT!r}
target = {archive_path!r}
excluded = {{'.agent', '.git', '.lunar-forge', '.ssh'}}
total = 0
with zipfile.ZipFile(target, 'w', zipfile.ZIP_DEFLATED) as output:
    for current, directories, files in os.walk(root, followlinks=False):
        directories[:] = [
            name for name in directories
            if name not in excluded and not os.path.islink(os.path.join(current, name))
        ]
        for name in files:
            source = os.path.join(current, name)
            if name in {_SENSITIVE_NAMES!r} or os.path.islink(source):
                continue
            size = os.path.getsize(source)
            total += size
            if total > {MAX_RUNTIME_ARCHIVE_BYTES}:
                raise SystemExit('archive limit exceeded')
            output.write(source, os.path.relpath(source, root))
""".strip()


def _github_size_check_script(owner: str, repository: str) -> str:
    endpoint = f"https://api.github.com/repos/{owner}/{repository}"
    return f"""
import json
import urllib.error
import urllib.request

class NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, 'redirect rejected', headers, fp)

request = urllib.request.Request(
    {endpoint!r},
    headers={{'Accept': 'application/vnd.github+json', 'User-Agent': 'lunar-forge-web'}},
)
with urllib.request.build_opener(NoRedirect).open(request, timeout=15) as response:
    payload = response.read(65537)
if len(payload) > 65536:
    raise SystemExit('GitHub metadata response exceeded bound')
size_kib = int(json.loads(payload)['size'])
if size_kib * 1024 > {MAX_PUBLIC_GIT_CLONE_BYTES}:
    raise SystemExit('repository exceeds clone limit')
""".strip()
