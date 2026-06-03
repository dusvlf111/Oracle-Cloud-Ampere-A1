"""Session + auth API: login/logout/me (PRD §7.7, task 2.3)."""

from __future__ import annotations

from httpx import AsyncClient

from tests.conftest import TEST_PASSWORD, TEST_USERNAME


async def test_login_sets_cookie_and_me_succeeds(
    client: AsyncClient, admin_settings
) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.json() == {"username": TEST_USERNAME}
    assert "session" in resp.headers.get("set-cookie", "")

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"username": TEST_USERNAME}


async def test_login_wrong_password_401(client: AsyncClient, admin_settings) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": "wrong"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_me_requires_session_401(client: AsyncClient, admin_settings) -> None:
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_logout_then_me_401(authed_client: AsyncClient) -> None:
    # authed_client is already logged in.
    me = await authed_client.get("/api/auth/me")
    assert me.status_code == 200

    logout = await authed_client.post("/api/auth/logout")
    assert logout.status_code == 204

    me2 = await authed_client.get("/api/auth/me")
    assert me2.status_code == 401
    assert me2.json()["error"]["code"] == "unauthorized"
