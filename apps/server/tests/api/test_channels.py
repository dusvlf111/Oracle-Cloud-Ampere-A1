"""Notification channel API tests (PRD §7.5.2, §8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from pytest_httpx import HTTPXMock

from app.config import Settings
from app.services import crypto


@pytest.fixture
def chan_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(app_secret="channels-test-secret")
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr(crypto, "get_settings", lambda: settings)
    crypto._key_for.cache_clear()
    return settings


NTFY_BODY = {
    "name": "supabin ntfy",
    "type": "ntfy",
    "enabled": True,
    "config": {
        "type": "ntfy",
        "server_url": "https://ntfy.supabin.com",
        "topic": "oci-arm-alerts",
        "token": "tk_supersecret",
        "priority": 4,
        "tags": ["rocket"],
    },
}

DISCORD_BODY = {
    "name": "disc",
    "type": "discord",
    "enabled": True,
    "config": {
        "type": "discord",
        "webhook_url": "https://discord.com/api/webhooks/1/abcdwxyz",
    },
}


async def test_requires_auth(client: AsyncClient, chan_settings) -> None:
    assert (await client.get("/api/channels")).status_code == 401


async def test_create_ntfy_masks_token(
    authed_db_client: AsyncClient, chan_settings
) -> None:
    resp = await authed_db_client.post("/api/channels", json=NTFY_BODY)
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "ntfy"
    # token masked, non-sensitive preserved.
    assert body["config"]["token"] == "***cret"
    assert body["config"]["server_url"] == "https://ntfy.supabin.com"
    assert body["config"]["topic"] == "oci-arm-alerts"


async def test_create_discord_masks_webhook(
    authed_db_client: AsyncClient, chan_settings
) -> None:
    resp = await authed_db_client.post("/api/channels", json=DISCORD_BODY)
    assert resp.status_code == 201
    assert resp.json()["config"]["webhook_url"] == "***wxyz"


async def test_create_type_mismatch_422(
    authed_db_client: AsyncClient, chan_settings
) -> None:
    bad = {
        "name": "x",
        "type": "ntfy",
        "enabled": True,
        # discord config under an ntfy channel → discriminator picks discord,
        # then router rejects the type mismatch.
        "config": {"type": "discord", "webhook_url": "https://discord.com/x"},
    }
    resp = await authed_db_client.post("/api/channels", json=bad)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_create_invalid_config_422(
    authed_db_client: AsyncClient, chan_settings
) -> None:
    # ntfy missing required 'topic'.
    bad = {
        "name": "x",
        "type": "ntfy",
        "enabled": True,
        "config": {"type": "ntfy", "server_url": "https://ntfy.sh"},
    }
    resp = await authed_db_client.post("/api/channels", json=bad)
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_list_and_update(
    authed_db_client: AsyncClient, chan_settings
) -> None:
    created = (await authed_db_client.post("/api/channels", json=NTFY_BODY)).json()
    cid = created["id"]

    listed = (await authed_db_client.get("/api/channels")).json()
    assert any(c["id"] == cid for c in listed)
    assert listed[0]["config"]["token"] == "***cret"  # masked in list too

    upd_body = {**NTFY_BODY, "name": "renamed", "enabled": False}
    upd = await authed_db_client.put(f"/api/channels/{cid}", json=upd_body)
    assert upd.status_code == 200
    assert upd.json()["name"] == "renamed"
    assert upd.json()["enabled"] is False


async def test_delete(authed_db_client: AsyncClient, chan_settings) -> None:
    created = (await authed_db_client.post("/api/channels", json=DISCORD_BODY)).json()
    resp = await authed_db_client.request("DELETE", f"/api/channels/{created['id']}")
    assert resp.status_code == 204
    assert (await authed_db_client.get("/api/channels")).json() == []


async def test_delete_not_found(
    authed_db_client: AsyncClient, chan_settings
) -> None:
    resp = await authed_db_client.request("DELETE", "/api/channels/9999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "channel_not_found"


async def test_test_send_ok(
    authed_db_client: AsyncClient, chan_settings, httpx_mock: HTTPXMock
) -> None:
    created = (await authed_db_client.post("/api/channels", json=NTFY_BODY)).json()
    httpx_mock.add_response(
        url="https://ntfy.supabin.com/oci-arm-alerts", status_code=200
    )
    resp = await authed_db_client.post(f"/api/channels/{created['id']}/test")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "error": None}


async def test_test_send_failure_still_200(
    authed_db_client: AsyncClient, chan_settings, httpx_mock: HTTPXMock
) -> None:
    created = (await authed_db_client.post("/api/channels", json=DISCORD_BODY)).json()
    # 4xx → not retried, surfaces as ok=false.
    httpx_mock.add_response(
        url="https://discord.com/api/webhooks/1/abcdwxyz", status_code=404
    )
    resp = await authed_db_client.post(f"/api/channels/{created['id']}/test")
    assert resp.status_code == 200
    assert resp.json()["ok"] is False
    assert resp.json()["error"]


async def test_test_send_not_found(
    authed_db_client: AsyncClient, chan_settings
) -> None:
    resp = await authed_db_client.post("/api/channels/9999/test")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "channel_not_found"
