"""FastAPI dependencies for identity, role, and ownership."""

from __future__ import annotations

from typing import Annotated

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lunar_forge_web.api.errors import ApiError
from lunar_forge_web.auth.authorization import (
    can_access_owned_resource,
    is_mfa_verified_admin,
)
from lunar_forge_web.auth.supabase import JWTValidationError
from lunar_forge_web.container import ApplicationContainer
from lunar_forge_web.domain.base import Identifier
from lunar_forge_web.domain.enums import AssuranceLevel, UserRole
from lunar_forge_web.domain.models import Principal, SandboxResponse, SessionResponse


bearer = HTTPBearer(auto_error=False)


def get_container(request: Request) -> ApplicationContainer:
    return request.app.state.container


ContainerDep = Annotated[ApplicationContainer, Depends(get_container)]


async def get_current_principal(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(bearer)],
    container: ContainerDep,
) -> Principal:
    if credentials is None or credentials.scheme.lower() != "bearer":
        raise ApiError(401, "authentication_required", "Authentication is required.")
    try:
        claims = await container.jwt_verifier.verify(credentials.credentials)
    except JWTValidationError as exc:
        raise ApiError(401, "invalid_token", "Bearer token is invalid.") from exc
    user = await container.users.get(claims.subject)
    if user is None:
        raise ApiError(403, "account_not_provisioned", "Account is not provisioned.")
    if user.suspended:
        raise ApiError(403, "account_suspended", "Account is suspended.")
    return Principal(
        id=user.id,
        email=user.email,
        role=user.role,
        suspended=user.suspended,
        assurance_level=claims.assurance_level,
    )


CurrentPrincipal = Annotated[Principal, Depends(get_current_principal)]


async def require_admin(principal: CurrentPrincipal) -> Principal:
    if principal.role != UserRole.ADMIN.value:
        raise ApiError(403, "admin_required", "Administrator access is required.")
    if principal.assurance_level != AssuranceLevel.AAL2.value:
        raise ApiError(403, "admin_mfa_required", "Administrator MFA is required.")
    if not is_mfa_verified_admin(principal):
        raise ApiError(403, "admin_required", "Administrator access is required.")
    return principal


AdminPrincipal = Annotated[Principal, Depends(require_admin)]


async def get_owned_sandbox(
    sandbox_id: Identifier,
    principal: CurrentPrincipal,
    container: ContainerDep,
) -> SandboxResponse:
    sandbox = await container.sandboxes.get(sandbox_id)
    if sandbox is None or not can_access_owned_resource(principal, sandbox.owner_id):
        raise ApiError(404, "sandbox_not_found", "Sandbox was not found.")
    return sandbox


OwnedSandbox = Annotated[SandboxResponse, Depends(get_owned_sandbox)]


async def get_owned_session(
    session_id: Identifier,
    principal: CurrentPrincipal,
    container: ContainerDep,
) -> SessionResponse:
    session = await container.sessions.get(session_id)
    if session is None or not can_access_owned_resource(principal, session.owner_id):
        raise ApiError(404, "session_not_found", "Session was not found.")
    return session


OwnedSession = Annotated[SessionResponse, Depends(get_owned_session)]
