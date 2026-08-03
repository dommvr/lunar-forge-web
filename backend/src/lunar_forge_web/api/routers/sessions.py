from fastapi import APIRouter, Query, status

from lunar_forge_web.api.dependencies import ContainerDep, OwnedSandbox, OwnedSession
from lunar_forge_web.api.errors import ERROR_RESPONSES
from lunar_forge_web.api.errors import ApiError
from lunar_forge_web.domain.models import (
    ApprovalResolutionRequest,
    ApprovalResponse,
    ArtifactsResponse,
    CancelResponse,
    CompactionResponse,
    EventReplayResponse,
    SessionCreateRequest,
    SessionResponse,
    TurnCreateRequest,
    TurnResponse,
)
from lunar_forge_web.services.fake_flow_service import (
    FakeFlowNotFoundError,
    FakeFlowService,
    FakeFlowStateError,
)
from lunar_forge_web.services.session_service import SessionService


router = APIRouter(tags=["sessions"])


@router.post(
    "/sandboxes/{sandbox_id}/sessions",
    response_model=SessionResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_session(
    body: SessionCreateRequest,
    sandbox: OwnedSandbox,
    container: ContainerDep,
) -> SessionResponse:
    del body
    session = await SessionService(container.sessions).create(
        sandbox.id,
        sandbox.owner_id,
    )
    await FakeFlowService(
        container.fake_flows,
        container.events,
        container.sessions,
    ).session_started(session)
    return session


@router.get(
    "/sessions/{session_id}",
    response_model=SessionResponse,
    responses=ERROR_RESPONSES,
)
async def get_session(session: OwnedSession) -> SessionResponse:
    return session


def fake_flow(container: ContainerDep) -> FakeFlowService:
    return FakeFlowService(
        container.fake_flows,
        container.events,
        container.sessions,
    )


@router.post(
    "/sessions/{session_id}/turns",
    response_model=TurnResponse,
    status_code=status.HTTP_202_ACCEPTED,
    responses=ERROR_RESPONSES,
)
async def create_turn(
    body: TurnCreateRequest,
    session: OwnedSession,
    container: ContainerDep,
) -> TurnResponse:
    sandbox = await container.sandboxes.get(session.sandbox_id)
    if sandbox is None:
        raise ApiError(404, "sandbox_not_found", "Sandbox was not found.")
    try:
        return await fake_flow(container).submit_turn(session, sandbox, body)
    except FakeFlowStateError as exc:
        raise ApiError(409, "turn_conflict", str(exc)) from exc


@router.post(
    "/sessions/{session_id}/approvals/{approval_id}",
    response_model=ApprovalResponse,
    responses=ERROR_RESPONSES,
)
async def resolve_approval(
    approval_id: str,
    body: ApprovalResolutionRequest,
    session: OwnedSession,
    container: ContainerDep,
) -> ApprovalResponse:
    try:
        return await fake_flow(container).resolve_approval(
            session,
            approval_id,
            body.approved,
        )
    except FakeFlowNotFoundError as exc:
        raise ApiError(404, "approval_not_found", "Approval was not found.") from exc
    except FakeFlowStateError as exc:
        raise ApiError(409, "approval_already_resolved", str(exc)) from exc


@router.post(
    "/sessions/{session_id}/cancel",
    response_model=CancelResponse,
    responses=ERROR_RESPONSES,
)
async def cancel_turn(
    session: OwnedSession,
    container: ContainerDep,
) -> CancelResponse:
    try:
        return await fake_flow(container).cancel(session)
    except FakeFlowStateError as exc:
        raise ApiError(409, "turn_not_active", str(exc)) from exc


@router.post(
    "/sessions/{session_id}/compact",
    response_model=CompactionResponse,
    responses=ERROR_RESPONSES,
)
async def compact_session(
    session: OwnedSession,
    container: ContainerDep,
) -> CompactionResponse:
    try:
        return await fake_flow(container).compact(session)
    except FakeFlowStateError as exc:
        raise ApiError(409, "compaction_deferred", str(exc)) from exc


@router.get(
    "/sessions/{session_id}/events",
    response_model=EventReplayResponse,
    responses=ERROR_RESPONSES,
)
async def replay_events(
    session: OwnedSession,
    container: ContainerDep,
    after_sequence: int = Query(default=0, ge=0),
    limit: int = Query(default=500, ge=1, le=2_000),
) -> EventReplayResponse:
    return await fake_flow(container).replay(session, after_sequence, limit)


@router.get(
    "/sessions/{session_id}/artifacts",
    response_model=ArtifactsResponse,
    responses=ERROR_RESPONSES,
)
async def list_artifacts(
    session: OwnedSession,
    container: ContainerDep,
) -> ArtifactsResponse:
    return fake_flow(container).artifacts(session)
