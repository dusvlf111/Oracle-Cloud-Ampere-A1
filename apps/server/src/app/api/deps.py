"""Shared API dependencies: standard error type, request-id middleware, auth guard.

See PRD §8 (standard error response) and §7.7 (auth).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from ulid import ULID


class AppError(Exception):
    """Domain error mapped to the standard error envelope (PRD §8).

    The global exception handler renders this as::

        {"error": {"code", "message", "details", "request_id"}}
    """

    def __init__(
        self,
        code: str,
        status_code: int,
        message: str,
        details: dict | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.status_code = status_code
        self.message = message
        self.details = details


def get_request_id(request: Request) -> str:
    """Return the request id set by ``RequestIdMiddleware`` (graceful fallback)."""
    return getattr(request.state, "request_id", "") or ""


class RequestIdMiddleware(BaseHTTPMiddleware):
    """Assign a ULID to every request and echo it back as ``X-Request-Id``.

    The id is stored on ``request.state.request_id`` so exception handlers and
    log records can reference it.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        request_id = str(ULID())
        request.state.request_id = request_id
        response = await call_next(request)
        response.headers["X-Request-Id"] = request_id
        return response


def require_login(request: Request) -> str:
    """Session auth guard. Returns the username or raises ``unauthorized`` (401).

    Public routes (``/healthz``, ``/api/auth/login``) must NOT depend on this.
    """
    user = request.session.get("user") if "session" in request.scope else None
    if not user:
        raise AppError("unauthorized", 401, "Not authenticated")
    return user
