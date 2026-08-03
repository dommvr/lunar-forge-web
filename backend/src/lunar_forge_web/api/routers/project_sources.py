"""Bounded public project-source validation."""

from fastapi import APIRouter

from lunar_forge_web.api.dependencies import ContainerDep, CurrentPrincipal
from lunar_forge_web.api.errors import ERROR_RESPONSES, ApiError
from lunar_forge_web.domain.models import (
    PublicGitValidateRequest,
    PublicGitValidateResponse,
)
from lunar_forge_web.security.git_urls import (
    UnsafeGitUrlError,
    validate_public_github_url,
)


router = APIRouter(tags=["project_sources"])


@router.post(
    "/project-sources/public-git/validate",
    response_model=PublicGitValidateResponse,
    responses=ERROR_RESPONSES,
)
async def validate_public_git(
    body: PublicGitValidateRequest,
    principal: CurrentPrincipal,
    container: ContainerDep,
) -> PublicGitValidateResponse:
    del principal
    try:
        repository = validate_public_github_url(body.url)
    except UnsafeGitUrlError as exc:
        raise ApiError(422, "invalid_repository_url", str(exc)) from exc
    return PublicGitValidateResponse(
        canonical_url=repository.url,
        owner=repository.owner,
        repository=repository.repository,
        clone_supported=container.runtime.capability().supports_public_git_clone,
    )
