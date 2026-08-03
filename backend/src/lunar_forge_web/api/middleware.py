"""Request IDs, request bounds, and redacted structured access logs."""

from __future__ import annotations

import logging
import re
import time
from uuid import uuid4

from fastapi import FastAPI, Request
from starlette.responses import Response

from lunar_forge_web.api.errors import error_response
from lunar_forge_web.config import Settings


logger = logging.getLogger("lunar_forge_web.access")
_REQUEST_ID = re.compile(r"^[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}$")


def _select_request_id(value: str | None) -> str:
    if value and _REQUEST_ID.fullmatch(value):
        return value
    return f"req_{uuid4().hex}"


def install_request_middleware(app: FastAPI, settings: Settings) -> None:
    @app.middleware("http")
    async def request_context(request: Request, call_next) -> Response:
        started = time.perf_counter()
        request_id = _select_request_id(request.headers.get("x-request-id"))
        request.state.request_id = request_id
        content_length = request.headers.get("content-length")
        if content_length:
            try:
                too_large = int(content_length) > settings.max_request_body_bytes
            except ValueError:
                too_large = True
            if too_large:
                response = error_response(
                    status_code=413,
                    code="request_too_large",
                    message="Request body is too large.",
                    request_id=request_id,
                )
                response.headers["X-Request-ID"] = request_id
                return response
        if request.method in {"POST", "PUT", "PATCH", "DELETE"}:
            body = await request.body()
            if len(body) > settings.max_request_body_bytes:
                response = error_response(
                    status_code=413,
                    code="request_too_large",
                    message="Request body is too large.",
                    request_id=request_id,
                )
                response.headers["X-Request-ID"] = request_id
                return response
        response = await call_next(request)
        response_length = response.headers.get("content-length")
        if response_length is not None:
            try:
                response_too_large = (
                    int(response_length) > settings.max_response_body_bytes
                )
            except ValueError:
                response_too_large = True
            if response_too_large:
                response = error_response(
                    status_code=500,
                    code="response_too_large",
                    message="Response exceeded the configured size bound.",
                    request_id=request_id,
                )
        response.headers["X-Request-ID"] = request_id
        response.headers.setdefault("Cache-Control", "no-store")
        logger.info(
            "request completed",
            extra={
                "event": {
                    "event": "request.completed",
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": round((time.perf_counter() - started) * 1_000, 2),
                }
            },
        )
        return response
