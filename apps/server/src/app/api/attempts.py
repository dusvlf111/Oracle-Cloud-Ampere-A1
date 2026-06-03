"""Attempt history query API (PRD §7.4, §8).

GET /api/attempts — filtered (config_id, status, limit), newest first.
The ``Attempt`` SQLModel doubles as the read schema. Requires auth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlmodel import Session, select

from app.api.deps import require_login
from app.db.models import Attempt
from app.db.session import get_session

router = APIRouter(prefix="/api/attempts", tags=["attempts"])

MAX_LIMIT = 500


@router.get("", response_model=list[Attempt])
def list_attempts(
    config_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[Attempt]:
    stmt = select(Attempt)
    if config_id is not None:
        stmt = stmt.where(Attempt.config_id == config_id)
    if status is not None:
        stmt = stmt.where(Attempt.status == status)
    stmt = stmt.order_by(Attempt.id.desc()).limit(limit)
    return list(session.exec(stmt).all())
