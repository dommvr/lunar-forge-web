from fastapi import APIRouter, Query, Response, status

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
from lunar_forge_web.services.sandbox_service import (
    MeaningfulActivity,
    SandboxCreationDisabledError,
    SandboxService,
    runtime_sandbox,
)
from lunar_forge_web.storage.repositories import RepositoryConflictError
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
    try:
        return await SandboxService(
            container.sandboxes,
            container.runtime,
            container.admin_settings,
        ).create(principal.id, body.template_id)
    except SandboxCreationDisabledError as exc:
        raise ApiError(503, "sandbox_kill_switch", str(exc)) from exc
    except RepositoryConflictError as exc:
        raise ApiError(409, "active_sandbox_limit", str(exc)) from exc


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
    session_ids = tuple(
        item.id for item in await container.sessions.list_for_sandbox(sandbox.id)
    )
    reset = await SandboxService(
        container.sandboxes, container.runtime
    ).reset(sandbox)
    await FakeFlowService(
        container.fake_flows,
        container.events,
        container.sessions,
    ).clear_sandbox(sandbox.id)
    if container.coordination is not None:
        await container.coordination.clear_sandbox(sandbox.id, session_ids)
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
    session_ids = tuple(
        item.id for item in await container.sessions.list_for_sandbox(sandbox.id)
    )
    if sandbox.runtime_reference is not None:
        await container.runtime.terminate(runtime_sandbox(sandbox))
    await FakeFlowService(
        container.fake_flows,
        container.events,
        container.sessions,
    ).clear_sandbox(sandbox.id)
    if container.coordination is not None:
        await container.coordination.clear_sandbox(sandbox.id, session_ids)
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
    if sandbox.runtime_provider == "fake":
        response = FakeFlowService(
            container.fake_flows,
            container.events,
            container.sessions,
        ).files(sandbox)
    else:
        items = await container.runtime.list_files(runtime_sandbox(sandbox))
        response = FilesResponse(
            sandbox_id=sandbox.id,
            items=[
                {
                    "path": item.path,
                    "kind": item.kind,
                    "size_bytes": item.size_bytes,
                }
                for item in items
            ],
            truncated=len(items) >= 10_000,
        )
    await SandboxService(container.sandboxes, container.runtime).record_activity(
        sandbox.id, MeaningfulActivity.FILE_INTERACTION
    )
    return response


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
        if sandbox.runtime_provider == "fake":
            response = FakeFlowService(
                container.fake_flows,
                container.events,
                container.sessions,
            ).file_content(sandbox, path)
        else:
            content = await container.runtime.read_file(
                runtime_sandbox(sandbox), path
            )
            response = FileContentResponse(
                sandbox_id=sandbox.id,
                path=content.path,
                content=content.content,
                truncated=content.truncated,
            )
        await SandboxService(container.sandboxes, container.runtime).record_activity(
            sandbox.id, MeaningfulActivity.FILE_INTERACTION
        )
        return response
    except FakeFlowNotFoundError as exc:
        raise ApiError(404, "file_not_found", "File was not found.") from exc
    except FileNotFoundError as exc:
        raise ApiError(404, "file_not_found", "File was not found.") from exc
    except ValueError as exc:
        raise ApiError(400, "invalid_file_path", "File path is invalid.") from exc


@router.post(
    "/sandboxes/{sandbox_id}/download",
    response_class=Response,
    responses=ERROR_RESPONSES,
)
async def download_sandbox(
    sandbox: OwnedSandbox,
    container: ContainerDep,
) -> Response:
    archive = await container.runtime.archive_project(runtime_sandbox(sandbox))
    if len(archive.content) > container.settings.max_response_body_bytes:
        raise ApiError(
            413,
            "project_download_too_large",
            "Project archive exceeds the configured response bound.",
        )
    await SandboxService(container.sandboxes, container.runtime).record_activity(
        sandbox.id, MeaningfulActivity.FILE_INTERACTION
    )
    return Response(
        content=archive.content,
        media_type="application/zip",
        headers={
            "Content-Disposition": f'attachment; filename="{archive.filename}"',
        },
    )
