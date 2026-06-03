"""Standard error envelope + RequestIdMiddleware (PRD §8, task 2.1)."""

from __future__ import annotations

import pytest
from httpx import ASGITransport, AsyncClient
from pydantic import BaseModel

from app.api.deps import AppError
from app.main import app


# --- throwaway routes mounted once for these tests --------------------------


class _Body(BaseModel):
    n: int


def _ensure_test_routes() -> None:
    if getattr(_ensure_test_routes, "_done", False):
        return

    @app.get("/__test__/app-error")
    async def _raise_app_error() -> None:
        raise AppError(
            "config_not_found",
            404,
            "InstanceConfig id=42 not found",
            {"config_id": 42},
        )

    @app.get("/__test__/boom")
    async def _raise_unhandled() -> None:
        raise RuntimeError("kaboom")

    @app.post("/__test__/validate")
    async def _validate(body: _Body) -> dict:
        return {"n": body.n}

    _ensure_test_routes._done = True  # type: ignore[attr-defined]


@pytest.fixture(autouse=True)
def _routes() -> None:
    _ensure_test_routes()


@pytest.fixture
async def raw_client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


async def test_app_error_renders_standard_envelope(raw_client: AsyncClient) -> None:
    resp = await raw_client.get("/__test__/app-error")
    assert resp.status_code == 404
    body = resp.json()
    assert set(body["error"]) == {"code", "message", "details", "request_id"}
    assert body["error"]["code"] == "config_not_found"
    assert body["error"]["details"] == {"config_id": 42}
    assert body["error"]["request_id"]


async def test_request_id_header_matches_body(raw_client: AsyncClient) -> None:
    resp = await raw_client.get("/__test__/app-error")
    header_id = resp.headers["X-Request-Id"]
    assert header_id
    assert header_id == resp.json()["error"]["request_id"]


async def test_healthz_carries_request_id_header(raw_client: AsyncClient) -> None:
    resp = await raw_client.get("/healthz")
    assert resp.status_code == 200
    assert resp.headers.get("X-Request-Id")


async def test_validation_error_maps_to_422(raw_client: AsyncClient) -> None:
    resp = await raw_client.post("/__test__/validate", json={"n": "not-an-int"})
    assert resp.status_code == 422
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert body["error"]["details"]["errors"]
    assert body["error"]["request_id"]


async def test_unhandled_exception_maps_to_500(raw_client: AsyncClient) -> None:
    transport = ASGITransport(app=app, raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.get("/__test__/boom")
    assert resp.status_code == 500
    body = resp.json()
    assert body["error"]["code"] == "internal_error"
    assert body["error"]["request_id"]
