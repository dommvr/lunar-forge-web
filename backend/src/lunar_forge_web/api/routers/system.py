from fastapi import APIRouter

from lunar_forge_web import __version__
from lunar_forge_web.api.dependencies import ContainerDep
from lunar_forge_web.domain.models import (
    CapabilitiesResponse,
    HealthResponse,
    TemplatesResponse,
    VersionResponse,
)


router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health(container: ContainerDep) -> HealthResponse:
    return HealthResponse(
        service="api",
        environment=container.settings.environment.value,
    )


@router.get("/version", response_model=VersionResponse)
async def version(container: ContainerDep) -> VersionResponse:
    settings = container.settings
    return VersionResponse(
        api_version=settings.api_version,
        backend_version=__version__,
        core_version=settings.core_version,
        event_schema_version=settings.event_schema_version,
    )


@router.get("/capabilities", response_model=CapabilitiesResponse)
async def capabilities(container: ContainerDep) -> CapabilitiesResponse:
    settings = container.settings
    return CapabilitiesResponse(
        api_version=settings.api_version,
        core_version=settings.core_version,
        event_schema_version=settings.event_schema_version,
        runtimes=[container.runtime.capability()],
        features=list(container.features),
    )


@router.get("/templates", response_model=TemplatesResponse)
async def templates(container: ContainerDep) -> TemplatesResponse:
    return TemplatesResponse(items=list(container.templates))
