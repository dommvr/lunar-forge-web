import hashlib
import asyncio

import pytest
from fastapi import WebSocketDisconnect

from lunar_forge_web.domain.events import AgentEventContract


def _event(sequence: int) -> AgentEventContract:
    return AgentEventContract(
        event_id=f"evt-reconnect-{sequence}",
        session_id="session-a",
        turn_id="turn-reconnect",
        sequence=sequence,
        timestamp=f"2026-08-04T12:00:0{sequence}Z",
        type="status.updated",
        payload={"message": f"step {sequence}"},
    )


def test_ticket_is_hashed_bound_and_consumed_once(client, container, auth_headers):
    response = client.post(
        "/api/v1/realtime/tickets",
        headers=auth_headers("user-a"),
        json={"session_id": "session-a"},
    )

    assert response.status_code == 201
    ticket = response.json()["ticket"]
    digest = hashlib.sha256(ticket.encode()).hexdigest()
    assert container.tickets.stored_digests() == (digest,)
    assert all(ticket not in stored for stored in container.tickets.stored_digests())

    with client.websocket_connect(
        f"/api/v1/sessions/session-a/stream?ticket={ticket}&after_sequence=7"
    ) as websocket:
        assert websocket.receive_json() == {
            "type": "stream.ready",
            "session_id": "session-a",
            "after_sequence": 7,
        }

    assert container.tickets.stored_digests() == ()
    with pytest.raises(WebSocketDisconnect) as reused:
        with client.websocket_connect(
            f"/api/v1/sessions/session-a/stream?ticket={ticket}"
        ):
            pass
    assert reused.value.code == 4401


def test_ticket_cannot_be_issued_for_another_users_session(client, auth_headers):
    response = client.post(
        "/api/v1/realtime/tickets",
        headers=auth_headers("user-a"),
        json={"session_id": "session-b"},
    )

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "session_not_found"


def test_websocket_reconnect_replays_strictly_after_last_sequence(
    client, container, auth_headers
):
    asyncio.run(container.events.append(_event(1)))
    first_ticket = client.post(
        "/api/v1/realtime/tickets",
        headers=auth_headers("user-a"),
        json={"session_id": "session-a"},
    ).json()["ticket"]

    with client.websocket_connect(
        f"/api/v1/sessions/session-a/stream?ticket={first_ticket}&after_sequence=0"
    ) as websocket:
        assert websocket.receive_json()["type"] == "stream.ready"
        assert websocket.receive_json()["sequence"] == 1

    asyncio.run(container.events.append(_event(2)))
    asyncio.run(container.events.append(_event(3)))
    second_ticket = client.post(
        "/api/v1/realtime/tickets",
        headers=auth_headers("user-a"),
        json={"session_id": "session-a"},
    ).json()["ticket"]
    with client.websocket_connect(
        f"/api/v1/sessions/session-a/stream?ticket={second_ticket}&after_sequence=1"
    ) as websocket:
        assert websocket.receive_json()["type"] == "stream.ready"
        assert [websocket.receive_json()["sequence"] for _ in range(2)] == [2, 3]


def test_heartbeat_is_explicit_and_does_not_extend_sandbox_ttl(
    client, container, settings, auth_headers
):
    settings.websocket_heartbeat_seconds = 0.05
    before = asyncio.run(container.sandboxes.get("sandbox-a"))
    ticket = client.post(
        "/api/v1/realtime/tickets",
        headers=auth_headers("user-a"),
        json={"session_id": "session-a"},
    ).json()["ticket"]

    with client.websocket_connect(
        f"/api/v1/sessions/session-a/stream?ticket={ticket}"
    ) as websocket:
        assert websocket.receive_json()["type"] == "stream.ready"
        heartbeat = websocket.receive_json()
        assert heartbeat["type"] == "stream.heartbeat"
        assert heartbeat["last_sequence"] == 0
        assert "sent_at" in heartbeat

    after = asyncio.run(container.sandboxes.get("sandbox-a"))
    assert before is not None and after is not None
    assert after.last_activity_at == before.last_activity_at
    assert after.expires_at == before.expires_at
