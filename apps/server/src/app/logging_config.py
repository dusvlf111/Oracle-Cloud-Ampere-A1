"""Custom logging infrastructure (PRD §9.3).

Three sinks hang off the root logger:

* ``StreamHandler(stdout)`` with :class:`JsonFormatter` — structured JSON lines
  for Docker stdout.
* :class:`DbLogHandler` — synchronous INSERT into the ``LogEntry`` table.
* ``LogBusHandler`` (Task 3.3) — in-memory pub/sub for the SSE stream.

Context propagation: callers attach ``extra={"config_id": ..., "attempt_id":
..., "credential_id": ...}``. Both the JSON formatter and the DB handler pull
those predefined keys out of ``record.__dict__``; any other ``extra`` keys are
serialised into the ``extra`` JSON column / field.

Safety: the DB handler isolates its own failures via ``handleError`` and a
recursion guard drops records emitted by SQLAlchemy / the handler itself so a
logging INSERT can never trigger another logging INSERT.
"""

from __future__ import annotations

import json
import logging
import sys
from datetime import datetime, timezone

from sqlalchemy.engine import Engine
from sqlmodel import Session

from app.config import get_settings
from app.db.models import LogEntry

# Predefined context keys lifted onto LogEntry columns (PRD §9.3.4).
_CONTEXT_KEYS = ("config_id", "attempt_id", "credential_id")

# Standard LogRecord attributes — everything else in record.__dict__ that a
# caller passed via `extra=` is treated as additional context.
_RESERVED = {
    "name", "msg", "args", "levelname", "levelno", "pathname", "filename",
    "module", "exc_info", "exc_text", "stack_info", "lineno", "funcName",
    "created", "msecs", "relativeCreated", "thread", "threadName",
    "processName", "process", "taskName", "message", "asctime",
}

# Logger-name prefixes whose records must never hit the DB/bus handlers,
# otherwise a write would recurse into another log record (PRD §9.3.5).
_RECURSION_PREFIXES = ("sqlalchemy", "aiosqlite", "app.db", "alembic")


def _iso(ts: float) -> str:
    return (
        datetime.fromtimestamp(ts, tz=timezone.utc)
        .isoformat(timespec="milliseconds")
        .replace("+00:00", "Z")
    )


def _extract_context(record: logging.LogRecord) -> tuple[dict, dict]:
    """Return ``(context, extra)`` pulled from ``record.__dict__``.

    ``context`` holds the predefined keys; ``extra`` holds any remaining
    user-supplied attributes.
    """
    context = {k: record.__dict__.get(k) for k in _CONTEXT_KEYS}
    extra = {
        k: v
        for k, v in record.__dict__.items()
        if k not in _RESERVED and k not in _CONTEXT_KEYS and not k.startswith("_")
    }
    return context, extra


class NoRecursionFilter(logging.Filter):
    """Drop records from loggers that could recurse through a DB write."""

    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith(_RECURSION_PREFIXES)


class JsonFormatter(logging.Formatter):
    """Render a record as a single-line JSON object (PRD §9.3.3)."""

    def format(self, record: logging.LogRecord) -> str:
        context, extra = _extract_context(record)
        payload: dict = {
            "ts": _iso(record.created),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }
        for key, value in context.items():
            if value is not None:
                payload[key] = value
        if extra:
            payload["extra"] = extra
        if record.exc_info:
            payload["exc_info"] = self.formatException(record.exc_info)
        return json.dumps(payload, ensure_ascii=False, default=str)


class DbLogHandler(logging.Handler):
    """Synchronously INSERT each record into the ``LogEntry`` table.

    Failures are swallowed via :meth:`handleError` so a DB outage never breaks
    the request/worker path (PRD §9.3.5).
    """

    # Reused only for its formatException() helper (records carry their own data).
    _exc_formatter = logging.Formatter()

    def __init__(self, engine: Engine, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._engine = engine
        self.addFilter(NoRecursionFilter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            context, extra = _extract_context(record)
            entry = LogEntry(
                timestamp=datetime.fromtimestamp(record.created, tz=timezone.utc),
                level=record.levelname,
                logger=record.name,
                message=record.getMessage(),
                config_id=context["config_id"],
                attempt_id=context["attempt_id"],
                credential_id=context["credential_id"],
                extra=json.dumps(extra, ensure_ascii=False, default=str) if extra else None,
                exc_info=(
                    self._exc_formatter.formatException(record.exc_info)
                    if record.exc_info
                    else None
                ),
            )
            with Session(self._engine) as session:
                session.add(entry)
                session.commit()
        except Exception:  # noqa: BLE001 — must never propagate to the app
            self.handleError(record)


def configure_logging(engine: Engine | None = None) -> logging.Logger:
    """Install the stdout JSON handler (+ optional DB handler) on the root logger.

    Idempotent: clears previously installed app handlers so repeated calls
    (tests, reloads) don't duplicate output. ``LogBusHandler`` is attached
    separately in :func:`app.log_bus.attach_log_bus`.
    """
    settings = get_settings()
    root = logging.getLogger()

    # Remove handlers we previously installed (tagged via attribute).
    for h in list(root.handlers):
        if getattr(h, "_app_managed", False):
            root.removeHandler(h)

    root.setLevel(logging.DEBUG)

    stream = logging.StreamHandler(sys.stdout)
    stream.setFormatter(JsonFormatter())
    stream.setLevel(getattr(logging, settings.log_level.upper(), logging.INFO))
    stream._app_managed = True  # type: ignore[attr-defined]
    root.addHandler(stream)

    if engine is not None:
        db_level_name = (settings.log_level_db or settings.log_level).upper()
        db = DbLogHandler(engine, level=getattr(logging, db_level_name, logging.INFO))
        db._app_managed = True  # type: ignore[attr-defined]
        root.addHandler(db)

    # Quiet noisy libraries (PRD §9.3.2).
    for noisy in ("uvicorn.access", "sqlalchemy.engine", "httpx", "httpcore"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    return root
