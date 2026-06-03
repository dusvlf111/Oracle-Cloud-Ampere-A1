"""FastAPI application entrypoint.

The worker (poller supervisor) will be started from the lifespan context in a
later Push; for now the lifespan is a no-op placeholder so the contract is in
place.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager, suppress
from collections.abc import AsyncIterator

from fastapi import FastAPI
from slowapi.errors import RateLimitExceeded
from starlette.middleware.sessions import SessionMiddleware

import logging

from app.api import attempts as attempts_api
from app.api import auth as auth_api
from app.api import channels as channels_api
from app.api import configs as configs_api
from app.api import credentials as credentials_api
from app.api import logs as logs_api
from app.api.deps import RequestIdMiddleware
from app.api.errors import rate_limit_handler, register_error_handlers
from app.api.ratelimit import limiter
from app.config import get_settings
from app.db.session import get_engine
from app.log_bus import attach_log_bus, log_bus
from app.logging_config import configure_logging
from app.workers.log_pruner import run_log_pruner
from app.workers.poller import poller_supervisor


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: install the three log sinks (stdout JSON + DB + in-memory bus)
    # on the root logger and bind the bus to the running event loop so the
    # synchronous handlers can marshal records onto it (PRD §9.3).
    settings = get_settings()
    db_level_name = (settings.log_level_db or settings.log_level).upper()
    db_level = getattr(logging, db_level_name, logging.INFO)
    engine = get_engine()
    configure_logging(engine=engine)
    attach_log_bus(level=db_level)
    log_bus.bind_loop()
    # Background workers (PRD §7.3.1, §9.3.8): poller supervisor manages a
    # per-config polling task; log_pruner enforces retention.
    pruner_task = asyncio.create_task(run_log_pruner(engine))
    poller_task = asyncio.create_task(poller_supervisor(engine))
    try:
        yield
    finally:
        # Graceful shutdown — cancel and await both, swallowing CancelledError
        # so child config tasks unwind cleanly (PRD §7.3.1).
        for task in (poller_task, pruner_task):
            task.cancel()
        for task in (poller_task, pruner_task):
            with suppress(asyncio.CancelledError):
                await task


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
app.include_router(credentials_api.router)
app.include_router(configs_api.router)
app.include_router(channels_api.router)
app.include_router(attempts_api.router)
app.include_router(logs_api.router)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Public, unauthenticated health check."""
    return {"status": "ok"}
