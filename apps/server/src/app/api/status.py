"""Polling status API (PRD §7.3, §7.4).

GET /api/status/polling — the dashboard's "currently polling" view: one row per
*enabled* ``InstanceConfig`` with its credential name, requested shape/spec, and
a summary of its attempt history (last status + time, total count). Derived
purely from the DB so it works regardless of the worker's in-memory state.
Requires auth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import is_admin, require_login
from app.db.models import Attempt, InstanceConfig, OciCredential, User
from app.db.session import get_session
from app.schemas.status import PollingStatusItem

router = APIRouter(prefix="/api/status", tags=["status"])


@router.get("/polling", response_model=list[PollingStatusItem])
def polling_status(
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[PollingStatusItem]:
    stmt = (
        select(InstanceConfig)
        .where(InstanceConfig.enabled == True)  # noqa: E712 — SQL boolean compare
        .order_by(InstanceConfig.id)
    )
    # Ownership scope (PRD §6.3): non-admins only see their own configs.
    if not is_admin(user):
        stmt = stmt.where(InstanceConfig.owner_id == user.id)
    configs = session.exec(stmt).all()

    items: list[PollingStatusItem] = []
    for cfg in configs:
        cred = session.get(OciCredential, cfg.credential_id)

        total = session.exec(
            select(func.count())
            .select_from(Attempt)
            .where(Attempt.config_id == cfg.id)
        ).one()

        last = session.exec(
            select(Attempt)
            .where(Attempt.config_id == cfg.id)
            .order_by(Attempt.id.desc())
            .limit(1)
        ).first()

        items.append(
            PollingStatusItem(
                config_id=cfg.id,
                config_name=cfg.name,
                credential_name=cred.name if cred else None,
                shape=cfg.shape,
                ocpus=cfg.ocpus,
                memory_gb=cfg.memory_gb,
                retry_interval_sec=cfg.retry_interval_sec,
                last_attempt_status=last.status if last else None,
                last_attempt_at=last.attempted_at if last else None,
                total_attempts=int(total),
            )
        )
    return items
