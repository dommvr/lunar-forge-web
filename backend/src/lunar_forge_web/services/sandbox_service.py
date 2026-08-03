from datetime import datetime, timedelta, timezone
from uuid import uuid4

from lunar_forge_web.domain.enums import SandboxStatus
from lunar_forge_web.domain.models import SandboxResponse
from lunar_forge_web.runtime.base import RuntimeProvider
from lunar_forge_web.storage.repositories import SandboxRepository


class SandboxService:
    def __init__(self, repository: SandboxRepository, runtime: RuntimeProvider) -> None:
        self._repository = repository
        self._runtime = runtime

    async def create(self, owner_id: str, template_id: str) -> SandboxResponse:
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
            expires_at=now + timedelta(minutes=30),
        )
        await self._repository.put(sandbox)
        return sandbox

    async def get(self, sandbox_id: str) -> SandboxResponse | None:
        return await self._repository.get(sandbox_id)
