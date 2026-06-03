"""Restart auto-resume guarantee (PRD §7.3.1, §9.2; task 8.2).

When the process restarts (container `restart: unless-stopped` or a crash) the
poller supervisor is re-created from scratch in the FastAPI lifespan. State is
NOT carried in memory — the *source of truth* is the DB `enabled` flag. So:

- every config still ``enabled=True`` is re-spawned on the fresh supervisor;
- a config that finished (success/auth_error flips ``enabled=False``) is NOT
  re-spawned — it stays stopped;
- transient runtime state (rate_limited backoff multiplier) lives only in the
  per-task loop, so a restart resets it to an immediate retry.

The test simulates a restart by shutting the first supervisor down and standing
a second one up against the *same* DB, asserting the spawn set is derived purely
from the persisted ``enabled`` flag.
"""

from __future__ import annotations

import asyncio

import pytest
from sqlmodel import Session

import app.workers.poller as poller_mod
from app.db.models import InstanceConfig, OciCredential
from app.db.session import (
    MigrationsNotAppliedError,
    assert_schema_ready,
    create_db_engine,
)
from app.workers.poller import PollerSupervisor


@pytest.fixture
def stub_task(monkeypatch):
    """run_config_task → a controllable sleeper recording spawns/cancels."""
    state = {"started": [], "cancelled": []}

    async def _fake(engine, config_id):
        state["started"].append(config_id)
        try:
            await asyncio.Event().wait()
        except asyncio.CancelledError:
            state["cancelled"].append(config_id)
            raise

    monkeypatch.setattr(poller_mod, "run_config_task", _fake)
    return state


def _cred(session: Session, name="acct") -> OciCredential:
    c = OciCredential(
        name=name,
        tenancy_ocid="ocid1.tenancy..a",
        user_ocid="ocid1.user..b",
        fingerprint="ab:cd",
        region="ap-chuncheon-1",
        private_key_path="/data/keys/x.pem",
    )
    session.add(c)
    session.commit()
    session.refresh(c)
    return c


def _config(session: Session, cred, *, enabled=True, name="cfg") -> InstanceConfig:
    cfg = InstanceConfig(
        name=name,
        credential_id=cred.id,
        enabled=enabled,
        image_ocid="ocid1.image..x",
        subnet_ocid="ocid1.subnet..x",
        availability_domain="AD-1",
        ssh_public_key="ssh-ed25519 AAAA",
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


async def test_restart_respawns_only_enabled_configs(engine, stub_task):
    # 2 enabled + 1 disabled (e.g. previously succeeded → enabled=False).
    with Session(engine) as s:
        cred = _cred(s)
        e1 = _config(s, cred, enabled=True, name="e1").id
        e2 = _config(s, cred, enabled=True, name="e2").id
        _config(s, cred, enabled=False, name="done").id

    # --- first lifecycle: supervisor spawns the two enabled configs ---
    sup1 = PollerSupervisor(engine)
    await sup1.reconcile()
    await asyncio.sleep(0)
    assert sup1.running_ids == {e1, e2}

    # --- simulate restart: graceful shutdown of the old supervisor ---
    await sup1.shutdown()
    assert sup1.running_ids == set()
    assert sorted(stub_task["cancelled"]) == sorted([e1, e2])

    # --- second lifecycle: brand-new supervisor against the SAME DB ---
    stub_task["started"].clear()
    sup2 = PollerSupervisor(engine)
    await sup2.reconcile()
    await asyncio.sleep(0)

    # Enabled configs resume; the disabled one is never spawned.
    assert sup2.running_ids == {e1, e2}
    assert sorted(stub_task["started"]) == sorted([e1, e2])
    await sup2.shutdown()


async def test_completed_config_not_resumed_after_restart(engine, stub_task):
    # A config that succeeded sets enabled=False; after restart it must stay off.
    with Session(engine) as s:
        cred = _cred(s)
        live = _config(s, cred, enabled=True, name="live").id
        succeeded = _config(s, cred, enabled=True, name="succeeded").id

    sup1 = PollerSupervisor(engine)
    await sup1.reconcile()
    await asyncio.sleep(0)
    assert sup1.running_ids == {live, succeeded}

    # Simulate the "success → disable" outcome on one config, then restart.
    with Session(engine) as s:
        c = s.get(InstanceConfig, succeeded)
        c.enabled = False
        s.add(c)
        s.commit()
    await sup1.shutdown()

    stub_task["started"].clear()
    sup2 = PollerSupervisor(engine)
    await sup2.reconcile()
    await asyncio.sleep(0)

    assert sup2.running_ids == {live}
    assert stub_task["started"] == [live]
    await sup2.shutdown()


async def test_no_enabled_configs_means_no_spawns_after_restart(engine, stub_task):
    with Session(engine) as s:
        cred = _cred(s)
        _config(s, cred, enabled=False, name="off")

    sup = PollerSupervisor(engine)
    await sup.reconcile()
    await asyncio.sleep(0)
    assert sup.running_ids == set()
    assert stub_task["started"] == []
    await sup.shutdown()


def test_schema_guard_passes_on_migrated_engine(engine):
    # The `engine` fixture has the schema created → guard must not raise.
    assert_schema_ready(engine)


def test_schema_guard_fails_fast_on_unmigrated_db():
    # A fresh engine with no tables → guard fails with an actionable error.
    raw = create_db_engine("sqlite://")
    with pytest.raises(MigrationsNotAppliedError, match="alembic upgrade head"):
        assert_schema_ready(raw)
    raw.dispose()
