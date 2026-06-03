"""Poller supervisor (PRD §7.3.1, §9.2).

A single long-lived task runs :func:`poller_supervisor`. Every
``SUPERVISOR_INTERVAL_SEC`` (10s) it diffs the set of enabled
``InstanceConfig`` rows against the currently running per-config tasks and:

- **spawns** a :func:`~app.workers.config_task.run_config_task` task for a
  newly enabled config;
- **cancels** the task for a config that was disabled or deleted;
- **restarts** the task when the config's polling-relevant fields changed
  (``updated_at`` advanced) so edits to ``retry_interval_sec`` etc. take effect.

On shutdown all child tasks are cancelled and awaited (graceful, with
``CancelledError`` propagated — PRD §7.3.1 / §9.2).
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime

from sqlalchemy.engine import Engine
from sqlmodel import Session, select

from app.db.models import InstanceConfig
from app.workers.config_task import run_config_task

logger = logging.getLogger("app.workers.poller")

SUPERVISOR_INTERVAL_SEC = 10.0


@dataclass
class _Running:
    task: asyncio.Task
    updated_at: datetime | None


def _enabled_configs(engine: Engine) -> dict[int, datetime | None]:
    """Map of ``config_id -> updated_at`` for every enabled config."""
    with Session(engine) as session:
        rows = session.exec(
            select(InstanceConfig.id, InstanceConfig.updated_at).where(
                InstanceConfig.enabled == True  # noqa: E712 (SQL boolean)
            )
        ).all()
    return {cid: updated for cid, updated in rows}


class PollerSupervisor:
    """Owns the running config tasks and reconciles them with the DB."""

    def __init__(self, engine: Engine) -> None:
        self._engine = engine
        self._running: dict[int, _Running] = {}

    @property
    def running_ids(self) -> set[int]:
        return set(self._running)

    def _spawn(self, config_id: int, updated_at: datetime | None) -> None:
        task = asyncio.create_task(
            run_config_task(self._engine, config_id),
            name=f"config-task-{config_id}",
        )
        self._running[config_id] = _Running(task=task, updated_at=updated_at)
        logger.info("config task spawn", extra={"config_id": config_id})

    async def _cancel(self, config_id: int) -> None:
        running = self._running.pop(config_id, None)
        if running is None:
            return
        running.task.cancel()
        try:
            await running.task
        except asyncio.CancelledError:
            pass
        logger.info("config task cancel", extra={"config_id": config_id})

    async def reconcile(self) -> None:
        """One reconciliation pass: spawn / cancel / restart as needed."""
        desired = _enabled_configs(self._engine)

        # Drop tasks that finished on their own (success / auth_error / stop).
        for cid in list(self._running):
            if self._running[cid].task.done():
                self._running.pop(cid, None)

        # Cancel tasks no longer desired.
        for cid in list(self._running):
            if cid not in desired:
                await self._cancel(cid)

        # Spawn new / restart changed.
        for cid, updated in desired.items():
            current = self._running.get(cid)
            if current is None:
                self._spawn(cid, updated)
            elif current.updated_at != updated:
                logger.info("config 수정 감지 — task 재시작", extra={"config_id": cid})
                await self._cancel(cid)
                self._spawn(cid, updated)

    async def shutdown(self) -> None:
        """Cancel and await every child task (graceful)."""
        tasks = [r.task for r in self._running.values()]
        for t in tasks:
            t.cancel()
        if tasks:
            await asyncio.wait(tasks)
        self._running.clear()
        logger.info("poller supervisor shutdown 완료")


async def poller_supervisor(
    engine: Engine, *, interval: float = SUPERVISOR_INTERVAL_SEC
) -> None:
    """Run the reconcile loop until cancelled, then shut children down."""
    supervisor = PollerSupervisor(engine)
    logger.info("poller supervisor 기동")
    try:
        while True:
            try:
                await supervisor.reconcile()
            except Exception:  # noqa: BLE001 — keep the supervisor alive
                logger.exception("poller reconcile pass failed")
            await asyncio.sleep(interval)
    except asyncio.CancelledError:
        await supervisor.shutdown()
        raise
