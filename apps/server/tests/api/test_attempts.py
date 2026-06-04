"""Attempt history API tests (PRD §7.4, §8)."""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.db.models import Attempt, InstanceConfig, OciCredential


@pytest.fixture
def seed_attempts(session: Session, admin_settings):
    oid = admin_settings.id
    cred = OciCredential(
        name="acct",
        tenancy_ocid="ocid1.tenancy.oc1..t",
        user_ocid="ocid1.user.oc1..u",
        fingerprint="ab:cd",
        region="ap-chuncheon-1",
        private_key_enc="enc",
        owner_id=oid,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)

    def _cfg(name: str) -> int:
        c = InstanceConfig(
            name=name,
            credential_id=cred.id,
            owner_id=oid,
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


async def test_includes_config_and_credential_names(
    authed_db_client: AsyncClient, seed_attempts
) -> None:
    resp = await authed_db_client.get(
        f"/api/attempts?config_id={seed_attempts['cfg1']}"
    )
    assert resp.status_code == 200
    items = resp.json()
    assert items, "expected at least one attempt"
    for item in items:
        assert item["config_name"] == "c1"
        assert item["credential_name"] == "acct"


async def test_names_none_when_config_deleted(
    authed_db_client: AsyncClient, session: Session, seed_attempts
) -> None:
    # Simulate a stale attempt whose config row no longer exists: delete the
    # config directly via SQL (bypassing the ORM's delete-orphan cascade) so an
    # orphaned attempt survives. The LEFT JOIN must still surface it with both
    # names null (PRD §7.4 — "config 삭제된 경우 None 허용").
    cfg1 = seed_attempts["cfg1"]
    conn = session.connection()
    conn.exec_driver_sql("PRAGMA foreign_keys=OFF")
    conn.exec_driver_sql("DELETE FROM instanceconfig WHERE id = ?", (cfg1,))
    session.commit()

    resp = await authed_db_client.get(f"/api/attempts?config_id={cfg1}")
    assert resp.status_code == 200
    items = resp.json()
    assert items, "orphaned attempts should still be returned"
    for item in items:
        assert item["config_id"] == cfg1
        assert item["config_name"] is None
        assert item["credential_name"] is None
