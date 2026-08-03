def test_owned_resources_are_visible_only_to_the_owner(client, auth_headers):
    own = client.get("/api/v1/sandboxes/sandbox-a", headers=auth_headers("user-a"))
    other = client.get("/api/v1/sandboxes/sandbox-b", headers=auth_headers("user-a"))
    listed = client.get("/api/v1/sandboxes", headers=auth_headers("user-a"))
    session = client.get("/api/v1/sessions/session-b", headers=auth_headers("user-a"))

    assert own.status_code == 200
    assert other.status_code == 404
    assert other.json()["error"]["code"] == "sandbox_not_found"
    assert [item["id"] for item in listed.json()["items"]] == ["sandbox-a"]
    assert session.status_code == 404
    assert session.json()["error"]["code"] == "session_not_found"


def test_invalid_request_is_bounded_and_does_not_echo_body(client, auth_headers):
    response = client.post(
        "/api/v1/sandboxes",
        headers=auth_headers(),
        json={"template_id": "bad value", "password": "top-secret"},
    )

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "invalid_request"
    assert "top-secret" not in response.text


def test_missing_route_uses_error_envelope(client):
    response = client.get("/api/v1/does-not-exist")

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "not_found"
    assert response.headers["x-request-id"].startswith("req_")
