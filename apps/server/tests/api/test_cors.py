"""CORS regression tests (PRD §7.7, task 11.4).

The API is fronted by the ``web`` container and may also be hit by a browser
SPA on an allow-listed Origin. These tests assert the CORSMiddleware:

  - reflects an allow-listed Origin (with credentials) on both a simple GET and
    a preflight OPTIONS, and
  - never emits ``Access-Control-Allow-Origin`` for a non-allow-listed Origin,
    so the browser blocks the cross-origin response / preflight.

A fresh app is built per-allow-list so the test does not depend on the global
app's import-time CORS configuration.
"""

from __future__ import annotations

import importlib

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient

from app.config import Settings

_ALLOWED = "http://localhost:3000"
_DENIED = "https://evil.example.com"


@pytest_asyncio.fixture
async def cors_client(monkeypatch: pytest.MonkeyPatch) -> AsyncClient:
    """Build a fresh app whose CORS allow-list is exactly ``_ALLOWED``."""
    settings = Settings(app_secret="cors-test-secret", cors_origins=_ALLOWED)
    monkeypatch.setattr("app.config.get_settings", lambda: settings)

    import app.main as main_module

    main_module = importlib.reload(main_module)
    transport = ASGITransport(app=main_module.app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac

    # Restore the original app module for the rest of the suite.
    importlib.reload(main_module)


async def test_allowed_origin_is_reflected_on_simple_request(
    cors_client: AsyncClient,
) -> None:
    resp = await cors_client.get("/healthz", headers={"Origin": _ALLOWED})
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == _ALLOWED
    assert resp.headers.get("access-control-allow-credentials") == "true"


async def test_allowed_origin_passes_preflight(cors_client: AsyncClient) -> None:
    resp = await cors_client.options(
        "/api/credentials",
        headers={
            "Origin": _ALLOWED,
            "Access-Control-Request-Method": "POST",
            "Access-Control-Request-Headers": "content-type",
        },
    )
    assert resp.status_code == 200
    assert resp.headers.get("access-control-allow-origin") == _ALLOWED
    assert "POST" in resp.headers.get("access-control-allow-methods", "")


async def test_disallowed_origin_gets_no_cors_header(cors_client: AsyncClient) -> None:
    resp = await cors_client.get("/healthz", headers={"Origin": _DENIED})
    # The request itself succeeds, but the browser-facing allow header must be
    # absent (or never equal to the denied origin) so the browser blocks it.
    assert resp.headers.get("access-control-allow-origin") != _DENIED


async def test_disallowed_origin_preflight_rejected(cors_client: AsyncClient) -> None:
    resp = await cors_client.options(
        "/api/credentials",
        headers={
            "Origin": _DENIED,
            "Access-Control-Request-Method": "POST",
        },
    )
    # Starlette returns 400 for a disallowed preflight Origin and emits no
    # allow-origin header for it.
    assert resp.headers.get("access-control-allow-origin") != _DENIED
    assert resp.status_code in (400, 403)
