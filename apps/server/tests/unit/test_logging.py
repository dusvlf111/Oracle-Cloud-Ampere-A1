"""JsonFormatter + DbLogHandler tests (PRD §9.3)."""

from __future__ import annotations

import json
import logging

import pytest
from sqlmodel import Session, select

from app.db.models import LogEntry
from app.logging_config import DbLogHandler, JsonFormatter, NoRecursionFilter


def _record(
    *,
    name: str = "app.workers.poller",
    level: int = logging.INFO,
    msg: str = "hello %s",
    args: tuple = ("world",),
    exc_info=None,
    **extra,
) -> logging.LogRecord:
    rec = logging.LogRecord(
        name=name,
        level=level,
        pathname=__file__,
        lineno=10,
        msg=msg,
        args=args,
        exc_info=exc_info,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


# --- JsonFormatter -------------------------------------------------------


def test_json_formatter_schema() -> None:
    out = json.loads(JsonFormatter().format(_record(config_id=3, attempt_id=142)))
    assert out["level"] == "INFO"
    assert out["logger"] == "app.workers.poller"
    assert out["message"] == "hello world"
    assert out["config_id"] == 3
    assert out["attempt_id"] == 142
    assert out["ts"].endswith("Z")
    # Unset context keys are omitted, not null.
    assert "credential_id" not in out


def test_json_formatter_extra_and_exc_info() -> None:
    try:
        raise ValueError("boom")
    except ValueError:
        import sys

        rec = _record(level=logging.ERROR, msg="failed", args=(), region="seoul",
                      exc_info=sys.exc_info())
    out = json.loads(JsonFormatter().format(rec))
    assert out["extra"] == {"region": "seoul"}
    assert "Traceback" in out["exc_info"]
    assert "ValueError: boom" in out["exc_info"]


# --- DbLogHandler --------------------------------------------------------


def test_db_handler_maps_context_to_columns(engine, session: Session) -> None:
    handler = DbLogHandler(engine)
    handler.emit(_record(config_id=5, attempt_id=142, credential_id=1, region="ap"))

    entry = session.exec(select(LogEntry)).one()
    assert entry.message == "hello world"
    assert entry.config_id == 5
    assert entry.attempt_id == 142
    assert entry.credential_id == 1
    assert json.loads(entry.extra) == {"region": "ap"}
    assert entry.exc_info is None


def test_db_handler_stores_exc_info_for_errors(engine, session: Session) -> None:
    import sys

    handler = DbLogHandler(engine)
    try:
        raise RuntimeError("kaboom")
    except RuntimeError:
        handler.emit(_record(level=logging.ERROR, msg="err", args=(),
                             exc_info=sys.exc_info()))

    entry = session.exec(select(LogEntry)).one()
    assert entry.level == "ERROR"
    assert "RuntimeError: kaboom" in entry.exc_info


def test_db_handler_isolates_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    """A broken engine must not raise out of emit()."""

    class BrokenEngine:
        def __getattr__(self, _name):
            raise RuntimeError("db down")

    handler = DbLogHandler.__new__(DbLogHandler)
    logging.Handler.__init__(handler, level=logging.INFO)
    handler._engine = BrokenEngine()  # type: ignore[attr-defined]
    handler.addFilter(NoRecursionFilter())

    seen: list[logging.LogRecord] = []
    monkeypatch.setattr(handler, "handleError", lambda rec: seen.append(rec))

    handler.emit(_record())  # must not raise
    assert len(seen) == 1


def test_recursion_filter_blocks_db_loggers(engine, session: Session) -> None:
    handler = DbLogHandler(engine)
    # SQLAlchemy's own logs must be dropped before they trigger another INSERT.
    rec = _record(name="sqlalchemy.engine.Engine", msg="SELECT 1", args=())
    if all(f.filter(rec) for f in handler.filters):
        handler.emit(rec)

    assert session.exec(select(LogEntry)).all() == []

    # A normal app record still gets through.
    handler.emit(_record(name="app.api.auth", msg="ok", args=()))
    assert len(session.exec(select(LogEntry)).all()) == 1
