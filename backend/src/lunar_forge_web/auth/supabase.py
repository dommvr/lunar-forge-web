"""Asynchronous Supabase JWT verification using issuer-bound JWKS."""

from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass
from typing import Any, Protocol

import httpx
import jwt
from jwt import InvalidTokenError, PyJWK

from lunar_forge_web.config import Settings
from lunar_forge_web.domain.enums import AssuranceLevel


class JWTValidationError(ValueError):
    """Raised when a bearer token cannot be trusted."""


@dataclass(frozen=True, slots=True)
class VerifiedClaims:
    subject: str
    email: str | None
    assurance_level: AssuranceLevel
    issued_at: int
    expires_at: int


class JWKSProvider(Protocol):
    async def get_jwks(self) -> dict[str, Any]: ...


class TokenVerifier(Protocol):
    async def verify(self, token: str) -> VerifiedClaims: ...


class DeterministicFakeTokenVerifier:
    """Accept bounded test tokens only when explicitly selected by settings."""

    async def verify(self, token: str) -> VerifiedClaims:
        identities = {
            "e2e-user": ("user-e2e", AssuranceLevel.AAL1),
            "e2e-admin-aal1": ("admin-e2e", AssuranceLevel.AAL1),
            "e2e-admin-aal2": ("admin-e2e", AssuranceLevel.AAL2),
        }
        selected = identities.get(token)
        if selected is None:
            raise JWTValidationError("Bearer token is invalid.")
        subject, assurance = selected
        now = int(time.time())
        return VerifiedClaims(
            subject=subject,
            email=f"{subject}@example.test",
            assurance_level=assurance,
            issued_at=now,
            expires_at=now + 3_600,
        )


class StaticJWKSProvider:
    """Deterministic provider used by tests and local contract fixtures."""

    def __init__(self, jwks: dict[str, Any]) -> None:
        self._jwks = jwks

    async def get_jwks(self) -> dict[str, Any]:
        return self._jwks


class RemoteJWKSProvider:
    """Bounded in-memory JWKS cache backed by an async HTTP client."""

    def __init__(self, url: str, cache_ttl_seconds: int) -> None:
        self._url = url
        self._cache_ttl_seconds = cache_ttl_seconds
        self._cached: dict[str, Any] | None = None
        self._cached_until = 0.0
        self._lock = asyncio.Lock()

    async def get_jwks(self) -> dict[str, Any]:
        now = time.monotonic()
        if self._cached is not None and now < self._cached_until:
            return self._cached
        async with self._lock:
            now = time.monotonic()
            if self._cached is not None and now < self._cached_until:
                return self._cached
            try:
                async with httpx.AsyncClient(
                    timeout=httpx.Timeout(5.0),
                    follow_redirects=False,
                ) as client:
                    response = await client.get(
                        self._url,
                        headers={"Accept": "application/json"},
                    )
                    response.raise_for_status()
                    payload = response.json()
            except (httpx.HTTPError, ValueError) as exc:
                raise JWTValidationError("Signing keys are unavailable.") from exc
            if not isinstance(payload, dict) or not isinstance(payload.get("keys"), list):
                raise JWTValidationError("Signing keys are invalid.")
            self._cached = payload
            self._cached_until = now + self._cache_ttl_seconds
            return payload


class SupabaseJWTVerifier:
    """Verify signature, issuer, audience, lifetime, subject, and Auth role."""

    def __init__(
        self,
        settings: Settings,
        jwks_provider: JWKSProvider | None = None,
    ) -> None:
        self._settings = settings
        self._jwks_provider = jwks_provider or RemoteJWKSProvider(
            settings.supabase_jwks_url,
            settings.jwks_cache_ttl_seconds,
        )

    async def verify(self, token: str) -> VerifiedClaims:
        if not token or len(token) > 16_384:
            raise JWTValidationError("Bearer token is invalid.")
        try:
            header = jwt.get_unverified_header(token)
        except InvalidTokenError as exc:
            raise JWTValidationError("Bearer token is invalid.") from exc
        algorithm = header.get("alg")
        key_id = header.get("kid")
        if algorithm not in self._settings.supabase_allowed_algorithms:
            raise JWTValidationError("Bearer token algorithm is not allowed.")
        if not isinstance(key_id, str) or not key_id:
            raise JWTValidationError("Bearer token key id is missing.")

        jwks = await self._jwks_provider.get_jwks()
        candidates = [
            item
            for item in jwks.get("keys", [])
            if isinstance(item, dict)
            and item.get("kid") == key_id
            and item.get("alg") == algorithm
        ]
        if len(candidates) != 1:
            raise JWTValidationError("Bearer token signing key was not found.")
        try:
            signing_key = PyJWK.from_dict(candidates[0], algorithm=algorithm).key
            claims = jwt.decode(
                token,
                signing_key,
                algorithms=[algorithm],
                audience=self._settings.supabase_audience,
                issuer=self._settings.supabase_issuer,
                options={"require": ["exp", "iat", "sub"]},
            )
        except (InvalidTokenError, ValueError, TypeError) as exc:
            raise JWTValidationError("Bearer token is invalid.") from exc

        subject = claims.get("sub")
        issued_at = claims.get("iat")
        expires_at = claims.get("exp")
        role = claims.get("role")
        if not isinstance(subject, str) or not subject or len(subject) > 200:
            raise JWTValidationError("Bearer token subject is invalid.")
        if not isinstance(issued_at, int) or not isinstance(expires_at, int):
            raise JWTValidationError("Bearer token lifetime is invalid.")
        if role != self._settings.supabase_required_role:
            raise JWTValidationError("Bearer token role is not accepted.")
        email = claims.get("email")
        if email is not None and (not isinstance(email, str) or len(email) > 320):
            raise JWTValidationError("Bearer token email is invalid.")
        assurance = (
            AssuranceLevel.AAL2
            if claims.get("aal") == AssuranceLevel.AAL2.value
            else AssuranceLevel.AAL1
        )
        return VerifiedClaims(
            subject=subject,
            email=email,
            assurance_level=assurance,
            issued_at=issued_at,
            expires_at=expires_at,
        )
