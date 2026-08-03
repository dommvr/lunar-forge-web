from fastapi import APIRouter

from lunar_forge_web.api.dependencies import CurrentPrincipal
from lunar_forge_web.api.errors import ERROR_RESPONSES
from lunar_forge_web.domain.models import MeResponse


router = APIRouter(tags=["identity"])


@router.get("/me", response_model=MeResponse, responses=ERROR_RESPONSES)
async def me(principal: CurrentPrincipal) -> MeResponse:
    return MeResponse(user=principal)
