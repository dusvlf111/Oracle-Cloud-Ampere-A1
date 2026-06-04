"""Admin user-management API (PRD §6.2, task 9.4).

Covers approve/reject/disable/enable lifecycle, last-admin protection, owned
config auto-disable on user disable, and non-admin access denial.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import Session, select

from app.db.models import InstanceConfig, OciCredential, User
from app.services import auth as auth_service
from tests.conftest import TEST_PASSWORD, TEST_USERNAME


def _seed_pending(engine, username: str = "pending1") -> int:
    with Session(engine) as s:
        u = auth_service.register_user(s, username, "pending-pw-123")
        return u.id


async def test_list_users_admin_only(
    authed_db_client: AsyncClient, engine
) -> None:
    _seed_pending(engine, "p1")
    resp = await authed_db_client.get("/api/users")
    assert resp.status_code == 200
    rows = resp.json()
    names = {r["username"] for r in rows}
    assert TEST_USERNAME in names and "p1" in names
    admin_row = next(r for r in rows if r["username"] == TEST_USERNAME)
    assert admin_row["role"] == "admin"
    assert admin_row["status"] == "active"


async def test_list_users_requires_auth_401(client: AsyncClient, db_app) -> None:
    resp = await client.get("/api/users")
    assert resp.status_code == 401


async def test_non_admin_forbidden_403(
    authed_db_client: AsyncClient, engine, make_user, login_as
) -> None:
    make_user("normaluser")
    user_client = await login_as("normaluser")
    resp = await user_client.get("/api/users")
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "forbidden"


async def test_approve_then_login_succeeds(
    authed_db_client: AsyncClient, engine, login_as
) -> None:
    uid = _seed_pending(engine, "tobeapproved")
    # Before approval, login is blocked.
    transport_check = await authed_db_client.post(
        "/api/auth/login",
        json={"username": "tobeapproved", "password": "pending-pw-123"},
    )
    assert transport_check.status_code == 403
    assert transport_check.json()["error"]["code"] == "account_pending"

    resp = await authed_db_client.post(f"/api/users/{uid}/approve")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    assert resp.json()["approved_at"] is not None

    # Now they can log in.
    user_client = await login_as("tobeapproved", "pending-pw-123")
    me = await user_client.get("/api/auth/me")
    assert me.status_code == 200


async def test_approve_non_pending_409(
    authed_db_client: AsyncClient, engine
) -> None:
    # The bootstrap admin is already active.
    with Session(engine) as s:
        admin = s.exec(
            select(User).where(User.username == TEST_USERNAME)
        ).one()
    resp = await authed_db_client.post(f"/api/users/{admin.id}/approve")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_state"


async def test_reject_deletes_pending_user(
    authed_db_client: AsyncClient, engine
) -> None:
    uid = _seed_pending(engine, "torej")
    resp = await authed_db_client.post(f"/api/users/{uid}/reject")
    assert resp.status_code == 204
    with Session(engine) as s:
        assert s.get(User, uid) is None


async def test_reject_non_pending_409(
    authed_db_client: AsyncClient, engine, make_user
) -> None:
    uid = make_user("activeuser")  # active, not pending
    resp = await authed_db_client.post(f"/api/users/{uid}/reject")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "invalid_state"


async def test_disable_blocks_login_and_disables_configs(
    authed_db_client: AsyncClient, engine, make_user, login_as
) -> None:
    uid = make_user("owneruser")
    # Seed an owned, enabled config.
    with Session(engine) as s:
        cred = OciCredential(
            name="c1",
            tenancy_ocid="ocid1.tenancy..a",
            user_ocid="ocid1.user..a",
            fingerprint="fp",
            region="ap-chuncheon-1",
            private_key_enc="enc",
            owner_id=uid,
        )
        s.add(cred)
        s.commit()
        s.refresh(cred)
        cfg = InstanceConfig(
            name="cfg1",
            credential_id=cred.id,
            owner_id=uid,
            enabled=True,
            image_ocid="ocid1.image..a",
            subnet_ocid="ocid1.subnet..a",
            availability_domain="AD-1",
            ssh_public_key="ssh-ed25519 AAAA",
        )
        s.add(cfg)
        s.commit()
        cfg_id = cfg.id

    resp = await authed_db_client.post(f"/api/users/{uid}/disable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"

    # Owned config is now disabled (supervisor will cancel on next reconcile).
    with Session(engine) as s:
        assert s.get(InstanceConfig, cfg_id).enabled is False

    # Login is now blocked with account_disabled.
    login = await authed_db_client.post(
        "/api/auth/login",
        json={"username": "owneruser", "password": "user-pass-123"},
    )
    assert login.status_code == 403
    assert login.json()["error"]["code"] == "account_disabled"


async def test_enable_restores_login(
    authed_db_client: AsyncClient, engine, make_user, login_as
) -> None:
    uid = make_user("reenable", status="disabled")
    resp = await authed_db_client.post(f"/api/users/{uid}/enable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "active"
    user_client = await login_as("reenable")
    me = await user_client.get("/api/auth/me")
    assert me.status_code == 200


async def test_last_admin_cannot_be_disabled_409(
    authed_db_client: AsyncClient, engine
) -> None:
    with Session(engine) as s:
        admin = s.exec(
            select(User).where(User.username == TEST_USERNAME)
        ).one()
    resp = await authed_db_client.post(f"/api/users/{admin.id}/disable")
    assert resp.status_code == 409
    assert resp.json()["error"]["code"] == "last_admin"


async def test_second_admin_can_be_disabled(
    authed_db_client: AsyncClient, engine, make_user
) -> None:
    # With two admins, one can be disabled.
    other = make_user("admin2", role="admin", status="active")
    resp = await authed_db_client.post(f"/api/users/{other}/disable")
    assert resp.status_code == 200
    assert resp.json()["status"] == "disabled"


async def test_actions_on_missing_user_404(
    authed_db_client: AsyncClient, engine
) -> None:
    for action in ("approve", "reject", "disable", "enable"):
        resp = await authed_db_client.post(f"/api/users/99999/{action}")
        assert resp.status_code == 404, action
        assert resp.json()["error"]["code"] == "user_not_found"
