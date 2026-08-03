def test_public_git_validation_is_bounded_and_runtime_truthful(client, auth_headers):
    valid = client.post(
        "/api/v1/project-sources/public-git/validate",
        headers=auth_headers(),
        json={"url": "https://github.com/openai/example"},
    )
    assert valid.status_code == 200
    assert valid.json() == {
        "canonical_url": "https://github.com/openai/example.git",
        "owner": "openai",
        "repository": "example",
        "clone_supported": False,
    }

    invalid = client.post(
        "/api/v1/project-sources/public-git/validate",
        headers=auth_headers(),
        json={"url": "https://127.0.0.1/private/repository"},
    )
    assert invalid.status_code == 422
    assert invalid.json()["error"]["code"] == "invalid_repository_url"
