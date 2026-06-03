"""Single-admin auth endpoints (PRD §7.7, §8).

GET  /api/auth/setup   — public; {needs_setup: bool} (true when no admin yet)
POST /api/auth/setup   — public; first-signup creates the admin + auto-login
POST /api/auth/login   — argon2 verify (DB) → session cookie
POST /api/auth/logout  — clear session (204)
GET  /api/auth/me      — current session (401 if absent)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session

from app.api.deps import AppError, require_login
from app.api.ratelimit import LOGIN_RATE, client_key, failure_tracker, limiter
from app.db.session import get_session
from app.services.auth import admin_exists, authenticate, create_admin

logger = logging.getLogger("app.api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class SetupRequest(BaseModel):
    # Built-in length constraints produce JSON-serialisable validation errors
    # (the standard 422 envelope renders ``exc.errors()`` directly).
    username: str = Field(min_length=3)
    password: str = Field(min_length=8)


class UserResponse(BaseModel):
    username: str


class SetupStatusResponse(BaseModel):
    needs_setup: bool


@router.get("/setup", response_model=SetupStatusResponse)
async def setup_status(
    session: Session = Depends(get_session),
) -> SetupStatusResponse:
    """Public: report whether the admin account still needs to be created."""
    return SetupStatusResponse(needs_setup=not admin_exists(session))


@router.post("/setup", response_model=UserResponse)
@limiter.limit(LOGIN_RATE)
async def setup(
    request: Request,
    body: SetupRequest,
    session: Session = Depends(get_session),
) -> UserResponse:
    """Public: create the single admin (first signup) and auto-login.

    409 ``setup_already_done`` if an admin already exists.
    """
    ip = client_key(request)
    failure_tracker.check_blocked(ip)
    if admin_exists(session):
        raise AppError("setup_already_done", 409, "Admin account already exists")
    create_admin(session, body.username, body.password)
    request.session["user"] = body.username
    logger.warning("Admin setup OK for user=%s ip=%s", body.username, ip)
    return UserResponse(username=body.username)


@router.post("/login", response_model=UserResponse)
@limiter.limit(LOGIN_RATE)
async def login(
    request: Request,
    body: LoginRequest,
    session: Session = Depends(get_session),
) -> UserResponse:
    ip = client_key(request)
    # Reject early if this IP is in a temporary block window.
    failure_tracker.check_blocked(ip)
    if not authenticate(session, body.username, body.password):
        failure_tracker.record_failure(ip)
        logger.warning("Login FAILED for user=%s ip=%s", body.username, ip)
        raise AppError("unauthorized", 401, "Invalid credentials")
    failure_tracker.record_success(ip)
    request.session["user"] = body.username
    logger.warning("Login OK for user=%s ip=%s", body.username, ip)
    return UserResponse(username=body.username)


@router.post("/logout", status_code=204)
async def logout(request: Request) -> Response:
    request.session.clear()
    return Response(status_code=204)


@router.get("/me", response_model=UserResponse)
async def me(username: str = Depends(require_login)) -> UserResponse:
    return UserResponse(username=username)
