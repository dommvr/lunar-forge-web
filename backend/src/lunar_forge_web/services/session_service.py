from uuid import uuid4

from lunar_forge_web.domain.enums import SessionStatus
from lunar_forge_web.domain.models import SessionResponse
from lunar_forge_web.storage.repositories import SessionRepository


class SessionService:
    def __init__(self, repository: SessionRepository) -> None:
        self._repository = repository

    async def create(self, sandbox_id: str, owner_id: str) -> SessionResponse:
        session = SessionResponse(
            id=f"session_{uuid4().hex}",
            sandbox_id=sandbox_id,
            owner_id=owner_id,
            status=SessionStatus.ACTIVE,
        )
        await self._repository.put(session)
        return session

    async def get(self, session_id: str) -> SessionResponse | None:
        return await self._repository.get(session_id)
