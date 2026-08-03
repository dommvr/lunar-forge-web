from datetime import datetime, timedelta, timezone
from enum import StrEnum
from uuid import uuid4

from lunar_forge_web.domain.enums import SandboxStatus
from lunar_forge_web.domain.models import SandboxResponse
from lunar_forge_web.runtime.base import RuntimeProvider, RuntimeSandbox
from lunar_forge_web.security.limits import SANDBOX_INACTIVITY_TTL_SECONDS
from lunar_forge_web.storage.repositories import (
    AdminSettingsRepository,
    RepositoryConflictError,
    SandboxRepository,
)


class SandboxCreationDisabledError(RepositoryConflictError):
    pass


class MeaningfulActivity(StrEnum):
    TURN_SENT = "turn_sent"
    APPROVAL_RESOLVED = "approval_resolved"
    AGENT_PROGRESS = "agent_progress"
    PREVIEW_OPENED = "preview_opened"
    FILE_INTERACTION = "file_interaction"


_MEANINGFUL_ACTIVITIES = frozenset(MeaningfulActivity)


class SandboxService:
    def __init__(
        self,
        repository: SandboxRepository,
        runtime: RuntimeProvider,
        admin_settings: AdminSettingsRepository | None = None,
    ) -> None:
        self._repository = repository
        self._runtime = runtime
        self._admin_settings = admin_settings

    async def create(self, owner_id: str, template_id: str) -> SandboxResponse:
        if self._admin_settings is not None:
            settings = await self._admin_settings.get()
            if settings.sandbox_kill_switch_enabled:
                raise SandboxCreationDisabledError("Sandbox creation is disabled.")
        now = datetime.now(timezone.utc)
        sandbox_id = f"sandbox_{uuid4().hex}"
        runtime = await self._runtime.create(
            owner_id=owner_id,
            sandbox_id=sandbox_id,
            template_id=template_id,
        )
        sandbox = SandboxResponse(
            id=sandbox_id,
            owner_id=owner_id,
            template_id=template_id,
            runtime_provider=runtime.provider,
            runtime_reference=runtime.reference,
            status=SandboxStatus.READY,
            created_at=now,
            last_activity_at=now,
            expires_at=now + timedelta(seconds=SANDBOX_INACTIVITY_TTL_SECONDS),
        )
        try:
            await self._repository.put(sandbox)
        except Exception:
            await self._runtime.terminate(runtime)
            raise
        return sandbox

    async def get(self, sandbox_id: str) -> SandboxResponse | None:
        return await self._repository.get(sandbox_id)

    async def record_activity(
        self,
        sandbox_id: str,
        activity: MeaningfulActivity,
        *,
        now: datetime | None = None,
    ) -> SandboxResponse | None:
        if activity not in _MEANINGFUL_ACTIVITIES:
            raise ValueError("Passive heartbeats do not extend sandbox lifetime.")
        activity_at = now or datetime.now(timezone.utc)
        sandbox = await self._repository.get(sandbox_id)
        if sandbox is None or sandbox.runtime_reference is None:
            return None
        await self._runtime.extend_timeout(
            runtime_sandbox(sandbox), SANDBOX_INACTIVITY_TTL_SECONDS
        )
        return await self._repository.extend_activity(
            sandbox_id,
            activity_at,
            activity_at + timedelta(seconds=SANDBOX_INACTIVITY_TTL_SECONDS),
        )

    async def reset(self, sandbox: SandboxResponse) -> SandboxResponse:
        runtime = await self._runtime.reset(runtime_sandbox(sandbox))
        now = datetime.now(timezone.utc)
        reset = sandbox.model_copy(
            update={
                "runtime_provider": runtime.provider,
                "runtime_reference": runtime.reference,
                "status": SandboxStatus.READY,
                "last_activity_at": now,
                "expires_at": now
                + timedelta(seconds=SANDBOX_INACTIVITY_TTL_SECONDS),
            }
        )
        await self._repository.put(reset)
        return reset

    async def delete(self, sandbox: SandboxResponse) -> None:
        if sandbox.runtime_reference is not None:
            await self._runtime.terminate(runtime_sandbox(sandbox))
        await self._repository.delete(sandbox.id)


def runtime_sandbox(sandbox: SandboxResponse) -> RuntimeSandbox:
    if sandbox.runtime_reference is None:
        raise RuntimeError("Sandbox runtime reference is unavailable.")
    return RuntimeSandbox(
        provider=sandbox.runtime_provider,
        reference=sandbox.runtime_reference,
        workspace_root=(
            "/home/user/project" if sandbox.runtime_provider == "e2b" else "/workspace"
        ),
        sandbox_id=sandbox.id,
        owner_id=sandbox.owner_id,
        template_id=sandbox.template_id,
    )
