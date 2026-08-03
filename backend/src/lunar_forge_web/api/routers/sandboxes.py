from datetime import datetime, timezone

from fastapi import APIRouter, Query, status

from lunar_forge_web.api.dependencies import (
    ContainerDep,
    CurrentPrincipal,
    OwnedSandbox,
)
from lunar_forge_web.api.errors import ERROR_RESPONSES, ApiError
from lunar_forge_web.domain.models import (
    SandboxCreateRequest,
    SandboxDeleteResponse,
    FileContentResponse,
    FilesResponse,
    SandboxResponse,
    SandboxesResponse,
)
from lunar_forge_web.services.sandbox_service import SandboxService
from lunar_forge_web.services.fake_flow_service import (
    FakeFlowNotFoundError,
    FakeFlowService,
)


router = APIRouter(tags=["sandboxes"])


@router.post(
    "/sandboxes",
    response_model=SandboxResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_sandbox(
    body: SandboxCreateRequest,
    principal: CurrentPrincipal,
    container: ContainerDep,
) -> SandboxResponse:
    if body.template_id not in {item.id for item in container.templates}:
        raise ApiError(422, "template_not_found", "Template was not found.")
    return await SandboxService(container.sandboxes, container.runtime).create(
        principal.id,
        body.template_id,
    )


@router.get("/sandboxes", response_model=SandboxesResponse, responses=ERROR_RESPONSES)
async def list_sandboxes(
    principal: CurrentPrincipal,
    container: ContainerDep,
) -> SandboxesResponse:
    return SandboxesResponse(
        items=list(await container.sandboxes.list_for_owner(principal.id))
    )


@router.get(
    "/sandboxes/{sandbox_id}",
    response_model=SandboxResponse,
    responses=ERROR_RESPONSES,
)
async def get_sandbox(sandbox: OwnedSandbox) -> SandboxResponse:
    return sandbox


@router.post(
    "/sandboxes/{sandbox_id}/reset",
    response_model=SandboxResponse,
    responses=ERROR_RESPONSES,
)
async def reset_sandbox(
    sandbox: OwnedSandbox,
    container: ContainerDep,
) -> SandboxResponse:
    await FakeFlowService(
        container.fake_flows,
        container.events,
        container.sessions,
    ).clear_sandbox(sandbox.id)
    now = datetime.now(timezone.utc)
    reset = sandbox.model_copy(
        update={"status": "ready", "last_activity_at": now}
    )
    await container.sandboxes.put(reset)
    return reset


@router.delete(
    "/sandboxes/{sandbox_id}",
    response_model=SandboxDeleteResponse,
    responses=ERROR_RESPONSES,
)
async def delete_sandbox(
    sandbox: OwnedSandbox,
    container: ContainerDep,
) -> SandboxDeleteResponse:
    await FakeFlowService(
        container.fake_flows,
        container.events,
        container.sessions,
    ).clear_sandbox(sandbox.id)
    await container.sandboxes.delete(sandbox.id)
    return SandboxDeleteResponse(sandbox_id=sandbox.id)


@router.get(
    "/sandboxes/{sandbox_id}/files",
    response_model=FilesResponse,
    responses=ERROR_RESPONSES,
)
async def list_files(
    sandbox: OwnedSandbox,
    container: ContainerDep,
) -> FilesResponse:
    return FakeFlowService(
        container.fake_flows,
        container.events,
        container.sessions,
    ).files(sandbox)


@router.get(
    "/sandboxes/{sandbox_id}/file",
    response_model=FileContentResponse,
    responses=ERROR_RESPONSES,
)
async def get_file(
    sandbox: OwnedSandbox,
    container: ContainerDep,
    path: str = Query(min_length=1, max_length=4_096),
) -> FileContentResponse:
    try:
        return FakeFlowService(
            container.fake_flows,
            container.events,
            container.sessions,
        ).file_content(sandbox, path)
    except FakeFlowNotFoundError as exc:
        raise ApiError(404, "file_not_found", "File was not found.") from exc
