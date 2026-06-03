"""First-signup admin setup flow (PRD §7.7).

GET  /api/auth/setup  → {needs_setup}
POST /api/auth/setup  → create admin + auto-login (or 409 if already done)
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api import ratelimit

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
    assert resp.status_code == 200, resp.text
    assert resp.json() == {"username": NEW_USERNAME}
    assert "session" in resp.headers.get("set-cookie", "")

    # Auto-login: the session cookie grants immediate access to /me.
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"username": NEW_USERNAME}


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


async def test_second_setup_returns_409(client: AsyncClient, db_app) -> None:
    first = await client.post(
        "/api/auth/setup",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    assert first.status_code == 200
    second = await client.post(
        "/api/auth/setup",
        json={"username": "other", "password": "another-pw-123"},
    )
    assert second.status_code == 409
    assert second.json()["error"]["code"] == "setup_already_done"


async def test_login_succeeds_after_setup(client: AsyncClient, db_app) -> None:
    await client.post(
        "/api/auth/setup",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    # Fresh client semantics: clear session then log in explicitly.
    resp = await client.post(
        "/api/auth/login",
        json={"username": NEW_USERNAME, "password": NEW_PASSWORD},
    )
    assert resp.status_code == 200
    assert resp.json() == {"username": NEW_USERNAME}


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
    client: AsyncClient, db_app, monkeypatch: pytest.MonkeyPatch
) -> None:
    # The setup endpoint shares the login limiter (5/minute). After a successful
    # first signup, subsequent attempts return 409 but still consume the limit;
    # the 6th request within the window is rate-limited.
    codes = []
    for i in range(5):
        r = await client.post(
            "/api/auth/setup",
            json={"username": f"user{i}aa", "password": "valid-pass-123"},
        )
        codes.append(r.status_code)
    # First creates admin (200), rest are 409 (already done) but still counted.
    assert codes[0] == 200
    assert all(c == 409 for c in codes[1:])

    sixth = await client.post(
        "/api/auth/setup",
        json={"username": "user9aa", "password": "valid-pass-123"},
    )
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "rate_limited"
