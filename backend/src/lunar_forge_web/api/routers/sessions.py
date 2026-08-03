from fastapi import APIRouter, Query, status
from uuid import uuid4

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
    SessionSettings,
    TurnCreateRequest,
    TurnResponse,
)
from lunar_forge_web.domain.enums import FundingMode
from lunar_forge_web.services.fake_flow_service import (
    FakeFlowNotFoundError,
    FakeFlowService,
    FakeFlowStateError,
)
from lunar_forge_web.services.session_service import SessionService
from lunar_forge_web.services.sandbox_service import (
    MeaningfulActivity,
    SandboxService,
    runtime_sandbox,
)
from lunar_forge_web.services.usage_service import UsageService
from lunar_forge_web.storage.repositories import QuotaLimitError


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
    settings = body.settings or SessionSettings()
    admin_settings = await container.admin_settings.get()
    if admin_settings.sandbox_kill_switch_enabled:
        raise ApiError(503, "sandbox_kill_switch", "Sandbox use is disabled.")
    if (
        settings.funding_mode == FundingMode.OWNER_FUNDED.value
        and not admin_settings.owner_funded_enabled
    ):
        raise ApiError(
            503,
            "owner_funded_disabled",
            "Owner-funded mode is disabled.",
        )
    owner_funded = settings.funding_mode == FundingMode.OWNER_FUNDED.value
    if owner_funded and settings.provider != "openai":
        raise ApiError(
            422,
            "owner_funded_provider_not_allowed",
            "Owner-funded mode uses OpenAI only.",
        )
    if owner_funded and settings.model not in {
        "server-default",
        container.settings.owner_funded_model,
    }:
        raise ApiError(
            422,
            "owner_funded_model_not_allowed",
            "Owner-funded mode uses the server-approved model only.",
        )
    turn_id = f"turn_{uuid4().hex}"
    if owner_funded:
        try:
            await UsageService(container.quotas).reserve(
                user_id=session.owner_id,
                turn_id=turn_id,
            )
        except QuotaLimitError as exc:
            status_code = 503 if exc.code in {
                "sandbox_kill_switch",
                "owner_funded_disabled",
            } else 429
            raise ApiError(status_code, exc.code, str(exc)) from exc
    try:
        response = await fake_flow(container).submit_turn(
            session, sandbox, body, turn_id=turn_id
        )
        await SandboxService(container.sandboxes, container.runtime).record_activity(
            sandbox.id, MeaningfulActivity.TURN_SENT
        )
        return response
    except FakeFlowStateError as exc:
        if owner_funded:
            await UsageService(container.quotas).release(turn_id)
        raise ApiError(409, "turn_conflict", str(exc)) from exc
    except Exception:
        if owner_funded:
            await UsageService(container.quotas).release(turn_id)
        raise


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
        response = await fake_flow(container).resolve_approval(
            session,
            approval_id,
            body.approved,
        )
        await SandboxService(container.sandboxes, container.runtime).record_activity(
            session.sandbox_id, MeaningfulActivity.APPROVAL_RESOLVED
        )
        await UsageService(container.quotas).release(response.turn_id)
        return response
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
        response = await fake_flow(container).cancel(session)
        await UsageService(container.quotas).release(response.turn.id)
        return response
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
    sandbox = await container.sandboxes.get(session.sandbox_id)
    if sandbox is None:
        raise ApiError(404, "sandbox_not_found", "Sandbox was not found.")
    if sandbox.runtime_provider == "fake":
        response = fake_flow(container).artifacts(session)
        await SandboxService(container.sandboxes, container.runtime).record_activity(
            sandbox.id, MeaningfulActivity.FILE_INTERACTION
        )
        return response
    items = await container.runtime.list_artifacts(runtime_sandbox(sandbox))
    response = ArtifactsResponse(
        items=[
            {
                "id": item.id,
                "sandbox_id": sandbox.id,
                "session_id": session.id,
                "owner_id": session.owner_id,
                "name": item.name,
                "media_type": item.media_type,
                "size_bytes": item.size_bytes,
                "expires_at": sandbox.expires_at,
            }
            for item in items
        ]
    )
    await SandboxService(container.sandboxes, container.runtime).record_activity(
        sandbox.id, MeaningfulActivity.FILE_INTERACTION
    )
    return response
