"""Poller supervisor integration tests (PRD §7.3.1, §9.2; task 6.3).

Drives the real :class:`PollerSupervisor` against an in-memory DB while
stubbing ``run_config_task`` with a controllable long-running coroutine so we
can assert spawn / cancel / restart / graceful-shutdown behaviour without any
OCI traffic.
"""

from __future__ import annotations

import asyncio
from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session

import app.workers.poller as poller_mod
from app.db.models import InstanceConfig, OciCredential
from app.workers.poller import PollerSupervisor, poller_supervisor


@pytest.fixture
def stub_task(monkeypatch):
    """Replace run_config_task with a sleeper that records start/cancel."""
    state = {"started": [], "cancelled": []}

    async def _fake(engine, config_id):
        state["started"].append(config_id)
        try:
            await asyncio.Event().wait()  # block until cancelled
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


async def test_spawns_task_for_enabled_config(engine, stub_task):
    with Session(engine) as s:
        cfg = _config(s, _cred(s))
        cid = cfg.id

    sup = PollerSupervisor(engine)
    await sup.reconcile()
    await asyncio.sleep(0)  # let the spawned task start

    assert sup.running_ids == {cid}
    assert stub_task["started"] == [cid]
    await sup.shutdown()


async def test_toggle_off_cancels_task(engine, stub_task):
    with Session(engine) as s:
        cred = _cred(s)
        cfg = _config(s, cred)
        cid = cfg.id

    sup = PollerSupervisor(engine)
    await sup.reconcile()
    await asyncio.sleep(0)
    assert sup.running_ids == {cid}

    # Disable the config → next reconcile should cancel.
    with Session(engine) as s:
        c = s.get(InstanceConfig, cid)
        c.enabled = False
        s.add(c)
        s.commit()

    await sup.reconcile()
    assert sup.running_ids == set()
    assert cid in stub_task["cancelled"]
    await sup.shutdown()


async def test_config_edit_restarts_task(engine, stub_task):
    with Session(engine) as s:
        cred = _cred(s)
        cfg = _config(s, cred)
        cid = cfg.id

    sup = PollerSupervisor(engine)
    await sup.reconcile()
    await asyncio.sleep(0)
    assert stub_task["started"] == [cid]

    # Bump updated_at to simulate an edit → supervisor restarts the task.
    with Session(engine) as s:
        c = s.get(InstanceConfig, cid)
        c.retry_interval_sec = 5
        c.updated_at = datetime.now(tz=timezone.utc) + timedelta(seconds=1)
        s.add(c)
        s.commit()

    await sup.reconcile()
    await asyncio.sleep(0)

    assert stub_task["started"] == [cid, cid]  # spawned twice
    assert cid in stub_task["cancelled"]  # old one cancelled
    await sup.shutdown()


async def test_multi_account_multi_config_concurrent(engine, stub_task):
    with Session(engine) as s:
        cred_a = _cred(s, name="a")
        cred_b = _cred(s, name="b")
        ids = [
            _config(s, cred_a, name="a1").id,
            _config(s, cred_a, name="a2").id,
            _config(s, cred_b, name="b1").id,
        ]

    sup = PollerSupervisor(engine)
    await sup.reconcile()
    await asyncio.sleep(0)

    assert sup.running_ids == set(ids)
    assert sorted(stub_task["started"]) == sorted(ids)
    await sup.shutdown()


async def test_graceful_shutdown_cancels_all(engine, stub_task):
    with Session(engine) as s:
        cred = _cred(s)
        ids = [_config(s, cred, name=f"c{i}").id for i in range(3)]

    sup = PollerSupervisor(engine)
    await sup.reconcile()
    await asyncio.sleep(0)
    assert sup.running_ids == set(ids)

    await sup.shutdown()
    assert sup.running_ids == set()
    assert sorted(stub_task["cancelled"]) == sorted(ids)


async def test_supervisor_loop_cancellation_propagates(engine, stub_task):
    """The top-level supervisor coroutine shuts children down on cancel."""
    with Session(engine) as s:
        cred = _cred(s)
        _config(s, cred)

    task = asyncio.create_task(poller_supervisor(engine, interval=0.05))
    await asyncio.sleep(0.12)  # allow at least one reconcile pass
    assert stub_task["started"]  # a child was spawned

    task.cancel()
    with pytest.raises(asyncio.CancelledError):
        await task
    # Child config task was cancelled during graceful shutdown.
    assert stub_task["cancelled"]
