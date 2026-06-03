"""Log query / delete API (PRD §8).

GET    /api/logs        — filtered, cursor-paginated query → ``LogPage``
DELETE /api/logs?before — bulk delete of records older than an ISO timestamp

The SSE stream (``GET /api/logs/stream``) is added in Task 3.5. Every route
requires an authenticated session (``require_login``).
"""

from __future__ import annotations

import base64
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Response
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select

from app.api.deps import AppError, require_login
from app.db.models import LogEntry
from app.db.session import get_session

router = APIRouter(prefix="/api/logs", tags=["logs"])

MAX_LIMIT = 200


class LogPage(BaseModel):
    items: list[LogEntry]
    next_cursor: str | None
    has_more: bool


def _encode_cursor(last_id: int) -> str:
    return base64.b64encode(str(last_id).encode()).decode()


def _decode_cursor(cursor: str) -> int:
    try:
        return int(base64.b64decode(cursor.encode()).decode())
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise AppError("validation_error", 422, "Invalid cursor") from exc


@router.get("", response_model=LogPage)
def list_logs(
    levels: list[str] | None = Query(default=None),
    logger: str | None = Query(default=None, description="logger name prefix"),
    config_id: int | None = Query(default=None),
    since: datetime | None = Query(default=None),
    until: datetime | None = Query(default=None),
    q: str | None = Query(default=None, description="message substring (LIKE)"),
    limit: int = Query(default=50, ge=1, le=MAX_LIMIT),
    cursor: str | None = Query(default=None, description="base64(last_id) — descending"),
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> LogPage:
    stmt = select(LogEntry)
    if levels:
        stmt = stmt.where(LogEntry.level.in_([lvl.upper() for lvl in levels]))
    if logger:
        stmt = stmt.where(LogEntry.logger.like(f"{logger}%"))
    if config_id is not None:
        stmt = stmt.where(LogEntry.config_id == config_id)
    if since is not None:
        stmt = stmt.where(LogEntry.timestamp >= since)
    if until is not None:
        stmt = stmt.where(LogEntry.timestamp <= until)
    if q:
        stmt = stmt.where(LogEntry.message.like(f"%{q}%"))
    if cursor:
        stmt = stmt.where(LogEntry.id < _decode_cursor(cursor))

    # Newest first, fetch one extra row to detect a further page.
    stmt = stmt.order_by(LogEntry.id.desc()).limit(limit + 1)
    rows = session.exec(stmt).all()

    has_more = len(rows) > limit
    items = rows[:limit]
    next_cursor = (
        _encode_cursor(items[-1].id) if has_more and items and items[-1].id else None
    )
    return LogPage(items=items, next_cursor=next_cursor, has_more=has_more)


@router.delete("", status_code=204)
def delete_logs(
    before: datetime = Query(..., description="delete records with timestamp < before"),
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> Response:
    session.exec(sa_delete(LogEntry).where(LogEntry.timestamp < before))
    session.commit()
    return Response(status_code=204)
