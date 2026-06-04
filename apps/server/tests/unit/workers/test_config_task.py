"""config_task polling-loop tests (PRD §7.3.1, §9.2; task 6.1, 6.2).

All OCI calls are mocked — no real launch ever happens. Covers:

- success → Attempt(success) + enabled=False + loop stops
- out_of_capacity → Attempt recorded, no notification, keeps retrying
- auth_error → Attempt + enabled=False + warning notification + stops
- 429 rate_limited → tenacity backoff, Attempt(rate_limited), sleep extended
- success → all linked channels notified in parallel (one failure isolated)
- same credential serialised / different credentials parallel
"""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, MagicMock

import oci.exceptions as oe
import pytest
from sqlmodel import Session, select

import app.workers.config_task as ct
from app.db.models import (
    Attempt,
    ConfigChannelLink,
    InstanceConfig,
    NotificationChannel,
    OciCredential,
)
from app.services.crypto import encrypt_json
from app.workers import concurrency


@pytest.fixture(autouse=True)
def _reset_sems():
    concurrency.reset_semaphores()
    yield
    concurrency.reset_semaphores()


@pytest.fixture
def app_secret(monkeypatch):
    from app.config import Settings

    settings = Settings(app_secret="x" * 32, oci_max_concurrent=10, oci_per_credential_max=1)
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.services.crypto.get_settings", lambda: settings)
    monkeypatch.setattr("app.workers.concurrency.get_settings", lambda: settings)
    return settings


def _service_error(status: int, code: str, message: str) -> oe.ServiceError:
    return oe.ServiceError(status, code, {}, message)


def _make_credential(session: Session, name: str = "acct") -> OciCredential:
    cred = OciCredential(
        name=name,
        tenancy_ocid="ocid1.tenancy.oc1..aaa",
        user_ocid="ocid1.user.oc1..bbb",
        fingerprint="ab:cd:ef",
        region="ap-chuncheon-1",
        private_key_path="/data/keys/x.pem",
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)
    return cred


def _make_config(session: Session, cred: OciCredential, **kw) -> InstanceConfig:
    cfg = InstanceConfig(
        name=kw.pop("name", "cfg"),
        credential_id=cred.id,
        image_ocid="ocid1.image..x",
        subnet_ocid="ocid1.subnet..x",
        availability_domain="AD-1",
        ssh_public_key="ssh-ed25519 AAAA",
        retry_interval_sec=kw.pop("retry_interval_sec", 60),
        **kw,
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    return cfg


# --------------------------------------------------------------------------- #
# 6.1 — success / out_of_capacity / concurrency
# --------------------------------------------------------------------------- #


async def test_success_records_attempt_disables_and_stops(engine, app_secret, monkeypatch):
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred)
        cfg_id = cfg.id

    monkeypatch.setattr(
        ct.oci_client, "launch_instance_sync", lambda *a, **k: "ocid1.instance..ok"
    )
    notify = AsyncMock()
    monkeypatch.setattr(ct, "fan_out", notify)

    status, mult = await ct.poll_once(engine, cfg_id)

    assert status == "success"
    with Session(engine) as s:
        cfg = s.get(InstanceConfig, cfg_id)
        assert cfg.enabled is False
        att = s.exec(select(Attempt)).all()
        assert len(att) == 1
        assert att[0].status == "success"
        assert att[0].instance_ocid == "ocid1.instance..ok"
        assert att[0].duration_ms is not None


async def test_run_loop_stops_after_success(engine, app_secret, monkeypatch):
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred, retry_interval_sec=0)
        cfg_id = cfg.id

    monkeypatch.setattr(
        ct.oci_client, "launch_instance_sync", lambda *a, **k: "ocid1.instance..z"
    )
    monkeypatch.setattr(ct, "fan_out", AsyncMock())

    # Should return promptly (no infinite loop) because success stops it.
    await asyncio.wait_for(ct.run_config_task(engine, cfg_id), timeout=2.0)
    with Session(engine) as s:
        assert s.get(InstanceConfig, cfg_id).enabled is False


async def test_out_of_capacity_records_no_notify_keeps_enabled(engine, app_secret, monkeypatch):
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred)
        cfg_id = cfg.id

    def _raise(*a, **k):
        raise _service_error(500, "InternalError", "Out of host capacity")

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _raise)
    notify = AsyncMock()
    monkeypatch.setattr(ct, "fan_out", notify)

    status, mult = await ct.poll_once(engine, cfg_id)

    assert status == "out_of_capacity"
    assert mult == 1.0
    notify.assert_not_called()
    with Session(engine) as s:
        cfg = s.get(InstanceConfig, cfg_id)
        assert cfg.enabled is True  # keeps retrying
        att = s.exec(select(Attempt)).all()
        assert att[0].status == "out_of_capacity"


