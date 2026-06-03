"""SQLite engine/session factory with WAL mode.

WAL (write-ahead logging) lets the worker tasks and request handlers read
concurrently without blocking writers (PRD §9.2).
"""

from __future__ import annotations

from collections.abc import Iterator

from sqlalchemy import event
from sqlalchemy.engine import Engine
from sqlmodel import Session, create_engine

from app.config import get_settings


def _enable_sqlite_wal(dbapi_conn, _connection_record) -> None:
    cursor = dbapi_conn.cursor()
    cursor.execute("PRAGMA journal_mode=WAL")
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_db_engine(database_url: str | None = None, **kwargs) -> Engine:
    """Create an engine and register the WAL pragma on every connection."""
    url = database_url or get_settings().database_url
    connect_args = dict(kwargs.pop("connect_args", {}))
    if url.startswith("sqlite"):
        connect_args.setdefault("check_same_thread", False)
    engine = create_engine(url, connect_args=connect_args, **kwargs)
    if url.startswith("sqlite"):
        event.listen(engine, "connect", _enable_sqlite_wal)
    return engine


# Application-wide engine (lazy default URL from settings).
_engine: Engine | None = None


def get_engine() -> Engine:
    global _engine
    if _engine is None:
        _engine = create_db_engine()
    return _engine


def get_session() -> Iterator[Session]:
    """FastAPI dependency yielding a session."""
    with Session(get_engine()) as session:
        yield session
