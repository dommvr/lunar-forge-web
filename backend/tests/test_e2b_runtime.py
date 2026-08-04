from __future__ import annotations

import asyncio
import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from types import SimpleNamespace

import pytest
from e2b import FileType

from lunar_forge_web.domain.enums import SandboxStatus
from lunar_forge_web.domain.models import SandboxResponse
from lunar_forge_web.runtime.base import RuntimeSandbox
from lunar_forge_web.runtime.e2b_provider import (
    E2BRuntimeProvider,
    RuntimeIdentityError,
    RuntimeLimitError,
    RuntimeNetworkPolicyError,
    RuntimeUnavailableError,
)
from lunar_forge_web.security.git_urls import (
    UnsafeGitUrlError,
    validate_public_github_url,
)
from lunar_forge_web.services.sandbox_service import MeaningfulActivity, SandboxService
from lunar_forge_web.storage.repositories import InMemorySandboxRepository


@dataclass
class FakeResult:
    stdout: str = ""
    stderr: str = ""
    exit_code: int = 0


class FakeReader:
    def __init__(self, content: bytes) -> None:
        self._chunks = [content[index : index + 8] for index in range(0, len(content), 8)]
        self.closed = False

    def __aiter__(self):
        return self

    async def __anext__(self):
        if not self._chunks:
            raise StopAsyncIteration
        return self._chunks.pop(0)

    async def aclose(self) -> None:
        self.closed = True


class FakeHandle:
    def __init__(self, result: FakeResult, *, blocked: bool = False) -> None:
        self.result = result
        self.killed = False
        self._blocked = blocked
        self._released = asyncio.Event()
        if not blocked:
            self._released.set()

    async def wait(self) -> FakeResult:
        await self._released.wait()
        return self.result

    async def kill(self) -> bool:
        self.killed = True
        self._released.set()
        return True


class FakeFiles:
    def __init__(self) -> None:
        self.data = {
            "/home/user/project/README.md": b"hello\n",
            "/home/user/project/src/main.py": b"print('ok')\n",
            "/home/user/project/.env": b"SECRET=never-return\n",
            "/home/user/project/.lunar-forge/artifacts/report.json": b"{}",
        }
        self.entries = [
            SimpleNamespace(path="/home/user/project/src", type=FileType.DIR, size=0),
            SimpleNamespace(
                path="/home/user/project/README.md", type=FileType.FILE, size=6
            ),
            SimpleNamespace(
                path="/home/user/project/src/main.py", type=FileType.FILE, size=12
            ),
            SimpleNamespace(path="/home/user/project/.env", type=FileType.FILE, size=20),
            SimpleNamespace(
                path="/home/user/project/link",
                type=FileType.SYMLINK,
                size=0,
            ),
            SimpleNamespace(
                path="/home/user/project/.lunar-forge/artifacts/report.json",
                type=FileType.FILE,
                size=2,
            ),
        ]
        self.directories = {"/home/user/project", "/home/user/project/src"}

    async def list(self, path: str, **_):
        if path.endswith("/.lunar-forge/artifacts"):
            return [self.entries[-1]]
        return self.entries

    async def read(self, path: str, *, format: str, **_):
        content = self.data[path]
        if format == "stream":
            return FakeReader(content)
        return bytearray(content)

    async def get_info(self, path: str):
        if path in self.directories:
            return SimpleNamespace(size=0, type=FileType.DIR)
        if path not in self.data:
            from e2b import FileNotFoundException

            raise FileNotFoundException(path)
        return SimpleNamespace(size=len(self.data[path]), type=FileType.FILE)

    async def remove(self, path: str, **_):
        self.data.pop(path, None)
        for nested in tuple(self.data):
            if nested.startswith(path.rstrip("/") + "/"):
                self.data.pop(nested, None)
        self.directories.discard(path)

    async def exists(self, path: str):
        return path in self.data or path in self.directories or any(
            item.startswith(path.rstrip("/") + "/") for item in self.data
        )

    async def write(self, path: str, content: str, **_):
        self.data[path] = content.encode("utf-8")

    async def make_dir(self, path: str, **_):
        self.directories.add(path)

    async def rename(self, source: str, destination: str, **_):
        self.data[destination] = self.data.pop(source)


