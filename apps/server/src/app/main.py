"""FastAPI application entrypoint.

The worker (poller supervisor) will be started from the lifespan context in a
later Push; for now the lifespan is a no-op placeholder so the contract is in
place.
"""

from __future__ import annotations

from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from fastapi import FastAPI

from app.api.deps import RequestIdMiddleware
from app.api.errors import register_error_handlers


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    # Startup: background worker supervisor will be spawned here (Push 5).
    yield
    # Shutdown: graceful cancellation of worker tasks will go here.


app = FastAPI(title="OCI Ampere A1 Auto-Provisioner", lifespan=lifespan)

# Standard error envelope + request-id correlation (PRD §8).
app.add_middleware(RequestIdMiddleware)
register_error_handlers(app)


@app.get("/healthz", tags=["meta"])
async def healthz() -> dict[str, str]:
    """Public, unauthenticated health check."""
    return {"status": "ok"}
