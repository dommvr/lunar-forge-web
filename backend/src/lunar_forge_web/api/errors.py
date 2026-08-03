"""Consistent bounded API error envelopes."""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

from lunar_forge_web.domain.models import ErrorDetail, ErrorEnvelope


logger = logging.getLogger("lunar_forge_web.errors")


class ApiError(Exception):
    def __init__(self, status_code: int, code: str, message: str) -> None:
        super().__init__(message)
        self.status_code = status_code
        self.code = code
        self.message = message


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "req_unknown")


def error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
) -> JSONResponse:
    envelope = ErrorEnvelope(
        error=ErrorDetail(code=code, message=message, request_id=request_id)
    )
    return JSONResponse(status_code=status_code, content=envelope.model_dump(mode="json"))


def install_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def handle_api_error(request: Request, exc: ApiError) -> JSONResponse:
        return error_response(
            status_code=exc.status_code,
            code=exc.code,
            message=exc.message,
            request_id=_request_id(request),
        )

    @app.exception_handler(RequestValidationError)
    async def handle_validation_error(
        request: Request,
        exc: RequestValidationError,
    ) -> JSONResponse:
        del exc
        return error_response(
            status_code=422,
            code="invalid_request",
            message="Request validation failed.",
            request_id=_request_id(request),
        )

    @app.exception_handler(HTTPException)
    async def handle_http_error(request: Request, exc: HTTPException) -> JSONResponse:
        code = "not_found" if exc.status_code == 404 else "http_error"
        message = "Resource was not found." if exc.status_code == 404 else "Request failed."
        return error_response(
            status_code=exc.status_code,
            code=code,
            message=message,
            request_id=_request_id(request),
        )

    @app.exception_handler(Exception)
    async def handle_unexpected_error(request: Request, exc: Exception) -> JSONResponse:
        logger.exception(
            "unhandled request error",
            extra={
                "event": {
                    "event": "request.unhandled_error",
                    "request_id": _request_id(request),
                    "error_type": type(exc).__name__,
                }
            },
        )
        return error_response(
            status_code=500,
            code="internal_error",
            message="An internal error occurred.",
            request_id=_request_id(request),
        )


ERROR_RESPONSES = {
    401: {"model": ErrorEnvelope, "description": "Authentication required."},
    403: {"model": ErrorEnvelope, "description": "Access denied."},
    404: {"model": ErrorEnvelope, "description": "Resource not found."},
    422: {"model": ErrorEnvelope, "description": "Invalid request."},
}
