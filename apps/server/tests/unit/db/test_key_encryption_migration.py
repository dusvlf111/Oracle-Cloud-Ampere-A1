"""OCI key file → Fernet DB migration tests (PRD §7.1, task 11.2).

Exercises the real Alembic migration ``b2c3d4e5f6a7`` against a temp SQLite DB
seeded at the previous head (``a1b2c3d4e5f6``) with credentials that still carry
on-disk ``private_key_path`` files, asserting:

  - a credential WITH a key file → upgrade encrypts the PEM into
    ``private_key_enc`` (decrypts back to the original) and deletes the file
  - a credential whose key file is MISSING → warning + empty ``private_key_enc``
    (no crash, no invented data)
  - the legacy ``private_key_path`` column is dropped and ``private_key_enc``
    ends up NOT NULL
  - downgrade is unsupported (raises)
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import pytest
import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlmodel import Session, select

from app.config import Settings
from app.db.models import OciCredential
from app.services import crypto

SERVER_ROOT = Path(__file__).resolve().parents[3]

_APP_SECRET = "migration-test-secret-123"

_PEM_PRESENT = (
    "-----BEGIN PRIVATE KEY-----\nPRESENT-KEY-CONTENT\n-----END PRIVATE KEY-----\n"
)


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch):
    """Point crypto at a fixed APP_SECRET so the migration can Fernet-encrypt."""
    settings = Settings(app_secret=_APP_SECRET)
    monkeypatch.setattr(crypto, "get_settings", lambda: settings)
    crypto._fernet_key_for.cache_clear()
    yield
    crypto._fernet_key_for.cache_clear()


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(SERVER_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _seed_pre_migration(engine: sa.Engine, keys_dir: Path) -> tuple[int, int]:
    """Stamp at a1b2c3d4e5f6 and seed an admin + two credentials.

    Returns ``(cred_with_file_id, cred_missing_file_id)``.
    """
    command.upgrade(_alembic_cfg(str(engine.url)), "a1b2c3d4e5f6")
    keys_dir.mkdir(parents=True, exist_ok=True)
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO user "
                "(username, password_hash, role, status, created_at, approved_at) "
                "VALUES ('admin', 'h', 'admin', 'active', :now, :now)"
            ).bindparams(now=datetime.utcnow())
        )
        admin_id = conn.execute(
            sa.text("SELECT id FROM user WHERE username='admin'")
        ).scalar_one()

        def _insert(name: str, key_path: str) -> int:
            conn.execute(
                sa.text(
                    "INSERT INTO ocicredential "
                    "(name, tenancy_ocid, user_ocid, fingerprint, region, "
                    " private_key_path, owner_id, created_at) "
                    "VALUES (:name, 'ocid1.tenancy..a', 'ocid1.user..a', 'fp', "
                    "'ap-chuncheon-1', :kp, :oid, :now)"
                ).bindparams(name=name, kp=key_path, oid=admin_id, now=datetime.utcnow())
            )
            return conn.execute(
                sa.text("SELECT id FROM ocicredential WHERE name=:n").bindparams(n=name)
            ).scalar_one()

        with_file_path = keys_dir / "withfile.pem"
        with_file_path.write_text(_PEM_PRESENT, encoding="utf-8")
        with_id = _insert("cred-with-file", str(with_file_path))

        missing_id = _insert("cred-missing", str(keys_dir / "gone.pem"))

    return with_id, missing_id


def test_migration_encrypts_present_key_and_deletes_file(tmp_path: Path) -> None:
    db_path = tmp_path / "live.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    keys_dir = tmp_path / "keys"
    with_id, _missing_id = _seed_pre_migration(engine, keys_dir)
    key_file = keys_dir / "withfile.pem"
    assert key_file.exists()

    command.upgrade(_alembic_cfg(url), "head")

    with Session(engine) as s:
        cred = s.get(OciCredential, with_id)
        assert cred.private_key_enc  # non-empty ciphertext stored
        assert _PEM_PRESENT not in cred.private_key_enc  # not plaintext
        # Decrypts back to the original PEM.
        assert crypto.fernet_decrypt(cred.private_key_enc) == _PEM_PRESENT

    # File deleted only after the encrypted value was committed.
    assert not key_file.exists()
    engine.dispose()


def test_migration_missing_file_warns_and_stores_empty(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    db_path = tmp_path / "missing.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    keys_dir = tmp_path / "keys"
    _with_id, missing_id = _seed_pre_migration(engine, keys_dir)

    import logging

    # Alembic's env.py runs ``fileConfig()`` which disables existing loggers and
    # detaches our capture handler. Neutralise it for this test so the migration
    # WARNING reaches a handler we attach to the migration logger.
    monkeypatch.setattr("logging.config.fileConfig", lambda *a, **k: None)

    records: list[logging.LogRecord] = []

    class _Capture(logging.Handler):
        def emit(self, record: logging.LogRecord) -> None:
            records.append(record)

    mig_logger = logging.getLogger("alembic.key_db_encryption")
    handler = _Capture(level=logging.WARNING)
    mig_logger.addHandler(handler)
    prev_level = mig_logger.level
    mig_logger.setLevel(logging.WARNING)
    try:
        command.upgrade(_alembic_cfg(url), "head")
    finally:
        mig_logger.removeHandler(handler)
        mig_logger.setLevel(prev_level)

    with Session(engine) as s:
        cred = s.get(OciCredential, missing_id)
        assert cred.private_key_enc == ""  # empty → verify fails → re-upload

    assert any("key file missing" in r.getMessage() for r in records)
    engine.dispose()


def test_private_key_path_dropped_and_enc_not_null(tmp_path: Path) -> None:
    db_path = tmp_path / "schema.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    keys_dir = tmp_path / "keys"
    _seed_pre_migration(engine, keys_dir)

    command.upgrade(_alembic_cfg(url), "head")

    with engine.connect() as conn:
        cols = {c["name"]: c for c in sa.inspect(conn).get_columns("ocicredential")}
        assert "private_key_path" not in cols
        assert "private_key_enc" in cols
        assert cols["private_key_enc"]["nullable"] is False
    engine.dispose()


def test_downgrade_is_unsupported(tmp_path: Path) -> None:
    db_path = tmp_path / "down.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    keys_dir = tmp_path / "keys"
    _seed_pre_migration(engine, keys_dir)
    command.upgrade(_alembic_cfg(url), "head")

    with pytest.raises(Exception):  # NotImplementedError surfaces through alembic
        command.downgrade(_alembic_cfg(url), "a1b2c3d4e5f6")
    engine.dispose()
