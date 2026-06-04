"""Polling status API tests (PRD §7.3, §7.4)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.db.models import Attempt, InstanceConfig, OciCredential


@pytest.fixture
def seed_polling(session: Session, admin_settings):
    oid = admin_settings.id
    cred = OciCredential(
        name="acct",
        tenancy_ocid="ocid1.tenancy.oc1..t",
        user_ocid="ocid1.user.oc1..u",
        fingerprint="ab:cd",
        region="ap-chuncheon-1",
        private_key_path="/data/keys/1.pem",
        owner_id=oid,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)

    def _cfg(name: str, *, enabled: bool) -> int:
        c = InstanceConfig(
            name=name,
            credential_id=cred.id,
            owner_id=oid,
            enabled=enabled,
            shape="VM.Standard.A1.Flex",
            ocpus=4,
            memory_gb=24,
            retry_interval_sec=90,
            image_ocid="i",
            subnet_ocid="s",
            availability_domain="ad",
            ssh_public_key="k",
        )
        session.add(c)
        session.commit()
        session.refresh(c)
        return c.id

    active_with = _cfg("active-with-attempts", enabled=True)
    active_without = _cfg("active-no-attempts", enabled=True)
    disabled = _cfg("disabled", enabled=False)

    session.add_all(
        [
            Attempt(config_id=active_with, status="out_of_capacity"),
            Attempt(config_id=active_with, status="rate_limited"),
            Attempt(config_id=disabled, status="success"),
        ]
    )
    session.commit()
    return {
        "active_with": active_with,
        "active_without": active_without,
        "disabled": disabled,
        "credential_name": "acct",
    }


async def test_requires_auth(client: AsyncClient, seed_polling) -> None:
    assert (await client.get("/api/status/polling")).status_code == 401


async def test_only_enabled_configs(
    authed_db_client: AsyncClient, seed_polling
) -> None:
    resp = await authed_db_client.get("/api/status/polling")
    assert resp.status_code == 200
    items = resp.json()
    ids = {i["config_id"] for i in items}
    assert ids == {seed_polling["active_with"], seed_polling["active_without"]}
    assert seed_polling["disabled"] not in ids


async def test_attempt_summary_fields(
    authed_db_client: AsyncClient, seed_polling
) -> None:
    resp = await authed_db_client.get("/api/status/polling")
    items = {i["config_id"]: i for i in resp.json()}

    with_attempts = items[seed_polling["active_with"]]
    assert with_attempts["config_name"] == "active-with-attempts"
    assert with_attempts["credential_name"] == seed_polling["credential_name"]
    assert with_attempts["shape"] == "VM.Standard.A1.Flex"
    assert with_attempts["ocpus"] == 4
    assert with_attempts["memory_gb"] == 24
    assert with_attempts["retry_interval_sec"] == 90
    assert with_attempts["total_attempts"] == 2
    # Newest attempt wins (rate_limited was added last).
    assert with_attempts["last_attempt_status"] == "rate_limited"
    assert with_attempts["last_attempt_at"] is not None


async def test_config_without_attempts(
    authed_db_client: AsyncClient, seed_polling
) -> None:
    resp = await authed_db_client.get("/api/status/polling")
    items = {i["config_id"]: i for i in resp.json()}

    none_yet = items[seed_polling["active_without"]]
    assert none_yet["total_attempts"] == 0
    assert none_yet["last_attempt_status"] is None
    assert none_yet["last_attempt_at"] is None
