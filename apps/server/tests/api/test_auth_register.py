"""Registration flow (PRD §6.1, task 9.2).

POST /api/auth/register:
  - first ever user → admin/active + auto-login (session issued)
  - subsequent users → user/pending, 201, NO session
  - duplicate username → 409 username_taken
  - rate-limited (shares the login limiter, 5/min/IP) → 429
  - /api/auth/setup remains a backward-compatible wrapper
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

FIRST = ("rootadmin", "root-pass-123")
SECOND = ("member1", "member-pass-123")


async def test_first_register_is_admin_active_and_autologs_in(
    client: AsyncClient, db_app
) -> None:
    resp = await client.post(
        "/api/auth/register", json={"username": FIRST[0], "password": FIRST[1]}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body == {"username": FIRST[0], "role": "admin", "status": "active"}
    # Auto-login: the session cookie grants immediate access to /me.
    assert "session" in resp.headers.get("set-cookie", "")
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json() == {"username": FIRST[0], "role": "admin", "status": "active"}


async def test_second_register_is_pending_without_session(
    client: AsyncClient, db_app
) -> None:
    # Bootstrap admin first (separate client so its session is isolated).
    transport_admin = AsyncClient(
        transport=client._transport, base_url="http://test"
    )
    await transport_admin.post(
        "/api/auth/register", json={"username": FIRST[0], "password": FIRST[1]}
    )
    await transport_admin.aclose()

    resp = await client.post(
        "/api/auth/register", json={"username": SECOND[0], "password": SECOND[1]}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json() == {
        "username": SECOND[0],
        "role": "user",
        "status": "pending",
    }
    # No session issued for a pending signup.
    assert "session" not in resp.headers.get("set-cookie", "")
    me = await client.get("/api/auth/me")
    assert me.status_code == 401


async def test_register_duplicate_username_409(
    client: AsyncClient, db_app
) -> None:
    await client.post(
        "/api/auth/register", json={"username": FIRST[0], "password": FIRST[1]}
    )
    dup = await client.post(
        "/api/auth/register", json={"username": FIRST[0], "password": "other-pw-1"}
    )
    assert dup.status_code == 409
    assert dup.json()["error"]["code"] == "username_taken"


@pytest.mark.parametrize(
    ("username", "password"),
    [
        ("ab", "valid-password"),  # username too short (<3)
        ("validname", "short"),  # password too short (<8)
    ],
)
async def test_register_validation_422(
    client: AsyncClient, db_app, username: str, password: str
) -> None:
    resp = await client.post(
        "/api/auth/register", json={"username": username, "password": password}
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_register_rate_limited_after_five(
    client: AsyncClient, db_app
) -> None:
    codes = []
    for i in range(5):
        r = await client.post(
            "/api/auth/register",
            json={"username": f"user{i}aa", "password": "valid-pass-123"},
        )
        codes.append(r.status_code)
    # First is admin (201), the rest are pending users (201).
    assert all(c == 201 for c in codes)
    sixth = await client.post(
        "/api/auth/register",
        json={"username": "user9aa", "password": "valid-pass-123"},
    )
    assert sixth.status_code == 429
    assert sixth.json()["error"]["code"] == "rate_limited"


async def test_setup_wrapper_still_bootstraps_admin(
    client: AsyncClient, db_app
) -> None:
    """The deprecated /setup endpoint forwards to register (admin + auto-login)."""
    resp = await client.post(
        "/api/auth/setup", json={"username": FIRST[0], "password": FIRST[1]}
    )
    assert resp.status_code == 201, resp.text
    assert resp.json()["role"] == "admin"
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
