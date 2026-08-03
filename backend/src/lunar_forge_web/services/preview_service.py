from typing import Protocol

from lunar_forge_web.domain.models import PreviewResponse


class PreviewRepository(Protocol):
    async def get(self, preview_id: str) -> PreviewResponse | None: ...


class PreviewService:
    def __init__(self, repository: PreviewRepository) -> None:
        self._repository = repository

    async def get(self, preview_id: str) -> PreviewResponse | None:
        return await self._repository.get(preview_id)
