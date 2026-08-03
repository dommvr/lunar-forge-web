"""Strict validation for credential-free public GitHub project sources."""

from __future__ import annotations

import re
from dataclasses import dataclass
from urllib.parse import urlsplit, urlunsplit

from lunar_forge_web.security.limits import MAX_PUBLIC_GIT_URL_CHARACTERS


_GITHUB_COMPONENT = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9_.-]{0,99})$")


class UnsafeGitUrlError(ValueError):
    pass


@dataclass(frozen=True, slots=True)
class PublicGitHubRepository:
    url: str
    owner: str
    repository: str


def validate_public_github_url(value: str) -> PublicGitHubRepository:
    if not value or len(value) > MAX_PUBLIC_GIT_URL_CHARACTERS:
        raise UnsafeGitUrlError("Repository URL is invalid.")
    parsed = urlsplit(value)
    if parsed.scheme.lower() != "https" or parsed.hostname != "github.com":
        raise UnsafeGitUrlError("Only HTTPS github.com repositories are supported.")
    if (
        parsed.username is not None
        or parsed.password is not None
        or parsed.port is not None
        or parsed.query
        or parsed.fragment
    ):
        raise UnsafeGitUrlError("Credentials, ports, queries, and fragments are not allowed.")
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) != 2:
        raise UnsafeGitUrlError("Repository URL must contain one owner and repository.")
    owner, repository = parts
    if repository.endswith(".git"):
        repository = repository[:-4]
    if not _GITHUB_COMPONENT.fullmatch(owner) or not _GITHUB_COMPONENT.fullmatch(
        repository
    ):
        raise UnsafeGitUrlError("Repository owner or name is invalid.")
    canonical = urlunsplit(("https", "github.com", f"/{owner}/{repository}.git", "", ""))
    return PublicGitHubRepository(
        url=canonical,
        owner=owner,
        repository=repository,
    )
