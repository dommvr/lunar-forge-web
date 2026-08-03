import hashlib

import pytest
from fastapi import WebSocketDisconnect


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
