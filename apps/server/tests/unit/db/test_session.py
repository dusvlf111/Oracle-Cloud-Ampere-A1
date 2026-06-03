"""DB engine: WAL pragma + session fixtures."""

from __future__ import annotations

from sqlalchemy import text
from sqlmodel import Session

from app.db.session import create_db_engine


def test_wal_pragma_applied(tmp_path) -> None:
    # WAL only applies to file-backed SQLite databases.
    db_file = tmp_path / "wal.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    with engine.connect() as conn:
        mode = conn.execute(text("PRAGMA journal_mode")).scalar()
    assert str(mode).lower() == "wal"


def test_foreign_keys_enabled(tmp_path) -> None:
    db_file = tmp_path / "fk.db"
    engine = create_db_engine(f"sqlite:///{db_file}")
    with engine.connect() as conn:
        fk = conn.execute(text("PRAGMA foreign_keys")).scalar()
    assert int(fk) == 1


def test_engine_fixture(engine) -> None:
    # Fixture provides a working in-memory engine with schema created.
    with Session(engine) as s:
        assert s.exec  # session usable


def test_session_fixture(session: Session) -> None:
    from app.db.models import AppSetting

    session.add(AppSetting(key="k", value="v"))
    session.commit()
    got = session.get(AppSetting, "k")
    assert got is not None
    assert got.value == "v"
