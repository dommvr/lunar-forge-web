import asyncio

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
    WorkerTurnRequest,
)
from lunar_forge_web.domain.enums import FundingMode, TurnStatus
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
from lunar_forge_web.storage.repositories import (
    QuotaLimitError,
    RepositoryConflictError,
    RepositoryStateError,
)
from lunar_forge_web.worker.client import WorkerInvocationError


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
    if container.worker_client is None:
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
    if owner_funded and body.provider_api_key is not None:
        raise ApiError(
            422,
            "owner_funded_credential_forbidden",
            "Owner-funded turns must not include a provider credential.",
        )
    if not owner_funded and body.provider_api_key is None:
        raise ApiError(
            422,
            "byok_credential_required",
            "BYOK turns require a provider credential for the current turn.",
        )
    selected_model = (
        container.settings.owner_funded_model
        if owner_funded
        else container.settings.byok_openai_model
        if settings.provider == "openai"
        else container.settings.byok_anthropic_model
    )
    if settings.model not in {"server-default", selected_model}:
        raise ApiError(
            422,
            "model_not_allowed",
            "The selected model is not on the server allowlist.",
        )
    settings = settings.model_copy(update={"model": selected_model})
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
    if container.worker_client is not None:
        queued = TurnResponse(
            id=turn_id,
            session_id=session.id,
            owner_id=session.owner_id,
            status=TurnStatus.QUEUED,
        )
        try:
            await container.turns.create(
                queued,
                sandbox_id=sandbox.id,
                prompt=body.message,
                settings=settings,
            )
        except RepositoryConflictError as exc:
            if owner_funded:
                await UsageService(container.quotas).release(turn_id)
            raise ApiError(409, "turn_conflict", str(exc)) from exc
        await SandboxService(container.sandboxes, container.runtime).record_activity(
            sandbox.id, MeaningfulActivity.TURN_SENT
        )
        worker_execution = asyncio.create_task(
            container.worker_client.run_turn(
                WorkerTurnRequest(
                    sandbox_id=sandbox.id,
                    session_id=session.id,
                    turn_id=turn_id,
                    owner_id=session.owner_id,
                    message=body.message,
                    settings=settings,
                    provider_credential=body.provider_api_key,
                )
            )
        )
        try:
            await asyncio.shield(worker_execution)
        except asyncio.CancelledError:
            # A browser disconnect must not cancel the already-authenticated
            # private worker request or leave its event stream half-written.
            try:
                await worker_execution
            except WorkerInvocationError:
                pass
            raise
        except WorkerInvocationError as exc:
            raise ApiError(
                503 if exc.retryable else 504,
                exc.code,
                exc.message,
            ) from exc
        completed = await container.turns.get(turn_id)
        if completed is None:
            raise ApiError(
                502,
                "worker_terminal_state_missing",
                "The private worker did not record a terminal turn state.",
            )
        return completed.turn

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
    if container.worker_client is not None:
        approval = await container.approvals.get(approval_id)
        for _ in range(10):
            if approval is not None:
                break
            await asyncio.sleep(0.01)
            approval = await container.approvals.get(approval_id)
        if (
            approval is None
            or approval.session_id != session.id
            or approval.owner_id != session.owner_id
        ):
            raise ApiError(404, "approval_not_found", "Approval was not found.")
        try:
            resolved = await container.approvals.resolve(
                approval_id, session.owner_id, body.approved
            )
        except RepositoryConflictError as exc:
            raise ApiError(409, "approval_already_resolved", str(exc)) from exc
        except RepositoryStateError as exc:
            raise ApiError(404, "approval_not_found", "Approval was not found.") from exc
        await container.controls.publish_control(
            session_id=session.id,
            kind="approval",
            action_id=approval_id,
            payload={"approved": body.approved, "reason": body.reason},
        )
        await SandboxService(container.sandboxes, container.runtime).record_activity(
            session.sandbox_id, MeaningfulActivity.APPROVAL_RESOLVED
        )
        return resolved
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
    if container.worker_client is not None:
        active = await container.turns.active_for_session(session.id)
        if active is None:
            raise ApiError(409, "turn_not_active", "No turn is active.")
        await container.controls.publish_control(
            session_id=session.id,
            kind="cancel",
            action_id=active.turn.id,
            payload={"rollback": True},
        )
        return CancelResponse(
            turn=active.turn,
            rollback_report=(
                "Cancellation and rollback were requested. Await the ordered "
                "turn.cancelled and rollback.finished stream events for the result."
            ),
        )
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
    events = await container.events.replay(session.id, after_sequence, limit)
    last_sequence = await container.events.last_sequence(session.id)
    return EventReplayResponse(
        session_id=session.id,
        after_sequence=after_sequence,
        last_sequence=last_sequence,
        has_more=bool(events and events[-1].sequence < last_sequence),
        events=list(events),
    )


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
