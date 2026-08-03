from fastapi import APIRouter

from lunar_forge_web.api.dependencies import AdminPrincipal, ContainerDep
from lunar_forge_web.api.errors import ERROR_RESPONSES
from lunar_forge_web.domain.models import (
    AdminOverviewResponse,
    AdminSettingsPatch,
    AdminSettingsResponse,
)
from lunar_forge_web.services.admin_service import AdminService


router = APIRouter(tags=["admin"])


@router.get(
    "/admin/overview",
    response_model=AdminOverviewResponse,
    responses=ERROR_RESPONSES,
)
async def overview(
    principal: AdminPrincipal, container: ContainerDep
) -> AdminOverviewResponse:
    del principal
    response = AdminService().empty_overview()
    settings = await container.admin_settings.get()
    return response.model_copy(
        update={
            "sandbox_kill_switch_enabled": settings.sandbox_kill_switch_enabled,
            "owner_funded_enabled": settings.owner_funded_enabled,
        }
    )


@router.get(
    "/admin/settings",
    response_model=AdminSettingsResponse,
    responses=ERROR_RESPONSES,
)
async def get_settings(
    principal: AdminPrincipal, container: ContainerDep
) -> AdminSettingsResponse:
    del principal
    return await AdminService(container.admin_settings).get_settings()


@router.patch(
    "/admin/settings",
    response_model=AdminSettingsResponse,
    responses=ERROR_RESPONSES,
)
async def update_settings(
    body: AdminSettingsPatch,
    principal: AdminPrincipal,
    container: ContainerDep,
) -> AdminSettingsResponse:
    del principal
    return await AdminService(container.admin_settings).update_settings(
        sandbox_kill_switch_enabled=body.sandbox_kill_switch_enabled,
        owner_funded_enabled=body.owner_funded_enabled,
    )


@router.post(
    "/admin/kill-switch/enable",
    response_model=AdminSettingsResponse,
    responses=ERROR_RESPONSES,
)
async def enable_kill_switch(
    principal: AdminPrincipal, container: ContainerDep
) -> AdminSettingsResponse:
    del principal
    return await AdminService(container.admin_settings).update_settings(
        sandbox_kill_switch_enabled=True
    )


@router.post(
    "/admin/kill-switch/disable",
    response_model=AdminSettingsResponse,
    responses=ERROR_RESPONSES,
)
async def disable_kill_switch(
    principal: AdminPrincipal, container: ContainerDep
) -> AdminSettingsResponse:
    del principal
    return await AdminService(container.admin_settings).update_settings(
        sandbox_kill_switch_enabled=False
    )