class FakeCommands:
    def __init__(self, files: FakeFiles) -> None:
        self.files = files
        self.calls: list[tuple[str, dict[str, object]]] = []
        self.started = asyncio.Event()
        self.last_handle: FakeHandle | None = None
        self.checkpoints: dict[str, dict[str, bytes]] = {}

    async def run(self, command: str, **kwargs):
        self.calls.append((command, kwargs))
        if kwargs.get("background"):
            match = re.search(r"> (/tmp/cmd_[a-f0-9]+\.out) 2> (/tmp/cmd_[a-f0-9]+\.err)", command)
            assert match is not None
            supplied = kwargs["envs"]["LFW_COMMAND"]
            self.files.data[match.group(1)] = (
                b"sk-secret-value-is-redacted\n" if supplied == "show secret" else b"done\n"
            )
            self.files.data[match.group(2)] = b""
            self.last_handle = FakeHandle(
                FakeResult(stdout="0"), blocked=supplied == "sleep forever"
            )
            self.started.set()
            return self.last_handle
        archive = re.search(r"/tmp/lf-project-[a-f0-9]+\.zip", command)
        if archive:
            self.files.data[archive.group(0)] = b"PK\x03\x04bounded"
        checkpoint = re.search(r"/tmp/checkpoint_[a-f0-9]+", command)
        if checkpoint and "shutil.copytree" in command and "filecmp" not in command:
            self.checkpoints[checkpoint.group(0)] = dict(self.files.data)
        if checkpoint and "filecmp" in command:
            before = self.checkpoints[checkpoint.group(0)]
            current = self.files.data
            restored = [path.removeprefix("/home/user/project/") for path in before if current.get(path) != before[path]]
            removed = [path.removeprefix("/home/user/project/") for path in current if path not in before and path.startswith("/home/user/project/")]
            self.files.data = dict(before)
            return FakeResult(
                stdout=json.dumps(
                    {
                        "status": "completed",
                        "restored_files": restored,
                        "removed_files": removed,
                        "skipped_files": [],
                        "errors": [],
                    }
                )
            )
        return FakeResult()


class FakeRemote:
    def __init__(self, sandbox_id: str, metadata: dict[str, str]) -> None:
        self.sandbox_id = sandbox_id
        self.files = FakeFiles()
        self.commands = FakeCommands(self.files)
        now = datetime.now(timezone.utc)
        self.info = SimpleNamespace(
            metadata=metadata,
            allow_internet_access=False,
            network={
                "allow_out": [],
                "deny_out": ["0.0.0.0/0"],
                "allow_public_traffic": False,
            },
            lifecycle={"on_timeout": "kill", "auto_resume": False},
            state=SimpleNamespace(value="running"),
            started_at=now,
            end_at=now + timedelta(minutes=30),
            cpu_count=2,
            memory_mb=2048,
            disk_size_mb=4096,
        )
        self.timeout_updates: list[int] = []
        self.network_updates: list[dict[str, object]] = []

    async def get_info(self):
        return self.info

    async def set_timeout(self, seconds: int):
        self.timeout_updates.append(seconds)

    async def update_network(self, update: dict[str, object]):
        self.network_updates.append(update)
        if update.get("allow_internet_access") is False:
            self.info.allow_internet_access = False
        else:
            self.info.allow_internet_access = None
        self.info.network = {
            "allow_out": list(update.get("allow_out", [])),
            "deny_out": list(update.get("deny_out", [])),
            "allow_public_traffic": False,
        }


class FakeE2BClient:
    def __init__(self) -> None:
        self.create_kwargs: dict[str, object] | None = None
        self.remote: FakeRemote | None = None
        self.killed: list[str] = []

    async def create(self, **kwargs):
        self.create_kwargs = kwargs
        self.remote = FakeRemote("e2b-sandbox-1", kwargs["metadata"])
        return self.remote

    async def connect(self, sandbox_id: str):
        assert self.remote is not None and sandbox_id == self.remote.sandbox_id
        return self.remote

    async def kill(self, sandbox_id: str):
        self.killed.append(sandbox_id)
        return True