async def test_same_credential_serialised(engine, app_secret, monkeypatch):
    """Two configs on the same credential must not run launches concurrently."""
    with Session(engine) as s:
        cred = _make_credential(s)
        c1 = _make_config(s, cred, name="c1")
        c2 = _make_config(s, cred, name="c2")
        id1, id2 = c1.id, c2.id

    active = 0
    max_active = 0

    def _launch(*a, **k):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        # simulate blocking work; release GIL via short spin is not enough,
        # so the semaphore alone must serialise — record concurrency.
        import time

        time.sleep(0.05)
        active -= 1
        return "ocid1.instance..s"

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _launch)
    monkeypatch.setattr(ct, "fan_out", AsyncMock())

    await asyncio.gather(ct.poll_once(engine, id1), ct.poll_once(engine, id2))

    assert max_active == 1  # per-credential semaphore serialised them


async def test_different_credentials_parallel(engine, app_secret, monkeypatch):
    """Configs on different credentials run their launches in parallel."""
    with Session(engine) as s:
        cred_a = _make_credential(s, name="a")
        cred_b = _make_credential(s, name="b")
        ca = _make_config(s, cred_a, name="ca")
        cb = _make_config(s, cred_b, name="cb")
        id_a, id_b = ca.id, cb.id

    active = 0
    max_active = 0

    def _launch(*a, **k):
        nonlocal active, max_active
        active += 1
        max_active = max(max_active, active)
        import time

        time.sleep(0.05)
        active -= 1
        return "ocid1.instance..p"

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _launch)
    monkeypatch.setattr(ct, "fan_out", AsyncMock())

    await asyncio.gather(ct.poll_once(engine, id_a), ct.poll_once(engine, id_b))

    assert max_active == 2  # different credentials ran concurrently


# --------------------------------------------------------------------------- #
# 6.2 — errors + notifications
# --------------------------------------------------------------------------- #


async def test_auth_error_disables_and_notifies(engine, app_secret, monkeypatch):
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred)
        ch = NotificationChannel(
            name="ntfy", type="ntfy", config_enc=encrypt_json({"server_url": "https://n", "topic": "t"})
        )
        s.add(ch)
        s.commit()
        s.refresh(ch)
        s.add(ConfigChannelLink(config_id=cfg.id, channel_id=ch.id))
        s.commit()
        cfg_id = cfg.id

    def _raise(*a, **k):
        raise _service_error(401, "NotAuthenticated", "bad key")

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _raise)
    notify = AsyncMock()
    monkeypatch.setattr(ct, "fan_out", notify)

    status, mult = await ct.poll_once(engine, cfg_id)

    assert status == "auth_error"
    notify.assert_awaited_once()
    payload = notify.await_args.args[1]
    assert payload.title == "⚠️ OCI 인증 오류"
    assert payload.tags == ["warning"]
    with Session(engine) as s:
        cfg = s.get(InstanceConfig, cfg_id)
        assert cfg.enabled is False
        att = s.exec(select(Attempt)).all()
        assert att[0].status == "auth_error"


async def test_config_error_disables_notifies_and_stops(engine, app_secret, monkeypatch):
    """Permanent malformed-request error → record + disable + notify + stop.

    Regression for the prod bug where a bad image/subnet OCID made the worker
    retry an impossible CannotParseRequest forever (hardening §2).
    """
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred)
        ch = NotificationChannel(
            name="ntfy",
            type="ntfy",
            config_enc=encrypt_json({"server_url": "https://n", "topic": "t"}),
        )
        s.add(ch)
        s.commit()
        s.refresh(ch)
        s.add(ConfigChannelLink(config_id=cfg.id, channel_id=ch.id))
        s.commit()
        cfg_id = cfg.id

    def _raise(*a, **k):
        raise _service_error(400, "CannotParseRequest", "Invalid image OCID")

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _raise)
    notify = AsyncMock()
    monkeypatch.setattr(ct, "fan_out", notify)

    status, mult = await ct.poll_once(engine, cfg_id)

    assert status == "config_error"
    assert mult == 1.0
    notify.assert_awaited_once()
    payload = notify.await_args.args[1]
    assert payload.title.startswith("⚠️ 설정 오류로 자동 중지")
    assert payload.tags == ["warning"]
    with Session(engine) as s:
        cfg = s.get(InstanceConfig, cfg_id)
        assert cfg.enabled is False  # auto-disabled, no infinite retry
        att = s.exec(select(Attempt)).all()
        assert att[0].status == "config_error"


async def test_run_loop_stops_after_config_error(engine, app_secret, monkeypatch):
    """The polling loop terminates on config_error (no infinite retry)."""
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred, retry_interval_sec=0)
        cfg_id = cfg.id

    def _raise(*a, **k):
        raise _service_error(404, "NotAuthorizedOrNotFound", "subnet not found")

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _raise)
    monkeypatch.setattr(ct, "fan_out", AsyncMock())

    await asyncio.wait_for(ct.run_config_task(engine, cfg_id), timeout=2.0)
    with Session(engine) as s:
        assert s.get(InstanceConfig, cfg_id).enabled is False


