"""InstanceConfig CRUD + toggle API tests (PRD §7.2, §8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.db.models import NotificationChannel, OciCredential


@pytest.fixture
def seed(session: Session):
    """Seed a credential + two channels in the shared in-memory DB."""
    cred = OciCredential(
        name="acct",
        tenancy_ocid="ocid1.tenancy.oc1..t",
        user_ocid="ocid1.user.oc1..u",
        fingerprint="ab:cd:ef",
        region="ap-chuncheon-1",
        private_key_path="/data/keys/1.pem",
    )
    ch1 = NotificationChannel(name="disc", type="discord", config_enc="x")
    ch2 = NotificationChannel(name="ntfy", type="ntfy", config_enc="y")
    session.add_all([cred, ch1, ch2])
    session.commit()
    session.refresh(cred)
    session.refresh(ch1)
    session.refresh(ch2)
    return {"credential_id": cred.id, "ch1": ch1.id, "ch2": ch2.id}


def _payload(credential_id: int, **overrides) -> dict:
    body = {
        "name": "ARM 4OCPU main",
        "credential_id": credential_id,
        "shape": "VM.Standard.A1.Flex",
        "ocpus": 4,
        "memory_gb": 24,
        "boot_volume_gb": 50,
        "image_ocid": "ocid1.image.oc1..img",
        "subnet_ocid": "ocid1.subnet.oc1..sub",
        "availability_domain": "Uocm:AP-CHUNCHEON-1-AD-1",
        "ssh_public_key": "ssh-ed25519 AAAA user@host",
        "retry_interval_sec": 60,
        "max_attempts": None,
        "channel_ids": [],
    }
    body.update(overrides)
    return body


async def test_requires_auth(client: AsyncClient, seed) -> None:
    assert (await client.get("/api/configs")).status_code == 401


async def test_crud_lifecycle(authed_db_client: AsyncClient, seed) -> None:
    # create
    resp = await authed_db_client.post(
        "/api/configs",
        json=_payload(seed["credential_id"], channel_ids=[seed["ch1"]]),
    )
    assert resp.status_code == 201, resp.text
    created = resp.json()
    assert created["enabled"] is True
    assert created["channel_ids"] == [seed["ch1"]]
    cid = created["id"]

    # list
    listed = (await authed_db_client.get("/api/configs")).json()
    assert any(c["id"] == cid for c in listed)

    # update — change name + channels
    upd = await authed_db_client.put(
        f"/api/configs/{cid}",
        json=_payload(
            seed["credential_id"],
            name="renamed",
            channel_ids=[seed["ch1"], seed["ch2"]],
        ),
    )
    assert upd.status_code == 200
    assert upd.json()["name"] == "renamed"
    assert sorted(upd.json()["channel_ids"]) == sorted([seed["ch1"], seed["ch2"]])

    # delete
    dele = await authed_db_client.request("DELETE", f"/api/configs/{cid}")
    assert dele.status_code == 204
    assert (await authed_db_client.get("/api/configs")).json() == []


async def test_channel_ids_replaced_on_update(
    authed_db_client: AsyncClient, seed
) -> None:
    created = (
        await authed_db_client.post(
            "/api/configs",
            json=_payload(seed["credential_id"], channel_ids=[seed["ch1"], seed["ch2"]]),
        )
    ).json()
    upd = await authed_db_client.put(
        f"/api/configs/{created['id']}",
        json=_payload(seed["credential_id"], channel_ids=[seed["ch2"]]),
    )
    assert upd.json()["channel_ids"] == [seed["ch2"]]


async def test_toggle_flips_enabled(authed_db_client: AsyncClient, seed) -> None:
    created = (
        await authed_db_client.post(
            "/api/configs", json=_payload(seed["credential_id"])
        )
    ).json()
    assert created["enabled"] is True

    t1 = await authed_db_client.post(f"/api/configs/{created['id']}/toggle")
    assert t1.json()["enabled"] is False
    t2 = await authed_db_client.post(f"/api/configs/{created['id']}/toggle")
    assert t2.json()["enabled"] is True


async def test_create_unknown_credential_404(
    authed_db_client: AsyncClient, seed
) -> None:
    resp = await authed_db_client.post(
        "/api/configs", json=_payload(99999)
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


async def test_create_unknown_channel_404(
    authed_db_client: AsyncClient, seed
) -> None:
    resp = await authed_db_client.post(
        "/api/configs",
        json=_payload(seed["credential_id"], channel_ids=[424242]),
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "channel_not_found"


async def test_create_invalid_field_422(
    authed_db_client: AsyncClient, seed
) -> None:
    resp = await authed_db_client.post(
        "/api/configs", json=_payload(seed["credential_id"], ocpus=0)
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


# --- input validation + normalisation (hardening §1) -----------------------


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("image_ocid", "ocid1.subnet.oc1..wrong"),
        ("subnet_ocid", "ocid1.image.oc1..wrong"),
        ("availability_domain", "   "),
        ("ssh_public_key", "not-a-key"),
        ("ocpus", 5),  # A1 Free Tier cap is 4
        ("memory_gb", 25),  # A1 Free Tier cap is 24
    ],
)
async def test_create_rejects_malformed(
    authed_db_client: AsyncClient, seed, field: str, value
) -> None:
    resp = await authed_db_client.post(
        "/api/configs", json=_payload(seed["credential_id"], **{field: value})
    )
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    assert field in str(body["error"]["details"])


async def test_create_normalises_whitespace_and_multiline_ssh(
    authed_db_client: AsyncClient, seed
) -> None:
    """Whitespace is stripped and a wrapped SSH key is joined to one line."""
    resp = await authed_db_client.post(
        "/api/configs",
        json=_payload(
            seed["credential_id"],
            image_ocid="  ocid1.image.oc1..img\n",
            subnet_ocid="ocid1.subnet.oc1..sub\r\n",
            availability_domain=" Uocm:AP-CHUNCHEON-1-AD-1 ",
            ssh_public_key="ssh-ed25519 AAAAB3Nza\nC1lZDI1 user@host",
        ),
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["image_ocid"] == "ocid1.image.oc1..img"
    assert body["subnet_ocid"] == "ocid1.subnet.oc1..sub"
    assert body["availability_domain"] == "Uocm:AP-CHUNCHEON-1-AD-1"
    assert "\n" not in body["ssh_public_key"]
    assert body["ssh_public_key"].startswith("ssh-ed25519 ")


async def test_update_rejects_malformed(
    authed_db_client: AsyncClient, seed
) -> None:
    created = (
        await authed_db_client.post(
            "/api/configs", json=_payload(seed["credential_id"])
        )
    ).json()
    resp = await authed_db_client.put(
        f"/api/configs/{created['id']}",
        json=_payload(seed["credential_id"], subnet_ocid="ocid1.bogus.oc1..x"),
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_update_not_found(authed_db_client: AsyncClient, seed) -> None:
    resp = await authed_db_client.put(
        "/api/configs/55555", json=_payload(seed["credential_id"])
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "config_not_found"


async def test_toggle_not_found(authed_db_client: AsyncClient, seed) -> None:
    resp = await authed_db_client.post("/api/configs/55555/toggle")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "config_not_found"
