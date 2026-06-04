"""Backward-compatible setup flow (PRD §6.1, Open Question #1).

GET  /api/auth/setup  → {needs_setup}
POST /api/auth/setup  → DEPRECATED wrapper; forwards to register. The first
                        signup becomes admin/active + auto-login; later signups
                        are pending users (no longer 409 "already done").
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

NEW_USERNAME = "operator"
NEW_PASSWORD = "sup3r-secret-pw"


async def test_setup_status_true_when_no_admin(
    client: AsyncClient, db_app
) -> None:
    resp = await client.get("/api/auth/setup")
    assert resp.status_code == 200
    assert resp.json() == {"needs_setup": True}


async def test_setup_creates_admin_and_auto_logs_in(
    client: AsyncClient, db_app
) -> None:
    resp = await client.post(
        "/api/auth/setup",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["username"] == NEW_USERNAME
    assert body["role"] == "admin"
    assert body["status"] == "active"
    assert "session" in resp.headers.get("set-cookie", "")

    # Auto-login: the session cookie grants immediate access to /me.
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["username"] == NEW_USERNAME


async def test_setup_status_false_after_setup(
    client: AsyncClient, db_app
) -> None:
    await client.post(
        "/api/auth/setup",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    resp = await client.get("/api/auth/setup")
    assert resp.status_code == 200
    assert resp.json() == {"needs_setup": False}


async def test_second_setup_creates_pending_user(client: AsyncClient, db_app) -> None:
    first = await client.post(
        "/api/auth/setup",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    assert first.status_code == 201
    assert first.json()["role"] == "admin"
    second = await client.post(
        "/api/auth/setup",
        json={"username": "other", "password": "another-pw-123"},
    )
    # Now a normal pending signup rather than a 409.
    assert second.status_code == 201
    assert second.json() == {
        "username": "other",
        "role": "user",
        "status": "pending",
    }


async def test_login_succeeds_after_setup(client: AsyncClient, db_app) -> None:
    await client.post(
        "/api/auth/setup",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.json()["username"] == NEW_USERNAME


async def test_login_wrong_password_after_setup_401(
    client: AsyncClient, db_app
) -> None:
    await client.post(
        "/api/auth/setup",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    resp = await client.post(
        "/api/auth/login",
        json={"username": NEW_USERNAME, "password": "wrong-password"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


async def test_login_before_any_setup_401(client: AsyncClient, db_app) -> None:
    resp = await client.post(
        "/api/auth/login",
        json={"username": "admin", "password": "whatever-123"},
    )
    assert resp.status_code == 401
    assert resp.json()["error"]["code"] == "unauthorized"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("ab", "valid-password"),  # username too short (<3)
        ("validname", "short"),  # password too short (<8)
    ],
)
async def test_setup_validation_422(
    client: AsyncClient, db_app, username: str, password: str
) -> None:
    resp = await client.post(
        "/api/auth/setup",
        json={"username": username, "password": password},
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_setup_rate_limited_after_five(
    client: AsyncClient, db_app
) -> None:
    # The setup endpoint shares the login limiter (5/minute). Each signup now
    # succeeds (admin then pending users); the 6th request is rate-limited.
    codes = []
    for i in range(5):
        r = await client.post(
            "/api/auth/setup",
            json={"username": f"user{i}aa", "password": "valid-pass-123"},
        )
        codes.append(r.status_code)
    assert all(c == 201 for c in codes)

    sixth = await client.post(
        "/api/auth/setup",
        json={"username": "user9aa", "password": "valid-pass-123"},
    )
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "rate_limited"
