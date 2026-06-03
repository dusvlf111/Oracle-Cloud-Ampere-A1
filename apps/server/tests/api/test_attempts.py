"""Attempt history API tests (PRD §7.4, §8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.db.models import Attempt, InstanceConfig, OciCredential


@pytest.fixture
def seed_attempts(session: Session):
    cred = OciCredential(
        name="acct",
        tenancy_ocid="ocid1.tenancy.oc1..t",
        user_ocid="ocid1.user.oc1..u",
        fingerprint="ab:cd",
        region="ap-chuncheon-1",
        private_key_path="/data/keys/1.pem",
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)

    def _cfg(name: str) -> int:
        c = InstanceConfig(
            name=name,
            credential_id=cred.id,
            image_ocid="i",
            subnet_ocid="s",
            availability_domain="ad",
            ssh_public_key="k",
        )
        session.add(c)
        session.commit()
        session.refresh(c)
        return c.id

    cfg1, cfg2 = _cfg("c1"), _cfg("c2")
    rows = [
        Attempt(config_id=cfg1, status="out_of_capacity"),
        Attempt(config_id=cfg1, status="success", instance_ocid="ocid1.instance..x"),
        Attempt(config_id=cfg2, status="rate_limited"),
        Attempt(config_id=cfg2, status="out_of_capacity"),
    ]
    session.add_all(rows)
    session.commit()
    return {"cfg1": cfg1, "cfg2": cfg2}


async def test_requires_auth(client: AsyncClient, seed_attempts) -> None:
    assert (await client.get("/api/attempts")).status_code == 401


async def test_list_all_newest_first(
    authed_db_client: AsyncClient, seed_attempts
) -> None:
    resp = await authed_db_client.get("/api/attempts")
    assert resp.status_code == 200
    items = resp.json()
    assert len(items) == 4
    ids = [i["id"] for i in items]
    assert ids == sorted(ids, reverse=True)


async def test_filter_by_config_id(
    authed_db_client: AsyncClient, seed_attempts
) -> None:
    resp = await authed_db_client.get(
        f"/api/attempts?config_id={seed_attempts['cfg1']}"
    )
    items = resp.json()
    assert {i["config_id"] for i in items} == {seed_attempts["cfg1"]}
    assert len(items) == 2


async def test_filter_by_status(
    authed_db_client: AsyncClient, seed_attempts
) -> None:
    resp = await authed_db_client.get("/api/attempts?status=out_of_capacity")
    items = resp.json()
    assert {i["status"] for i in items} == {"out_of_capacity"}
    assert len(items) == 2


async def test_combined_filter_and_limit(
    authed_db_client: AsyncClient, seed_attempts
) -> None:
    resp = await authed_db_client.get(
        f"/api/attempts?config_id={seed_attempts['cfg2']}&status=rate_limited&limit=10"
    )
    items = resp.json()
    assert len(items) == 1
    assert items[0]["status"] == "rate_limited"


async def test_limit_validation(
    authed_db_client: AsyncClient, seed_attempts
) -> None:
    resp = await authed_db_client.get("/api/attempts?limit=0")
    assert resp.status_code == 422
