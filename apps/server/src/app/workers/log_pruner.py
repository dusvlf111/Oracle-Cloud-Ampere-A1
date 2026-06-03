"""Log retention worker (PRD §9.3.8).

Keeps at most the last ``LOG_RETENTION_DAYS`` days **and** ``LOG_RETENTION_ROWS``
rows of ``LogEntry`` (whichever bound is hit first). Runs every 5 minutes.

Retention values come from ``AppSetting`` (UI-tunable) and fall back to the
environment-derived defaults in :class:`app.config.Settings`.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone

from sqlalchemy import delete as sa_delete, func
from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.config import get_settings
from app.db.models import AppSetting, LogEntry

logger = logging.getLogger("app.workers.log_pruner")

PRUNE_INTERVAL_SEC = 300.0  # 5 minutes

_SETTING_DAYS = "log_retention_days"
_SETTING_ROWS = "log_retention_rows"


def _setting_int(session: Session, key: str, default: int) -> int:
    row = session.get(AppSetting, key)
    if row is None:
        return default
    try:
        return int(row.value)
    except (TypeError, ValueError):
        return default


def prune_once(engine: Engine, *, now: datetime | None = None) -> int:
    """Delete expired / overflow rows. Returns the number of rows removed."""
    settings = get_settings()
    now = now or datetime.now(tz=timezone.utc)
    deleted = 0
    with Session(engine) as session:
        days = _setting_int(session, _SETTING_DAYS, settings.log_retention_days)
        max_rows = _setting_int(session, _SETTING_ROWS, settings.log_retention_rows)

        # 1) Age-based cutoff.
        cutoff = now - timedelta(days=days)
        res = session.exec(sa_delete(LogEntry).where(LogEntry.timestamp < cutoff))
        deleted += res.rowcount or 0

        # 2) Row-count cap — keep only the newest `max_rows`.
        total = session.exec(select(func.count()).select_from(LogEntry)).one()
        if total > max_rows:
            # id of the newest row to *drop* (everything with id <= threshold goes)
            keep_ids = session.exec(
                select(LogEntry.id).order_by(LogEntry.id.desc()).limit(max_rows)
            ).all()
            if keep_ids:
                oldest_kept = keep_ids[-1]
                res2 = session.exec(
                    sa_delete(LogEntry).where(LogEntry.id < oldest_kept)
                )
                deleted += res2.rowcount or 0

        session.commit()

    if deleted:
        logger.info("log_pruner removed %d expired log rows", deleted)
    return deleted


async def run_log_pruner(
    engine: Engine, *, interval: float = PRUNE_INTERVAL_SEC
) -> None:
    """Background loop: prune, then sleep, until cancelled."""
    while True:
        try:
            await asyncio.to_thread(prune_once, engine)
        except Exception:  # noqa: BLE001 — keep the loop alive on failure
            logger.exception("log_pruner pass failed")
        await asyncio.sleep(interval)
