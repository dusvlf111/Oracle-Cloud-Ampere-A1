"""Attempt history query API (PRD §7.4, §8).

GET /api/attempts — filtered (config_id, status, limit), newest first.
Each row is enriched with the human-readable ``config_name`` /
``credential_name`` via an outer join (both ``None`` when the config/credential
was deleted after the attempt was recorded). Requires auth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.api.deps import is_admin, require_login
from app.db.models import Attempt, InstanceConfig, OciCredential, User
from app.db.session import get_session
from app.schemas.attempt import AttemptRead

router = APIRouter(prefix="/api/attempts", tags=["attempts"])

MAX_LIMIT = 500


@router.get("", response_model=list[AttemptRead])
def list_attempts(
    config_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[AttemptRead]:
    # LEFT JOIN so attempts whose config (or credential) was deleted still
    # surface, with the name columns coming back NULL → ``None`` (PRD §7.4).
    stmt = (
        select(Attempt, InstanceConfig.name, OciCredential.name)
        .join(InstanceConfig, Attempt.config_id == InstanceConfig.id, isouter=True)
        .join(
            OciCredential,
            InstanceConfig.credential_id == OciCredential.id,
            isouter=True,
        )
    )
    # Ownership scope (PRD §6.3): non-admins only see attempts of configs they
    # own. The inner join via owner filter also drops orphan attempts whose
    # config was deleted — acceptable since a non-admin can't own an orphan.
    if not is_admin(user):
        stmt = stmt.where(InstanceConfig.owner_id == user.id)
    if config_id is not None:
        stmt = stmt.where(Attempt.config_id == config_id)
    if status is not None:
        stmt = stmt.where(Attempt.status == status)
    stmt = stmt.order_by(Attempt.id.desc()).limit(limit)

    rows = session.exec(stmt).all()
    return [
        AttemptRead(
            id=attempt.id,
            config_id=attempt.config_id,
            config_name=config_name,
            credential_name=credential_name,
            attempted_at=attempt.attempted_at,
            status=attempt.status,
            message=attempt.message,
            instance_ocid=attempt.instance_ocid,
            duration_ms=attempt.duration_ms,
        )
        for attempt, config_name, credential_name in rows
    ]
