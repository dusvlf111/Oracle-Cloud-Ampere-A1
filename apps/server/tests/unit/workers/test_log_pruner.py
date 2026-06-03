"""log_pruner retention tests (PRD §9.3.8)."""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlmodel import Session, func, select

from app.db.models import AppSetting, LogEntry
from app.workers.log_pruner import prune_once

NOW = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


def _add(session: Session, n: int, *, age_days: float = 0.0) -> None:
    ts = NOW - timedelta(days=age_days)
    for i in range(n):
        session.add(LogEntry(timestamp=ts, level="INFO", logger="app.x", message=f"m{i}"))
    session.commit()


def test_prunes_by_age(engine, session: Session, monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr(
        "app.workers.log_pruner.get_settings",
        lambda: Settings(log_retention_days=7, log_retention_rows=100000),
    )
    _add(session, 3, age_days=10)  # expired
    _add(session, 2, age_days=1)   # fresh

    removed = prune_once(engine, now=NOW)
    assert removed == 3
    remaining = session.exec(select(func.count()).select_from(LogEntry)).one()
    assert remaining == 2


def test_prunes_by_row_cap(engine, session: Session, monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr(
        "app.workers.log_pruner.get_settings",
        lambda: Settings(log_retention_days=3650, log_retention_rows=5),
    )
    _add(session, 12, age_days=0)

    removed = prune_once(engine, now=NOW)
    assert removed == 7
    remaining = session.exec(select(LogEntry).order_by(LogEntry.id.desc())).all()
    assert len(remaining) == 5
    # Newest rows are the ones kept.
    assert remaining[0].message == "m11"


def test_appsetting_overrides_defaults(engine, session: Session, monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr(
        "app.workers.log_pruner.get_settings",
        lambda: Settings(log_retention_days=7, log_retention_rows=100000),
    )
    session.add(AppSetting(key="log_retention_days", value="1"))
    session.commit()
    _add(session, 4, age_days=2)  # older than the AppSetting 1-day cutoff

    removed = prune_once(engine, now=NOW)
    assert removed == 4
    assert session.exec(select(func.count()).select_from(LogEntry)).one() == 0


def test_noop_when_within_limits(engine, session: Session, monkeypatch) -> None:
    from app.config import Settings

    monkeypatch.setattr(
        "app.workers.log_pruner.get_settings",
        lambda: Settings(log_retention_days=30, log_retention_rows=100),
    )
    _add(session, 3, age_days=1)
    assert prune_once(engine, now=NOW) == 0
