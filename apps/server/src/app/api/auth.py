"""Single-admin auth endpoints (PRD §7.7, §8).

POST /api/auth/login   — argon2 verify → session cookie
POST /api/auth/logout  — clear session (204)
GET  /api/auth/me      — current session (401 if absent)
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel

from app.api.deps import AppError, require_login
from app.api.ratelimit import LOGIN_RATE, client_key, failure_tracker, limiter
from app.services.auth import authenticate

logger = logging.getLogger("app.api.auth")

router = APIRouter(prefix="/api/auth", tags=["auth"])


class LoginRequest(BaseModel):
    username: str
    password: str


class UserResponse(BaseModel):
    username: str


@router.post("/login", response_model=UserResponse)
@limiter.limit(LOGIN_RATE)
async def login(request: Request, body: LoginRequest) -> UserResponse:
    ip = client_key(request)
    # Reject early if this IP is in a temporary block window.
    failure_tracker.check_blocked(ip)
    if not authenticate(body.username, body.password):
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