async def test_rate_limited_backoff_and_extends_sleep(engine, app_secret, monkeypatch):
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred)
        cfg_id = cfg.id

    calls = 0

    def _raise(*a, **k):
        nonlocal calls
        calls += 1
        raise _service_error(429, "TooManyRequests", "slow down")

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _raise)
    monkeypatch.setattr(ct, "fan_out", AsyncMock())

    status, mult = await ct.poll_once(engine, cfg_id)

    assert status == "rate_limited"
    assert mult == ct.RATE_LIMIT_BACKOFF_FACTOR
    assert calls == 3  # initial + 2 tenacity retries
    with Session(engine) as s:
        att = s.exec(select(Attempt)).all()
        assert att[0].status == "rate_limited"
        cfg = s.get(InstanceConfig, cfg_id)
        assert cfg.enabled is True


async def test_success_notifies_all_channels_one_failure_isolated(engine, app_secret, monkeypatch):
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred)
        ch1 = NotificationChannel(
            name="discord", type="discord", config_enc=encrypt_json({"webhook_url": "https://x"})
        )
        ch2 = NotificationChannel(
            name="ntfy",
            type="ntfy",
            config_enc=encrypt_json({"server_url": "https://n", "topic": "t"}),
        )
        s.add(ch1)
        s.add(ch2)
        s.commit()
        s.refresh(ch1)
        s.refresh(ch2)
        s.add(ConfigChannelLink(config_id=cfg.id, channel_id=ch1.id))
        s.add(ConfigChannelLink(config_id=cfg.id, channel_id=ch2.id))
        s.commit()
        cfg_id = cfg.id

    monkeypatch.setattr(
        ct.oci_client, "launch_instance_sync", lambda *a, **k: "ocid1.instance..ok"
    )

    # Use the real fan_out, mock the per-channel send: one ok, one failing.
    sent: list[str] = []

    async def _send(channel, payload):
        sent.append(channel.type)
        if channel.type == "discord":
            raise RuntimeError("discord down")

    import app.services.notifier as notifier

    monkeypatch.setattr(notifier, "send", _send)

    status, _ = await ct.poll_once(engine, cfg_id)

    assert status == "success"
    # both channels attempted despite discord failing
    assert sorted(sent) == ["discord", "ntfy"]
    with Session(engine) as s:
        cfg = s.get(InstanceConfig, cfg_id)
        assert cfg.enabled is False


async def test_max_attempts_reached_disables_notifies_and_stops(
    engine, app_secret, monkeypatch
):
    """max_attempts cap: once the config has that many attempts, the worker
    disables it and notifies instead of launching again (PRD §7.2)."""
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred, max_attempts=2)
        ch = NotificationChannel(
            name="ntfy-cap",
            type="ntfy",
            config_enc=encrypt_json({"server_url": "https://n", "topic": "t"}),
        )
        s.add(ch)
        s.commit()
        s.refresh(ch)
        s.add(ConfigChannelLink(config_id=cfg.id, channel_id=ch.id))
        # Two attempts already on record → the cap is reached.
        s.add(Attempt(config_id=cfg.id, status="out_of_capacity"))
        s.add(Attempt(config_id=cfg.id, status="out_of_capacity"))
        s.commit()
        cfg_id = cfg.id

    launch = MagicMock()
    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", launch)
    notify = AsyncMock()
    monkeypatch.setattr(ct, "fan_out", notify)

    status, mult = await ct.poll_once(engine, cfg_id)

    assert status == "max_attempts"
    assert mult == 1.0
    launch.assert_not_called()  # no further OCI call past the cap
    notify.assert_awaited_once()
    payload = notify.await_args.args[1]
    assert "최대 시도 횟수" in payload.title
    with Session(engine) as s:
        assert s.get(InstanceConfig, cfg_id).enabled is False


async def test_max_attempts_none_is_unlimited(engine, app_secret, monkeypatch):
    """max_attempts=None (default) never trips the cap, however many attempts."""
    with Session(engine) as s:
        cred = _make_credential(s)
        cfg = _make_config(s, cred)  # max_attempts defaults to None
        for _ in range(5):
            s.add(Attempt(config_id=cfg.id, status="out_of_capacity"))
        s.commit()
        cfg_id = cfg.id

    def _raise(*a, **k):
        raise _service_error(500, "InternalError", "Out of host capacity")

    monkeypatch.setattr(ct.oci_client, "launch_instance_sync", _raise)
    monkeypatch.setattr(ct, "fan_out", AsyncMock())

    status, _ = await ct.poll_once(engine, cfg_id)

    assert status == "out_of_capacity"  # still polling, cap never applies
    with Session(engine) as s:
        assert s.get(InstanceConfig, cfg_id).enabled is True
