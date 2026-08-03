from fastapi import APIRouter

from lunar_forge_web.api.dependencies import AdminPrincipal
from lunar_forge_web.api.errors import ERROR_RESPONSES
from lunar_forge_web.domain.models import AdminOverviewResponse
from lunar_forge_web.services.admin_service import AdminService


router = APIRouter(tags=["admin"])


@router.get(
    "/admin/overview",
    response_model=AdminOverviewResponse,
    responses=ERROR_RESPONSES,
)
async def overview(principal: AdminPrincipal) -> AdminOverviewResponse:
    del principal
    return AdminService().empty_overview()
