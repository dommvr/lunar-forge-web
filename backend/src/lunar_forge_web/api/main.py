"""Browser-facing FastAPI application factory."""

from __future__ import annotations

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from lunar_forge_web import __version__
from lunar_forge_web.api.errors import install_error_handlers
from lunar_forge_web.api.middleware import install_request_middleware
from lunar_forge_web.api.routers import admin, identity, realtime, sandboxes, sessions, system
from lunar_forge_web.config import Settings, get_settings
from lunar_forge_web.container import ApplicationContainer, build_container
from lunar_forge_web.security.redaction import configure_logging


def create_app(
    settings: Settings | None = None,
    container: ApplicationContainer | None = None,
) -> FastAPI:
    selected = settings or get_settings()
    dependencies = container or build_container(selected)
    configure_logging(selected.log_level)
    app = FastAPI(
        title="LunarForge Web API",
        version=__version__,
        docs_url="/api/v1/docs",
        redoc_url=None,
        openapi_url="/api/v1/openapi.json",
    )
    app.state.container = dependencies
    app.add_middleware(
        CORSMiddleware,
        allow_origins=list(selected.cors_allowed_origins),
        allow_credentials=True,
        allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
        allow_headers=["Authorization", "Content-Type", "X-Request-ID"],
        expose_headers=["X-Request-ID"],
        max_age=600,
    )
    install_request_middleware(app, selected)
    install_error_handlers(app)
    prefix = "/api/v1"
    app.include_router(system.router, prefix=prefix)
    app.include_router(identity.router, prefix=prefix)
    app.include_router(sandboxes.router, prefix=prefix)
    app.include_router(sessions.router, prefix=prefix)
    app.include_router(realtime.router, prefix=prefix)
    app.include_router(admin.router, prefix=prefix)
    return app


app = create_app()


def run() -> None:
    import uvicorn

    uvicorn.run(
        "lunar_forge_web.api.main:app",
        host="0.0.0.0",
        port=8080,
        access_log=False,
        log_level="warning",
    )
