"""Shared API dependencies: standard error type, request-id middleware, auth guard.

See PRD §8 (standard error response) and §7.7 (auth).
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable

from fastapi import Depends, Request
from sqlmodel import Session
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response
from ulid import ULID

from app.db.models import User
from app.db.session import get_session


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


def require_login(
    request: Request,
    session: Session = Depends(get_session),
) -> User:
    """Session auth guard. Returns the current ``User`` or 401 ``unauthorized``.

    The session stores ``user_id`` (Push 9) — and, for backward compatibility
    with sessions issued before the multi-user migration, the legacy ``user``
    (username) key. Either is resolved to a live ``User`` row; if the row is
    missing or no longer ``active`` (disabled/pending after the session was
    issued) the request is rejected so a re-login is required.

    Public routes (``/healthz``, ``/api/auth/login``) must NOT depend on this.
    """
    if "session" not in request.scope:
        raise AppError("unauthorized", 401, "Not authenticated")

    sess = request.session
    user: User | None = None
    user_id = sess.get("user_id")
    if user_id is not None:
        user = session.get(User, user_id)
    else:
        # Legacy session (pre-Push 9): only a username was stored.
        username = sess.get("user")
        if username:
            from app.services.auth import get_user_by_username

            user = get_user_by_username(session, username)

    if user is None:
        raise AppError("unauthorized", 401, "Not authenticated")

    from app.services.auth import STATUS_ACTIVE

    if user.status != STATUS_ACTIVE:
        # Account was disabled/un-approved after the session was issued.
        raise AppError("unauthorized", 401, "Not authenticated")

    return user


def require_admin(user: User = Depends(require_login)) -> User:
    """Admin-only guard. 403 ``forbidden`` for non-admin users (PRD §6.3)."""
    from app.services.auth import ROLE_ADMIN

    if user.role != ROLE_ADMIN:
        raise AppError("forbidden", 403, "Admin privileges required")
    return user


def is_admin(user: User) -> bool:
    """True iff the user is an admin (sees every owner's resources)."""
    from app.services.auth import ROLE_ADMIN

    return user.role == ROLE_ADMIN
