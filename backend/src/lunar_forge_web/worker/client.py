"""Private Cloud Run worker invocation from the authenticated API plane."""

from __future__ import annotations

from typing import Protocol

import httpx
from pydantic import SecretStr, ValidationError

from lunar_forge_web.domain.models import WorkerTurnRequest, WorkerTurnResponse


_METADATA_IDENTITY_ENDPOINT = (
    "http://metadata.google.internal/computeMetadata/v1/instance/"
    "service-accounts/default/identity"
)


class WorkerInvocationError(RuntimeError):
    def __init__(self, code: str, message: str, *, retryable: bool) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.retryable = retryable


class WorkerClient(Protocol):
    async def run_turn(self, request: WorkerTurnRequest) -> WorkerTurnResponse: ...
    async def close(self) -> None: ...


class IdentityTokenProvider(Protocol):
    async def token(self, audience: str) -> str: ...


class GoogleMetadataIdentityTokenProvider:
    """Fetch a Google-signed ID token from the Cloud Run metadata server."""

    def __init__(self, client: httpx.AsyncClient) -> None:
        self._client = client

    async def token(self, audience: str) -> str:
        try:
            response = await self._client.get(
                _METADATA_IDENTITY_ENDPOINT,
                params={"audience": audience, "format": "full"},
                headers={"Metadata-Flavor": "Google"},
            )
            response.raise_for_status()
        except httpx.HTTPError as exc:
            raise WorkerInvocationError(
                "worker_identity_unavailable",
                "Private worker identity could not be established.",
                retryable=True,
            ) from exc
        token = response.text.strip()
        if not token or len(token) > 16_384:
            raise WorkerInvocationError(
                "worker_identity_invalid",
                "Private worker identity was invalid.",
                retryable=True,
            )
        return token


class CloudRunWorkerClient:
    """Invoke one private worker request for the complete bounded turn."""

    def __init__(
        self,
        *,
        worker_url: str,
        audience: str,
        shared_secret: SecretStr,
        request_timeout_seconds: float,
        identity_timeout_seconds: float,
        client: httpx.AsyncClient | None = None,
        identity_tokens: IdentityTokenProvider | None = None,
    ) -> None:
        self._worker_url = worker_url.rstrip("/")
        self._audience = audience
        self._shared_secret = shared_secret
        self._owns_client = client is None
        self._client = client or httpx.AsyncClient(
            timeout=httpx.Timeout(
                request_timeout_seconds,
                connect=10.0,
                write=30.0,
                pool=10.0,
            ),
            follow_redirects=False,
        )
        if identity_tokens is None:
            metadata_client = httpx.AsyncClient(
                timeout=httpx.Timeout(identity_timeout_seconds),
                follow_redirects=False,
            )
            self._metadata_client = metadata_client
            self._identity_tokens = GoogleMetadataIdentityTokenProvider(metadata_client)
        else:
            self._metadata_client = None
            self._identity_tokens = identity_tokens

    async def run_turn(self, request: WorkerTurnRequest) -> WorkerTurnResponse:
        identity_token = await self._identity_tokens.token(self._audience)
        payload = request.model_dump(
            mode="json", exclude={"provider_credential"}
        )
        if request.provider_credential is not None:
            payload["provider_credential"] = (
                request.provider_credential.get_secret_value()
            )
        try:
            response = await self._client.post(
                f"{self._worker_url}/internal/v1/turns:run",
                json=payload,
                headers={
                    "Authorization": (
                        "Bearer " + self._shared_secret.get_secret_value()
                    ),
                    "X-Serverless-Authorization": f"Bearer {identity_token}",
                    "Cache-Control": "no-store",
                },
            )
        except httpx.TimeoutException as exc:
            raise WorkerInvocationError(
                "worker_timeout",
                "The private worker request timed out.",
                retryable=False,
            ) from exc
        except httpx.HTTPError as exc:
            raise WorkerInvocationError(
                "worker_unavailable",
                "The private worker is unavailable.",
                retryable=True,
            ) from exc
        if response.status_code != 200:
            raise WorkerInvocationError(
                "worker_rejected",
                "The private worker rejected the turn.",
                retryable=response.status_code >= 500,
            )
        try:
            return WorkerTurnResponse.model_validate(response.json())
        except (ValueError, ValidationError) as exc:
            raise WorkerInvocationError(
                "worker_response_invalid",
                "The private worker returned an invalid response.",
                retryable=True,
            ) from exc

    async def close(self) -> None:
        if self._metadata_client is not None:
            await self._metadata_client.aclose()
        if self._owns_client:
            await self._client.aclose()


class InProcessWorkerClient:
    """Deterministic worker boundary substitute for integration tests."""

    def __init__(self, runner) -> None:
        self._runner = runner

    async def run_turn(self, request: WorkerTurnRequest) -> WorkerTurnResponse:
        return await self._runner.run(request)

    async def close(self) -> None:
        return None