def provider(client: FakeE2BClient) -> E2BRuntimeProvider:
    return E2BRuntimeProvider(
        api_key="not-used-by-injected-client",
        template_ids={"python-cli": "lfw-python-cli-v1"},
        client=client,
    )


async def create_runtime(client: FakeE2BClient) -> tuple[E2BRuntimeProvider, RuntimeSandbox]:
    selected = provider(client)
    runtime = await selected.create(
        owner_id="user-a", sandbox_id="sandbox-a", template_id="python-cli"
    )
    return selected, runtime


async def test_create_is_secure_offline_kill_on_timeout_and_secret_free():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)

    assert runtime.reference == "e2b-sandbox-1"
    assert client.create_kwargs == {
        "template": "lfw-python-cli-v1",
        "timeout": 1800,
        "metadata": {
            "lfw_owner_id": "user-a",
            "lfw_sandbox_id": "sandbox-a",
            "lfw_template_id": "python-cli",
            "lfw_network_policy": "deny_all",
        },
        "envs": {},
        "secure": True,
        "allow_internet_access": False,
        "network": {"deny_out": ["0.0.0.0/0"], "allow_public_traffic": False},
        "lifecycle": {"on_timeout": "kill", "auto_resume": False},
    }
    capability = selected.capability()
    assert capability.supports_temporary_egress is True
    assert capability.supports_public_git_clone is True
    assert capability.inactivity_ttl_seconds == 1800


async def test_connect_status_ttl_identity_and_delete_contract():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)

    assert (await selected.status(runtime)).internet_access is False
    await selected.extend_timeout(runtime, 1800)
    assert client.remote.timeout_updates == [1800]
    with pytest.raises(RuntimeLimitError):
        await selected.extend_timeout(runtime, 3600)
    client.remote.info.metadata["lfw_owner_id"] = "user-b"
    with pytest.raises(RuntimeIdentityError):
        await selected.connect(runtime)
    client.remote.info.metadata["lfw_owner_id"] = "user-a"
    await selected.terminate(runtime)
    assert client.killed == [runtime.reference]


async def test_meaningful_activity_extends_provider_and_metadata_but_heartbeat_does_not():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)
    now = datetime.now(timezone.utc)
    repository = InMemorySandboxRepository(
        (
            SandboxResponse(
                id="sandbox-a",
                owner_id="user-a",
                template_id="python-cli",
                runtime_provider="e2b",
                runtime_reference=runtime.reference,
                status=SandboxStatus.READY,
                created_at=now,
                last_activity_at=now,
                expires_at=now + timedelta(minutes=30),
            ),
        )
    )
    service = SandboxService(repository, selected)
    activity_at = now + timedelta(minutes=5)

    extended = await service.record_activity(
        "sandbox-a", MeaningfulActivity.FILE_INTERACTION, now=activity_at
    )
    assert extended.expires_at == activity_at + timedelta(minutes=30)
    assert client.remote.timeout_updates == [1800]
    with pytest.raises(ValueError, match="Passive heartbeats"):
        await service.record_activity("sandbox-a", "heartbeat", now=activity_at)  # type: ignore[arg-type]
    assert client.remote.timeout_updates == [1800]


async def test_commands_are_bounded_redacted_and_cancellable():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)

    result = await selected.run_command(runtime, "show secret", timeout_seconds=30)
    assert result.stdout == "[REDACTED]\n"
    assert result.exit_code == 0
    with pytest.raises(RuntimeLimitError):
        await selected.run_command(runtime, "OPENAI_API_KEY=bad", timeout_seconds=30)

    client.remote.commands.started.clear()
    task = asyncio.create_task(
        selected.run_command(runtime, "sleep forever", timeout_seconds=30)
    )
    await client.remote.commands.started.wait()
    assert await selected.cancel_active_command(runtime) is True
    await task
    assert client.remote.commands.last_handle.killed is True


