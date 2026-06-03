"""LogEntry model + indexed-column query tests (PRD §6).

Migration up/down is exercised against a temp sqlite DB driven through the
Alembic API (no external `alembic` CLI / docker needed — `uv run` only).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from pathlib import Path

import pytest
from sqlalchemy import inspect
from sqlmodel import Session, select

from app.db.models import LogEntry


def test_create_and_read_log_entry(session: Session) -> None:
    entry = LogEntry(
        timestamp=datetime(2026, 6, 3, 10, 30, 11),
        level="ERROR",
        logger="app.workers.config_task",
        message="OCI 인증 오류",
        config_id=5,
        attempt_id=142,
        credential_id=1,
        extra='{"region": "ap-seoul-1"}',
        exc_info="Traceback (most recent call last): ...",
    )
    session.add(entry)
    session.commit()
    session.refresh(entry)

    assert entry.id is not None
    fetched = session.get(LogEntry, entry.id)
    assert fetched is not None
    assert fetched.level == "ERROR"
    assert fetched.config_id == 5
    assert fetched.exc_info.startswith("Traceback")


def test_context_columns_default_to_none(session: Session) -> None:
    entry = LogEntry(level="INFO", logger="app.api.auth", message="login ok")
    session.add(entry)
    session.commit()
    session.refresh(entry)

    assert entry.config_id is None
    assert entry.attempt_id is None
    assert entry.credential_id is None
    assert entry.extra is None
    assert entry.exc_info is None


def test_query_by_indexed_columns(session: Session) -> None:
    base = datetime(2026, 6, 3, 12, 0, 0)
    for i in range(5):
        session.add(
            LogEntry(
                timestamp=base + timedelta(minutes=i),
                level="ERROR" if i % 2 else "INFO",
                logger="app.workers.poller" if i < 3 else "app.api.auth",
                message=f"msg {i}",
                config_id=1 if i < 2 else 2,
            )
        )
    session.commit()

    errors = session.exec(select(LogEntry).where(LogEntry.level == "ERROR")).all()
    assert {e.message for e in errors} == {"msg 1", "msg 3"}

    poller = session.exec(
        select(LogEntry).where(LogEntry.logger == "app.workers.poller")
    ).all()
    assert len(poller) == 3

    cfg1 = session.exec(select(LogEntry).where(LogEntry.config_id == 1)).all()
    assert len(cfg1) == 2


def test_indexes_present_on_table(engine) -> None:
    insp = inspect(engine)
    indexed_cols = {
        col
        for idx in insp.get_indexes("logentry")
        for col in idx["column_names"]
    }
    assert {"timestamp", "level", "logger", "config_id"} <= indexed_cols


def test_alembic_upgrade_and_downgrade(tmp_path: Path) -> None:
    """Run the full migration chain up to head then back down to base."""
    from alembic import command
    from alembic.config import Config
    from sqlalchemy import create_engine, inspect as sa_inspect

    server_root = Path(__file__).resolve().parents[3]
    db_path = tmp_path / "mig.db"
    url = f"sqlite:///{db_path}"

    cfg = Config(str(server_root / "alembic.ini"))
    cfg.set_main_option("script_location", str(server_root / "alembic"))
    cfg.set_main_option("sqlalchemy.url", url)

    command.upgrade(cfg, "head")
    insp = sa_inspect(create_engine(url))
    assert "logentry" in insp.get_table_names()
    cols = {c["name"] for c in insp.get_columns("logentry")}
    assert {"id", "timestamp", "level", "logger", "message", "config_id"} <= cols

    command.downgrade(cfg, "base")
    insp2 = sa_inspect(create_engine(url))
    assert "logentry" not in insp2.get_table_names()
