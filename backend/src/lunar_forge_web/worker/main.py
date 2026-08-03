"""Private authenticated turn-worker FastAPI application."""

from __future__ import annotations

import secrets
from contextlib import asynccontextmanager
from typing import Annotated

from fastapi import Depends, FastAPI
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from lunar_forge_web import __version__
from lunar_forge_web.api.errors import ERROR_RESPONSES, ApiError, install_error_handlers
from lunar_forge_web.api.middleware import install_request_middleware
from lunar_forge_web.config import Settings, get_settings
from lunar_forge_web.container import ApplicationContainer, build_container
from lunar_forge_web.domain.models import (
    HealthResponse,
    WorkerTurnRequest,
    WorkerTurnResponse,
)
from lunar_forge_web.security.redaction import configure_logging
from lunar_forge_web.worker.turn_runner import TurnRunner


worker_bearer = HTTPBearer(auto_error=False)


def create_worker_app(
    settings: Settings | None = None,
    container: ApplicationContainer | None = None,
) -> FastAPI:
    selected = settings or get_settings()
    dependencies = container or build_container(selected)

    @asynccontextmanager
    async def lifespan(_: FastAPI):
        try:
            yield
        finally:
            await dependencies.close()

    configure_logging(selected.log_level)
    app = FastAPI(
        title="LunarForge Private Turn Worker",
        version=__version__,
        docs_url=None,
        redoc_url=None,
        openapi_url=None,
        lifespan=lifespan,
    )
    app.state.container = dependencies
    install_request_middleware(app, selected)
    install_error_handlers(app)

    async def require_worker_auth(
        credentials: Annotated[
            HTTPAuthorizationCredentials | None,
            Depends(worker_bearer),
        ],
    ) -> None:
        expected = selected.worker_shared_secret.get_secret_value()
        if (
            credentials is None
            or credentials.scheme.lower() != "bearer"
            or not secrets.compare_digest(credentials.credentials, expected)
        ):
            raise ApiError(
                401,
                "worker_authentication_required",
                "Worker authentication is required.",
            )

    @app.get("/health", response_model=HealthResponse, tags=["system"])
    async def health() -> HealthResponse:
        return HealthResponse(
            service="worker",
            environment=selected.environment.value,
        )

    @app.post(
        "/internal/v1/turns:run",
        response_model=WorkerTurnResponse,
        responses=ERROR_RESPONSES,
        dependencies=[Depends(require_worker_auth)],
        tags=["turns"],
    )
    async def run_turn(body: WorkerTurnRequest) -> WorkerTurnResponse:
        return await TurnRunner(dependencies.agent).run(body)

    return app


app = create_worker_app()


def run() -> None:
    import uvicorn

    uvicorn.run("lunar_forge_web.worker.main:app", host="0.0.0.0", port=8080)
