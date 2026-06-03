"""GET /healthz must be public and return {status: ok}."""

from __future__ import annotations

from httpx import AsyncClient


async def test_healthz_returns_ok(client: AsyncClient) -> None:
    resp = await client.get("/healthz")
    assert resp.status_code == 200
    assert resp.json() == {"status": "ok"}


async def test_healthz_requires_no_auth(client: AsyncClient) -> None:
    # No session cookie / auth header sent at all.
    resp = await client.get("/healthz", headers={})
    assert resp.status_code == 200
