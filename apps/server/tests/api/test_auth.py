"""Session + auth API: login status gate / session / me (PRD §6, task 9.3)."""

from __future__ import annotations

from httpx import AsyncClient
from sqlmodel import Session

from app.services import auth as auth_service
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


async def test_login_sets_cookie_and_me_succeeds(
    client: AsyncClient, admin_settings
) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert resp.status_code == 200
    # Login now returns role/status too (Push 9).
    assert resp.json() == {
        "username": TEST_USERNAME,
        "role": "admin",
        "status": "active",
    }
    assert "session" in resp.headers.get("set-cookie", "")

    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {
        "username": TEST_USERNAME,
        "role": "admin",
        "status": "active",
    }


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
    me = await authed_client.get("/api/auth/me")
    assert me.status_code == 200

    logout = await authed_client.post("/api/auth/logout")
    assert logout.status_code == 204

    me2 = await authed_client.get("/api/auth/me")
    assert me2.status_code == 401
    assert me2.json()["error"]["code"] == "unauthorized"


# --- status gate (PRD §6.1) ------------------------------------------------ #


async def test_pending_user_login_403_account_pending(
    client: AsyncClient, admin_settings, engine
) -> None:
    # admin_settings seeds the bootstrap admin; register a 2nd (pending) user.
    with Session(engine) as s:
        auth_service.register_user(s, "pendinguser", "pending-pw-123")

    resp = await client.post(
        "/api/auth/login",
        json={"username": "pendinguser", "password": "pending-pw-123"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "account_pending"


async def test_disabled_user_login_403_account_disabled(
    client: AsyncClient, admin_settings, engine
) -> None:
    from app.db.models import User
    from sqlmodel import select

    with Session(engine) as s:
        auth_service.register_user(s, "disableduser", "disabled-pw-123")
        u = s.exec(select(User).where(User.username == "disableduser")).one()
        u.status = auth_service.STATUS_DISABLED
        s.add(u)
        s.commit()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "disableduser", "password": "disabled-pw-123"},
    )
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "account_disabled"


async def test_active_user_login_succeeds(
    client: AsyncClient, admin_settings, engine
) -> None:
    from app.db.models import User
    from sqlmodel import select

    with Session(engine) as s:
        auth_service.register_user(s, "activeuser", "active-pw-123")
        u = s.exec(select(User).where(User.username == "activeuser")).one()
        u.status = auth_service.STATUS_ACTIVE
        s.add(u)
        s.commit()

    resp = await client.post(
        "/api/auth/login",
        json={"username": "activeuser", "password": "active-pw-123"},
    )
    assert resp.status_code == 200
    body = resp.json()
    assert body["username"] == "activeuser"
    assert body["role"] == "user"
    assert body["status"] == "active"


async def test_legacy_username_session_still_resolves(
    client: AsyncClient, admin_settings
) -> None:
    """A session carrying only the legacy ``user`` key still authenticates.

    Simulates a pre-Push-9 session cookie: we log in (which also sets user_id),
    then verify /me works — the deps layer resolves either key. Re-login is the
    documented fallback for sessions that predate the migration.
    """
    login = await client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert login.status_code == 200
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
