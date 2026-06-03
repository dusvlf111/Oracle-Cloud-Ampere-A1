"""Global exception handlers producing the standard error envelope (PRD §8).

Envelope shape (every 4xx/5xx)::

    {"error": {"code", "message", "details", "request_id"}}
"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from slowapi.errors import RateLimitExceeded
from starlette.responses import JSONResponse

from app.api.deps import AppError, get_request_id

logger = logging.getLogger("app.api.errors")


def _envelope(
    *,
    status_code: int,
    code: str,
    message: str,
    request_id: str,
    details: dict | None = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            "error": {
                "code": code,
                "message": message,
                "details": details,
                "request_id": request_id,
            }
        },
    )


async def app_error_handler(request: Request, exc: AppError) -> JSONResponse:
    return _envelope(
        status_code=exc.status_code,
        code=exc.code,
        message=exc.message,
        details=exc.details,
        request_id=get_request_id(request),
    )


async def validation_error_handler(
    request: Request, exc: RequestValidationError
) -> JSONResponse:
    # `errors()` is JSON-serialisable list of {loc, msg, type, ...}.
    return _envelope(
        status_code=422,
        code="validation_error",
        message="Request validation failed",
        details={"errors": exc.errors()},
        request_id=get_request_id(request),
    )


async def rate_limit_handler(
    request: Request, exc: RateLimitExceeded
) -> JSONResponse:
    # slowapi parses "5/minute" → 60s window. Surface retry hint in details.
    retry_after = getattr(exc.limit.limit, "get_expiry", lambda: 60)()
    return _envelope(
        status_code=429,
        code="rate_limited",
        message="Too many login attempts",
        details={"retry_after_sec": int(retry_after)},
        request_id=get_request_id(request),
    )


async def internal_error_handler(request: Request, exc: Exception) -> JSONResponse:
    request_id = get_request_id(request)
    logger.exception("Unhandled exception (request_id=%s)", request_id)
    return _envelope(
        status_code=500,
        code="internal_error",
        message="Internal server error",
        request_id=request_id,
    )


def register_error_handlers(app: FastAPI) -> None:
    app.add_exception_handler(AppError, app_error_handler)
    app.add_exception_handler(RequestValidationError, validation_error_handler)
    app.add_exception_handler(Exception, internal_error_handler)
