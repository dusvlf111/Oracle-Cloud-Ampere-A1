"""Resource ownership scoping (PRD §6.3, task 9.5).

Two regular users A/B plus the bootstrap admin. Verifies:
  - A cannot see/modify/delete B's credential/config/channel (404 isolation)
  - admin sees everyone's resources
  - a config can only link channels owned by the same user (422 owner_mismatch)
  - create auto-assigns owner_id = current user
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.db.models import NotificationChannel, OciCredential

_FINGERPRINT = "ab:cd:ef:12:34:56:78:90:ab:cd:ef:12:34:56:78:90"


@pytest.fixture
def cred_settings(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app.config import Settings
    from app.services import crypto

    settings = Settings(app_secret="scope-secret")
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr(crypto, "get_settings", lambda: settings)
    crypto._key_for.cache_clear()
    crypto._fernet_key_for.cache_clear()
    return settings


async def _create_cred(client: AsyncClient, name: str) -> int:
    data = {
        "name": name,
        "tenancy_ocid": "ocid1.tenancy.oc1..aaaaaaaatenancy",
        "user_ocid": "ocid1.user.oc1..aaaaaaaauser",
        "fingerprint": _FINGERPRINT,
        "region": "ap-chuncheon-1",
    }
    files = {"private_key": ("oci.pem", b"-----BEGIN-----\nx\n-----END-----", "x")}
    resp = await client.post("/api/credentials", data=data, files=files)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


async def _create_channel(client: AsyncClient, name: str) -> int:
    resp = await client.post(
        "/api/channels",
        json={
            "name": name,
            "type": "ntfy",
            "enabled": True,
            "config": {
                "type": "ntfy",
                "server_url": "https://ntfy.sh",
                "topic": "t",
            },
        },
    )
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


@pytest.fixture
def two_users(make_user):
    a = make_user("alice")
    b = make_user("bob")
    return {"alice": a, "bob": b}


async def test_user_cannot_see_others_credentials(
    admin_settings, two_users, login_as, cred_settings
) -> None:
    a_client = await login_as("alice")
    b_client = await login_as("bob")

    a_cred = await _create_cred(a_client, "alice-cred")
    await _create_cred(b_client, "bob-cred")

    # A's list shows only A's credential.
    a_list = (await a_client.get("/api/credentials")).json()
    assert {c["name"] for c in a_list} == {"alice-cred"}

    # B cannot fetch/verify/delete A's credential (404 isolation).
    assert (await b_client.post(f"/api/credentials/{a_cred}/verify")).status_code == 404
    assert (
        await b_client.request("DELETE", f"/api/credentials/{a_cred}")
    ).status_code == 404


async def test_admin_sees_all_credentials(
    admin_settings, two_users, login_as, cred_settings
) -> None:
    a_client = await login_as("alice")
    b_client = await login_as("bob")
    await _create_cred(a_client, "alice-cred")
    await _create_cred(b_client, "bob-cred")

    # Admin (authed via admin_settings) sees both.
    admin_client = await login_as_admin(login_as)
    rows = (await admin_client.get("/api/credentials")).json()
    assert {c["name"] for c in rows} >= {"alice-cred", "bob-cred"}


async def login_as_admin(login_as) -> AsyncClient:
    from tests.conftest import TEST_PASSWORD, TEST_USERNAME

    return await login_as(TEST_USERNAME, TEST_PASSWORD)


async def test_user_cannot_see_others_channels(
    admin_settings, two_users, login_as, cred_settings
) -> None:
    a_client = await login_as("alice")
    b_client = await login_as("bob")
    a_ch = await _create_channel(a_client, "alice-ch")
    await _create_channel(b_client, "bob-ch")

    b_list = (await b_client.get("/api/channels")).json()
    assert {c["name"] for c in b_list} == {"bob-ch"}
    # B cannot touch A's channel.
    assert (await b_client.post(f"/api/channels/{a_ch}/test")).status_code == 404
    assert (
        await b_client.request("DELETE", f"/api/channels/{a_ch}")
    ).status_code == 404


async def test_config_link_rejects_other_owner_channel_422(
    admin_settings, two_users, login_as, cred_settings, engine
) -> None:
    a_client = await login_as("alice")
    b_client = await login_as("bob")

    a_cred = await _create_cred(a_client, "alice-cred")
    b_ch = await _create_channel(b_client, "bob-ch")

    # Alice tries to attach Bob's channel to her config. Bob's channel is not
    # visible to Alice → 404 channel_not_found (isolation precedes 422).
    payload = {
        "name": "cfg",
        "credential_id": a_cred,
        "shape": "VM.Standard.A1.Flex",
        "ocpus": 4,
        "memory_gb": 24,
        "boot_volume_gb": 50,
        "image_ocid": "ocid1.image.oc1..img",
        "subnet_ocid": "ocid1.subnet.oc1..sub",
        "availability_domain": "AD-1",
        "ssh_public_key": "ssh-ed25519 AAAA user@host",
        "retry_interval_sec": 60,
        "max_attempts": None,
        "channel_ids": [b_ch],
    }
    resp = await a_client.post("/api/configs", json=payload)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "channel_not_found"


async def test_admin_link_cross_owner_channel_422(
    admin_settings, two_users, login_as, cred_settings, engine
) -> None:
    """Admin can see all, but same-owner linkage is still enforced (422)."""
    a_client = await login_as("alice")
    admin_client = await login_as_admin(login_as)

    a_cred = await _create_cred(a_client, "alice-cred2")
    # Admin owns this channel.
    admin_ch = await _create_channel(admin_client, "admin-ch")

    # Admin creates a config owned by admin, but tries to attach... actually the
    # config owner is admin here, and the channel is admin's → allowed. Instead
    # build the mismatch: admin-owned config + alice-owned channel.
    a_ch = await _create_channel(a_client, "alice-ch2")
    payload = {
        "name": "cfg-admin",
        "credential_id": a_cred,  # alice's cred — admin can see it
        "shape": "VM.Standard.A1.Flex",
        "ocpus": 4,
        "memory_gb": 24,
        "boot_volume_gb": 50,
        "image_ocid": "ocid1.image.oc1..img",
        "subnet_ocid": "ocid1.subnet.oc1..sub",
        "availability_domain": "AD-1",
        "ssh_public_key": "ssh-ed25519 AAAA user@host",
        "retry_interval_sec": 60,
        "max_attempts": None,
        "channel_ids": [a_ch, admin_ch],  # mixed owners
    }
    resp = await admin_client.post("/api/configs", json=payload)
    # Config owner = admin; a_ch belongs to alice → owner_mismatch 422.
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "owner_mismatch"


async def test_create_assigns_owner(
    admin_settings, two_users, login_as, engine, cred_settings
) -> None:
    a_client = await login_as("alice")
    ch_id = await _create_channel(a_client, "alice-owned")
    with Session(engine) as s:
        ch = s.get(NotificationChannel, ch_id)
        assert ch.owner_id == two_users["alice"]
