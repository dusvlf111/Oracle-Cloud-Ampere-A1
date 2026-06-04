"""Auth endpoints — registration, login, session (PRD §6).

GET  /api/auth/setup    — public; {needs_setup: bool} (true when no users yet)
POST /api/auth/setup    — DEPRECATED public wrapper → delegates to register
POST /api/auth/register — public signup (rate-limited); first user = admin/active
                          + auto-login, subsequent = user/pending (201, no session)
POST /api/auth/login    — argon2 verify (DB); status-gated (pending/disabled → 403)
POST /api/auth/logout   — clear session (204)
GET  /api/auth/me       — current session {username, role, status} (401 if absent)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.deps import AppError, require_login
from app.api.ratelimit import LOGIN_RATE, client_key, failure_tracker, limiter
from app.db.models import User
from app.db.session import get_session
from app.services.auth import (
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_PENDING,
    admin_exists,
    authenticate,
    register_user,
)

logger = logging.getLogger("app.api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class RegisterRequest(BaseModel):
    # Built-in length constraints produce JSON-serialisable validation errors
    # (the standard 422 envelope renders ``exc.errors()`` directly).
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)


# Backward-compatible alias for the deprecated setup flow.
SetupRequest = RegisterRequest


class UserResponse(BaseModel):
    username: str


class RegisterResponse(BaseModel):
    username: str
    role: str
    status: str


class MeResponse(BaseModel):
    username: str
    role: str
    status: str


class SetupStatusResponse(BaseModel):
    needs_setup: bool


def _login_session(request: Request, user: User) -> None:
    """Persist the authenticated identity into the session cookie."""
    request.session["user_id"] = user.id
    request.session["role"] = user.role
    # Keep the legacy key so anything still reading ``user`` keeps working.
    request.session["user"] = user.username


@router.get("/setup", response_model=SetupStatusResponse)
async def setup_status(
    session: Session = Depends(get_session),
) -> SetupStatusResponse:
    """Public: report whether the bootstrap admin still needs to be created."""
    return SetupStatusResponse(needs_setup=not admin_exists(session))


@router.post("/register", response_model=RegisterResponse, status_code=201)
@limiter.limit(LOGIN_RATE)
async def register(
    request: Request,
    body: RegisterRequest,
    session: Session = Depends(get_session),
) -> Response:
    """Public signup (PRD §6.1).

    - First ever user → ``admin``/``active`` + auto-login, 201.
    - Subsequent users → ``user``/``pending``, 201, no session issued.
    - Duplicate username → 409 ``username_taken``.
    """
    ip = client_key(request)
    failure_tracker.check_blocked(ip)
    try:
        user = register_user(session, body.username, body.password)
    except ValueError:
        raise AppError(
            "username_taken", 409, "Username already taken"
        ) from None

    if user.status == STATUS_ACTIVE:
        # Bootstrap admin: auto-login.
        _login_session(request, user)
        logger.warning("Bootstrap admin registered user=%s ip=%s", user.username, ip)
    else:
        logger.info("Signup pending approval user=%s ip=%s", user.username, ip)

    return RegisterResponse(
        username=user.username, role=user.role, status=user.status
    )


@router.post("/setup", response_model=RegisterResponse, status_code=201)
@limiter.limit(LOGIN_RATE)
async def setup(
    request: Request,
    body: SetupRequest,
    session: Session = Depends(get_session),
) -> Response:
    """DEPRECATED: kept for backward compatibility — delegates to register.

    Historically this created the single admin. It now simply forwards to the
    registration flow (first user → admin/active + auto-login). Will be removed
    after 1–2 releases (PRD Open Question #1).
    """
    return await register(request, body, session)


@router.post("/login", response_model=MeResponse)
@limiter.limit(LOGIN_RATE)
async def login(
    request: Request,
    body: LoginRequest,
    session: Session = Depends(get_session),
) -> Response:
    ip = client_key(request)
    # Reject early if this IP is in a temporary block window.
    failure_tracker.check_blocked(ip)
    user = authenticate(session, body.username, body.password)
    if user is None:
        failure_tracker.record_failure(ip)
        logger.warning("Login FAILED for user=%s ip=%s", body.username, ip)
        raise AppError("unauthorized", 401, "Invalid credentials")

    # Status gate (PRD §6.1): only active accounts may log in.
    if user.status == STATUS_PENDING:
        raise AppError("account_pending", 403, "Account awaiting admin approval")
    if user.status == STATUS_DISABLED:
        raise AppError("account_disabled", 403, "Account has been disabled")

    failure_tracker.record_success(ip)
    _login_session(request, user)
    logger.warning("Login OK for user=%s ip=%s", user.username, ip)
    return MeResponse(username=user.username, role=user.role, status=user.status)


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/me", response_model=MeResponse)
async def me(user: User = Depends(require_login)) -> MeResponse:
    return MeResponse(username=user.username, role=user.role, status=user.status)
