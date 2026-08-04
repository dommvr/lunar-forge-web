import asyncio

from fastapi import APIRouter, Query, WebSocket, WebSocketDisconnect, status

from lunar_forge_web.api.dependencies import ContainerDep, CurrentPrincipal
from lunar_forge_web.api.errors import ERROR_RESPONSES, ApiError
from lunar_forge_web.auth.authorization import can_access_owned_resource
from lunar_forge_web.domain.models import (
    RealtimeTicketRequest,
    RealtimeTicketResponse,
    StreamErrorMessage,
    StreamHeartbeatMessage,
    StreamReadyMessage,
)
from lunar_forge_web.security.tickets import TicketValidationError


router = APIRouter(tags=["realtime"])


@router.post(
    "/realtime/tickets",
    response_model=RealtimeTicketResponse,
    status_code=status.HTTP_201_CREATED,
    responses=ERROR_RESPONSES,
)
async def create_ticket(
    body: RealtimeTicketRequest,
    principal: CurrentPrincipal,
    container: ContainerDep,
) -> RealtimeTicketResponse:
    session = await container.sessions.get(body.session_id)
    if session is None or not can_access_owned_resource(principal, session.owner_id):
        raise ApiError(404, "session_not_found", "Session was not found.")
    issued = await container.tickets.issue(session.owner_id, session.id)
    return RealtimeTicketResponse(
        ticket=issued.token,
        session_id=session.id,
        expires_at=issued.expires_at,
        websocket_path=f"/api/v1/sessions/{session.id}/stream",
    )


@router.websocket("/sessions/{session_id}/stream")
async def stream(
    websocket: WebSocket,
    session_id: str,
    ticket: str = Query(min_length=32, max_length=512),
    after_sequence: int = Query(default=0, ge=0),
) -> None:
    container = websocket.app.state.container
    try:
        await container.tickets.consume(ticket, session_id)
    except TicketValidationError:
        await websocket.close(code=4401, reason="Invalid or expired ticket.")
        return
    await websocket.accept()
    await websocket.send_json(
        StreamReadyMessage(
            session_id=session_id,
            after_sequence=after_sequence,
        ).model_dump(mode="json")
    )
    cursor = after_sequence
    try:
        while True:
            events = await container.events.replay(
                session_id,
                cursor,
                container.settings.max_event_replay_items,
            )
            for event in events:
                if event.sequence != cursor + 1:
                    await websocket.send_json(
                        StreamErrorMessage(
                            code="stream_replay_gap",
                            message=(
                                "The requested event offset is no longer available."
                            ),
                            reconnectable=False,
                            last_sequence=cursor,
                        ).model_dump(mode="json")
                    )
                    await websocket.close(
                        code=4409, reason="Event replay offset is unavailable."
                    )
                    return
                await websocket.send_json(event.model_dump(mode="json"))
                cursor = event.sequence
            available = await container.events.wait_for_events(
                session_id,
                cursor,
                timeout=container.settings.websocket_heartbeat_seconds,
            )
            if not available:
                await websocket.send_json(
                    StreamHeartbeatMessage(
                        session_id=session_id,
                        last_sequence=cursor,
                    ).model_dump(mode="json")
                )
    except WebSocketDisconnect:
        return
    except asyncio.CancelledError:
        raise
    except Exception:
        try:
            await websocket.send_json(
                StreamErrorMessage(
                    code="stream_transport_error",
                    message="The event stream transport failed; reconnect with the last sequence.",
                    reconnectable=True,
                    last_sequence=cursor,
                ).model_dump(mode="json")
            )
            await websocket.close(code=1011, reason="Event stream transport failed.")
        except Exception:
            pass
