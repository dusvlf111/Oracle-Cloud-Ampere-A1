"""FastAPI application entrypoint.

The worker (poller supervisor) will be started from the lifespan context in a
later Push; for now the lifespan is a no-op placeholder so the contract is in
place.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

from app.api import auth as auth_api
from app.api.deps import RequestIdMiddleware
from app.api.errors import rate_limit_handler, register_error_handlers
from app.api.ratelimit import limiter
from app.config import get_settings


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: background worker supervisor will be spawned here (Push 5).
    yield
    # Shutdown: graceful cancellation of worker tasks will go here.


app = FastAPI(title="OCI Ampere A1 Auto-Provisioner", lifespan=lifespan)

_settings = get_settings()

# Session cookie (PRD §7.7.2): HTTP-only, SameSite=Lax, Secure in prod.
# Starlette runs middleware in reverse add-order, so SessionMiddleware (added
# first here) ends up *inner* to RequestIdMiddleware — both run for every req.
app.add_middleware(
    SessionMiddleware,
    secret_key=_settings.app_secret or "dev-insecure-secret-change-me",
    session_cookie="session",
    same_site="lax",
    https_only=_settings.session_secure,
)

# Standard error envelope + request-id correlation (PRD §8).
app.add_middleware(RequestIdMiddleware)
register_error_handlers(app)

# Login rate limiting (PRD §7.7.3).
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Routers.
app.include_router(auth_api.router)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Public, unauthenticated health check."""
    return {"status": "ok"}