async def test_files_archive_and_artifacts_are_safe_and_bounded():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)

    files = await selected.list_files(runtime)
    assert [item.path for item in files] == ["README.md", "src", "src/main.py"]
    content = await selected.read_file(runtime, "README.md")
    assert content.content == "hello\n"
    with pytest.raises(ValueError):
        await selected.read_file(runtime, ".env")
    archive = await selected.archive_project(runtime)
    assert archive.content.startswith(b"PK")
    artifacts = await selected.list_artifacts(runtime)
    assert [(item.name, item.media_type) for item in artifacts] == [
        ("report.json", "application/json")
    ]


async def test_public_core_runtime_operations_and_confirmed_rollback():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)

    assert [item.path for item in await selected.core_list_directory(runtime, ".")] == [
        "README.md",
        "src",
    ]
    assert (await selected.core_stat(runtime, "README.md")).size_bytes == 6
    assert (
        await selected.core_read_text(
            runtime,
            "README.md",
            start_line=1,
            end_line=None,
            max_characters=50_000,
        )
    ).content == "hello\n"
    checkpoint = await selected.core_checkpoint_turn(runtime, "turn-test")
    assert checkpoint.supported is True and checkpoint.checkpoint_id is not None
    written = await selected.core_write_text(
        runtime, "created.txt", "new\n", overwrite=False
    )
    assert written.created is True
    moved = await selected.core_move_path(
        runtime, "created.txt", "moved.txt", overwrite=False
    )
    assert moved.ok is True
    rollback = await selected.core_rollback_turn(runtime, checkpoint.checkpoint_id)
    assert rollback.status.value == "completed"
    assert "moved.txt" in rollback.removed_files


async def test_public_git_clone_uses_atomic_allowlist_and_restores_deny_all():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)

    result = await selected.clone_public_git(
        runtime, "https://github.com/openai/example.git"
    )
    assert result.exit_code == 0
    assert client.remote.network_updates[0] == {
        "allow_out": ["api.github.com", "github.com"],
        "deny_out": ["0.0.0.0/0"],
        "rules": {},
    }
    assert client.remote.network_updates[-1] == {
        "allow_internet_access": False,
        "allow_out": [],
        "deny_out": ["0.0.0.0/0"],
        "rules": {},
    }
    assert client.remote.info.allow_internet_access is False


async def test_approved_package_install_uses_operation_specific_allowlist():
    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)

    result = await selected.run_approved_network_command(
        runtime,
        "python -m pip install requests==2.32.4",
        operation="pip",
        timeout_seconds=60,
    )
    assert result.exit_code == 0
    assert client.remote.network_updates[0]["allow_out"] == [
        "files.pythonhosted.org",
        "pypi.org",
    ]
    assert client.remote.network_updates[-1]["deny_out"] == ["0.0.0.0/0"]


def test_public_git_url_validation_rejects_credentials_redirect_hosts_and_ssrf():
    assert validate_public_github_url("https://github.com/openai/example").url == (
        "https://github.com/openai/example.git"
    )
    for value in (
        "http://github.com/openai/example",
        "https://user:secret@github.com/openai/example",
        "https://github.com.evil.test/openai/example",
        "https://127.0.0.1/openai/example",
        "file:///tmp/example",
        "https://github.com/openai/example?token=secret",
    ):
        with pytest.raises(UnsafeGitUrlError):
            validate_public_github_url(value)


async def test_missing_api_key_and_unverified_network_fail_closed():
    unavailable = E2BRuntimeProvider(
        api_key=None,
        template_ids={"python-cli": "lfw-python-cli-v1"},
    )
    assert unavailable.capability().status == "unavailable"
    with pytest.raises(RuntimeUnavailableError):
        await unavailable.create(
            owner_id="user-a", sandbox_id="sandbox-a", template_id="python-cli"
        )

    client = FakeE2BClient()
    selected, runtime = await create_runtime(client)
    client.remote.info.allow_internet_access = True
    client.remote.info.network = {"allow_out": [], "deny_out": []}
    with pytest.raises(RuntimeNetworkPolicyError):
        await selected.status(runtime)
