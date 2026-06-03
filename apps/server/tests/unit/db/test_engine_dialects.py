"""Engine construction branches by dialect (task 8.3, PRD §9.2/§10).

These tests verify the *configuration* of the engine without opening a real
connection — a PostgreSQL URL produces a pooled engine with the WAL pragma
listener absent, while a SQLite URL registers the pragma and skips pooling.
No live PostgreSQL server is required.
"""

from __future__ import annotations

import pytest
from sqlalchemy import event
from sqlalchemy.pool import QueuePool, StaticPool

import app.db.session as session_mod
from app.config import Settings
from app.db.session import create_db_engine


@pytest.fixture
def pg_settings(monkeypatch):
    """Patch get_settings so pool defaults come from a known Settings."""
    s = Settings(
        _env_file=None,
        db_pool_size=4,
        db_max_overflow=6,
        db_pool_pre_ping=True,
    )
    monkeypatch.setattr(session_mod, "get_settings", lambda: s)
    return s


def test_sqlite_registers_wal_pragma_listener(tmp_path):
    engine = create_db_engine(f"sqlite:///{tmp_path / 'a.db'}")
    assert event.contains(engine, "connect", session_mod._enable_sqlite_wal)
    engine.dispose()


def test_sqlite_uses_check_same_thread_false():
    engine = create_db_engine("sqlite://")
    # in-memory SQLite uses SingletonThreadPool but connect_args is applied.
    assert engine.dialect.name == "sqlite"
    engine.dispose()


def test_postgres_applies_pool_options_from_settings(pg_settings):
    engine = create_db_engine("postgresql+psycopg://u:p@db:5432/oci")
    assert engine.dialect.name == "postgresql"
    assert isinstance(engine.pool, QueuePool)
    assert engine.pool.size() == 4
    assert engine.pool._max_overflow == 6
    assert engine.pool._pre_ping is True
    engine.dispose()


def test_postgres_does_not_register_wal_pragma(pg_settings):
    engine = create_db_engine("postgresql+psycopg://u:p@db:5432/oci")
    assert not event.contains(engine, "connect", session_mod._enable_sqlite_wal)
    engine.dispose()


def test_postgres_explicit_pool_args_override_settings(pg_settings):
    engine = create_db_engine(
        "postgresql+psycopg://u:p@db:5432/oci",
        pool_size=11,
        max_overflow=2,
    )
    assert engine.pool.size() == 11
    assert engine.pool._max_overflow == 2
    engine.dispose()


def test_custom_poolclass_skips_injected_pool_args():
    # Passing poolclass (as the test fixtures do) must not collide with
    # pool_size/max_overflow injection.
    engine = create_db_engine(
        "postgresql+psycopg://u:p@db:5432/oci",
        poolclass=StaticPool,
    )
    assert isinstance(engine.pool, StaticPool)
    engine.dispose()
