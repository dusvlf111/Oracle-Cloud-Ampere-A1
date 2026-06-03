"""Log query / delete API (PRD §8).

GET    /api/logs        — filtered, cursor-paginated query → ``LogPage``
DELETE /api/logs?before — bulk delete of records older than an ISO timestamp

The SSE stream (``GET /api/logs/stream``) is added in Task 3.5. Every route
requires an authenticated session (``require_login``).
"""

from __future__ import annotations

import asyncio
import base64
import json
from collections.abc import AsyncIterator, Awaitable, Callable
from datetime import datetime

from fastapi import APIRouter, Depends, Query, Request, Response
from pydantic import BaseModel
from sqlalchemy import delete as sa_delete
from sqlmodel import Session, select
from sse_starlette.sse import EventSourceResponse

from app.api.deps import AppError, require_login
from app.db.models import LogEntry
from app.db.session import get_session
from app.log_bus import log_bus

router = APIRouter(prefix="/api/logs", tags=["logs"])

MAX_LIMIT = 200
HEARTBEAT_SEC = 15.0


def _record_matches(
    rec: dict,
    *,
    levels: list[str] | None,
    logger: str | None,
    config_id: int | None,
) -> bool:
    if levels and rec.get("level") not in levels:
        return False
    if logger and not str(rec.get("logger", "")).startswith(logger):
        return False
    if config_id is not None and rec.get("config_id") != config_id:
        return False
    return True


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


async def sse_event_stream(
    *,
    is_disconnected: Callable[[], Awaitable[bool]],
    levels: list[str] | None,
    logger: str | None,
    config_id: int | None,
    heartbeat: float = HEARTBEAT_SEC,
) -> AsyncIterator[dict]:
    """Yield SSE ``log`` / ``ping`` events off the :data:`log_bus`.

    Extracted from the route so it can be unit-tested without a live HTTP
    connection: callers feed records by publishing to ``log_bus`` and control
    termination via the ``is_disconnected`` predicate.
    """
    norm_levels = [lvl.upper() for lvl in levels] if levels else None
    async with log_bus.subscribe() as queue:
        while True:
            if await is_disconnected():
                break
            try:
                rec = await asyncio.wait_for(queue.get(), timeout=heartbeat)
            except asyncio.TimeoutError:
                yield {"event": "ping", "data": "{}"}
                continue
            if _record_matches(
                rec, levels=norm_levels, logger=logger, config_id=config_id
            ):
                yield {"event": "log", "data": json.dumps(rec, default=str)}


@router.get("/stream")
async def stream_logs(
    request: Request,
    levels: list[str] | None = Query(default=None),
    logger: str | None = Query(default=None),
    config_id: int | None = Query(default=None),
    _user: str = Depends(require_login),
) -> EventSourceResponse:
    """Live log stream over SSE (PRD §8, §9.3.7).

    Subscribes to the in-memory :data:`log_bus`, applies the same filter
    semantics as the query endpoint, and emits a ``ping`` heartbeat every
    15 seconds so idle proxies don't drop the connection.
    """
    return EventSourceResponse(
        sse_event_stream(
            is_disconnected=request.is_disconnected,
            levels=levels,
            logger=logger,
            config_id=config_id,
        )
    )

    return EventSourceResponse(event_gen())


@router.delete("", status_code=204)
def delete_logs(
    before: datetime = Query(..., description="delete records with timestamp < before"),
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> Response:
    session.exec(sa_delete(LogEntry).where(LogEntry.timestamp < before))
    session.commit()
    return Response(status_code=204)
