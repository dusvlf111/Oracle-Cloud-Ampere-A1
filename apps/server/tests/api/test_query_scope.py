"""Read-side ownership scoping (PRD §6.3, task 9.6).

Covers attempts / polling status / logs / SSE filter / meta credential lookup:
two regular users A/B can't see each other's data; admin sees everything.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.api.logs import _record_matches
from app.db.models import Attempt, InstanceConfig, LogEntry, OciCredential

_FINGERPRINT = "ab:cd:ef:12:34:56:78:90:ab:cd:ef:12:34:56:78:90"


@pytest.fixture
def cred_settings(tmp_path, monkeypatch: pytest.MonkeyPatch):
    from app.config import Settings
    from app.services import crypto

    settings = Settings(app_secret="qscope-secret", keys_dir=str(tmp_path / "keys"))
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.credentials.get_settings", lambda: settings)
    monkeypatch.setattr(crypto, "get_settings", lambda: settings)
    crypto._key_for.cache_clear()
    return settings


def _seed_owned(session: Session, owner_id: int, name: str) -> int:
    """Create a credential + config + one attempt + one log for an owner.

    Returns the config id.
    """
    cred = OciCredential(
        name=f"cred-{name}",
        tenancy_ocid="ocid1.tenancy..a",
        user_ocid="ocid1.user..a",
        fingerprint="fp",
        region="ap-chuncheon-1",
        private_key_path="/k.pem",
        owner_id=owner_id,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)
    cfg = InstanceConfig(
        name=f"cfg-{name}",
        credential_id=cred.id,
        owner_id=owner_id,
        enabled=True,
        image_ocid="i",
        subnet_ocid="s",
        availability_domain="ad",
        ssh_public_key="k",
    )
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    session.add(Attempt(config_id=cfg.id, status="out_of_capacity"))
    session.add(
        LogEntry(level="INFO", logger="app.workers", message=f"poll {name}", config_id=cfg.id)
    )
    session.commit()
    return cfg.id


@pytest.fixture
def scoped(engine, make_user):
    a = make_user("a-user")
    b = make_user("b-user")
    with Session(engine) as s:
        a_cfg = _seed_owned(s, a, "a")
        b_cfg = _seed_owned(s, b, "b")
    return {"a": a, "b": b, "a_cfg": a_cfg, "b_cfg": b_cfg}


async def test_attempts_scoped_to_owner(
    admin_settings, scoped, login_as
) -> None:
    a_client = await login_as("a-user")
    rows = (await a_client.get("/api/attempts")).json()
    cfg_ids = {r["config_id"] for r in rows}
    assert scoped["a_cfg"] in cfg_ids
    assert scoped["b_cfg"] not in cfg_ids


async def test_polling_status_scoped_to_owner(
    admin_settings, scoped, login_as
) -> None:
    b_client = await login_as("b-user")
    rows = (await b_client.get("/api/status/polling")).json()
    names = {r["config_name"] for r in rows}
    assert "cfg-b" in names
    assert "cfg-a" not in names


async def test_logs_scoped_to_owner(admin_settings, scoped, login_as) -> None:
    a_client = await login_as("a-user")
    page = (await a_client.get("/api/logs")).json()
    messages = {item["message"] for item in page["items"]}
    assert "poll a" in messages
    assert "poll b" not in messages


async def test_admin_sees_all_attempts_and_logs(
    admin_settings, scoped, login_as
) -> None:
    from tests.conftest import TEST_PASSWORD, TEST_USERNAME

    admin_client = await login_as(TEST_USERNAME, TEST_PASSWORD)
    attempts = (await admin_client.get("/api/attempts")).json()
    cfg_ids = {r["config_id"] for r in attempts}
    assert {scoped["a_cfg"], scoped["b_cfg"]} <= cfg_ids

    logs = (await admin_client.get("/api/logs")).json()
    messages = {i["message"] for i in logs["items"]}
    assert {"poll a", "poll b"} <= messages


async def test_meta_credential_scoped_404(
    admin_settings, scoped, login_as, engine, cred_settings
) -> None:
    from sqlmodel import select

    # B's credential id.
    with Session(engine) as s:
        b_cred = s.exec(
            select(OciCredential).where(OciCredential.name == "cred-b")
        ).one()
    a_client = await login_as("a-user")
    resp = await a_client.get(
        f"/api/meta/availability-domains?credential_id={b_cred.id}"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


# --- SSE filter unit (ownership scope in _record_matches) ------------------ #


def test_record_matches_allows_owned_config() -> None:
    rec = {"level": "INFO", "logger": "app.workers", "config_id": 7}
    assert _record_matches(
        rec, levels=None, logger=None, config_id=None, allowed_config_ids={7}
    )


def test_record_matches_blocks_unowned_config() -> None:
    rec = {"level": "INFO", "logger": "app.workers", "config_id": 9}
    assert not _record_matches(
        rec, levels=None, logger=None, config_id=None, allowed_config_ids={7}
    )


def test_record_matches_blocks_systemwide_record_for_user() -> None:
    """A non-admin (restricted) never sees config-less system records."""
    rec = {"level": "ERROR", "logger": "app.main", "config_id": None}
    assert not _record_matches(
        rec, levels=None, logger=None, config_id=None, allowed_config_ids={7}
    )


def test_record_matches_admin_sees_everything() -> None:
    """admin → allowed_config_ids None means no ownership restriction."""
    rec = {"level": "INFO", "logger": "app.main", "config_id": None}
    assert _record_matches(
        rec, levels=None, logger=None, config_id=None, allowed_config_ids=None
    )


async def test_sse_stream_filters_unowned(admin_settings, scoped) -> None:
    """The SSE generator drops log records of configs the user doesn't own."""
    import asyncio

    from app.api.logs import sse_event_stream
    from app.log_bus import log_bus

    a_cfg, b_cfg = scoped["a_cfg"], scoped["b_cfg"]

    gen = sse_event_stream(
        is_disconnected=lambda: _never(),
        levels=None,
        logger=None,
        config_id=None,
        allowed_config_ids={a_cfg},
        heartbeat=0.05,
    )
    # Prime the subscription (the generator subscribes on first __anext__);
    # give it a moment, then publish one unowned + one owned record.
    agen = gen.__aiter__()
    pull = asyncio.ensure_future(agen.__anext__())
    await asyncio.sleep(0.01)
    log_bus.publish({"level": "INFO", "logger": "x", "config_id": b_cfg})  # dropped
    log_bus.publish({"level": "INFO", "logger": "x", "config_id": a_cfg})  # kept

    ev = await asyncio.wait_for(pull, timeout=1.0)
    # The unowned record was filtered, so the first ``log`` event is the owned one.
    assert ev["event"] == "log"
    assert f'"config_id": {a_cfg}' in ev["data"]
    assert f'"config_id": {b_cfg}' not in ev["data"]
    await agen.aclose()


async def _never() -> bool:
    return False
