"""Brute-force defense: slowapi rate limit + IP block (PRD §7.7.3, task 2.4)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.api import ratelimit
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


async def _bad_login(client: AsyncClient):
    return await client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": "wrong"},
    )


async def test_sixth_request_per_minute_is_429(
    client: AsyncClient, admin_settings
) -> None:
    # 5/minute allowed; the 6th within the window is rate-limited.
    codes = [(await _bad_login(client)).status_code for _ in range(5)]
    assert codes == [401, 401, 401, 401, 401]
    sixth = await _bad_login(client)
    assert sixth.status_code == 429
    body = sixth.json()
    assert body["error"]["code"] == "rate_limited"
    assert "retry_after_sec" in body["error"]["details"]


async def test_ten_consecutive_failures_block_ip(
    client: AsyncClient, admin_settings, monkeypatch: pytest.MonkeyPatch
) -> None:
    # Disable the per-minute slowapi cap so we can reach 10 failures, isolating
    # the consecutive-failure block behavior.
    monkeypatch.setattr(ratelimit.limiter, "enabled", False)

    clock = {"t": 1000.0}
    monkeypatch.setattr(ratelimit, "_now", lambda: clock["t"])

    for _ in range(10):
        assert (await _bad_login(client)).status_code == 401

    # 11th attempt is blocked even though credentials are now correct.
    blocked = await client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert blocked.status_code == 429
    assert blocked.json()["error"]["code"] == "rate_limited"

    # After the 5-minute block window elapses, login succeeds again.
    clock["t"] += ratelimit.BLOCK_DURATION_SEC + 1
    ok = await client.post(
        "/api/auth/login",
        json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
    )
    assert ok.status_code == 200
