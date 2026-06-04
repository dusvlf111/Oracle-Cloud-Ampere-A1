"""User model + non-disruptive migration tests (Push 9, task 9.1, PRD §5).

Exercises the real Alembic migration ``a1b2c3d4e5f6`` against a temp SQLite DB
that already holds a legacy admin (AppSetting pair) plus resources, asserting:

  - a ``User(role=admin, status=active)`` row is created from the AppSetting pair
  - the AppSetting admin keys are removed
  - every existing resource is backfilled with that admin's ``owner_id``
  - ``owner_id`` ends up NOT NULL
  - the migration is idempotent (a second upgrade is a no-op) and safe on a DB
    with no legacy admin

Also covers the ``User`` SQLModel relationships / owner_id columns directly.
"""

from __future__ import annotations

from datetime import datetime
from pathlib import Path

import sqlalchemy as sa
from alembic import command
from alembic.config import Config
from sqlmodel import Session, select

from app.db.models import (
    InstanceConfig,
    NotificationChannel,
    OciCredential,
    User,
)

SERVER_ROOT = Path(__file__).resolve().parents[3]


def _alembic_cfg(db_url: str) -> Config:
    cfg = Config(str(SERVER_ROOT / "alembic.ini"))
    cfg.set_main_option("script_location", str(SERVER_ROOT / "alembic"))
    cfg.set_main_option("sqlalchemy.url", db_url)
    return cfg


def _seed_pre_migration(engine: sa.Engine) -> None:
    """Build the schema as it existed *before* push9 and seed legacy data.

    We stamp the DB at the previous head (``1b9a876eab13``) by running the
    migration chain up to it, then insert a legacy admin pair + resources that
    lack ``owner_id``.
    """
    cfg = _alembic_cfg(str(engine.url))
    command.upgrade(cfg, "1b9a876eab13")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO appsetting (key, value) VALUES "
                "('admin_username', 'legacy-admin'), "
                "('admin_password_hash', '$argon2id$fake$hash')"
            )
        )
        conn.execute(
            sa.text(
                "INSERT INTO ocicredential "
                "(name, tenancy_ocid, user_ocid, fingerprint, region, "
                " private_key_path, created_at) "
                "VALUES ('cred-1', 'ocid1.tenancy..a', 'ocid1.user..a', 'fp', "
                "'ap-chuncheon-1', '/data/keys/1.pem', :now)"
            ).bindparams(now=datetime.utcnow())
        )
        cred_id = conn.execute(
            sa.text("SELECT id FROM ocicredential WHERE name='cred-1'")
        ).scalar_one()
        conn.execute(
            sa.text(
                "INSERT INTO instanceconfig "
                "(name, credential_id, enabled, shape, ocpus, memory_gb, "
                " boot_volume_gb, image_ocid, subnet_ocid, availability_domain, "
                " ssh_public_key, retry_interval_sec, created_at, updated_at) "
                "VALUES ('cfg-1', :cid, 1, 'VM.Standard.A1.Flex', 4, 24, 50, "
                "'ocid1.image..a', 'ocid1.subnet..a', 'AD-1', 'ssh-ed25519 AAAA', "
                "60, :now, :now)"
            ).bindparams(cid=cred_id, now=datetime.utcnow())
        )
        conn.execute(
            sa.text(
                "INSERT INTO notificationchannel "
                "(name, type, enabled, config_enc, created_at, updated_at) "
                "VALUES ('ch-1', 'ntfy', 1, 'enc', :now, :now)"
            ).bindparams(now=datetime.utcnow())
        )


def test_migration_moves_admin_and_backfills_owner(tmp_path: Path) -> None:
    db_path = tmp_path / "live.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)

    _seed_pre_migration(engine)

    # Run the push9 migration on the populated DB.
    command.upgrade(_alembic_cfg(url), "head")

    with Session(engine) as s:
        # Legacy admin became a User row.
        admin = s.exec(select(User).where(User.username == "legacy-admin")).one()
        assert admin.role == "admin"
        assert admin.status == "active"
        assert admin.password_hash == "$argon2id$fake$hash"
        assert admin.approved_at is not None

        # AppSetting admin keys are gone.
        remaining = s.exec(
            select(sa.text("key")).select_from(sa.text("appsetting"))
        ).all()
        keys = {r[0] if isinstance(r, tuple) else r for r in remaining}
        assert "admin_username" not in keys
        assert "admin_password_hash" not in keys

        # Resources backfilled with the admin owner.
        cred = s.exec(select(OciCredential)).one()
        cfg = s.exec(select(InstanceConfig)).one()
        ch = s.exec(select(NotificationChannel)).one()
        assert cred.owner_id == admin.id
        assert cfg.owner_id == admin.id
        assert ch.owner_id == admin.id

    engine.dispose()


def test_owner_id_is_not_null_after_migration(tmp_path: Path) -> None:
    db_path = tmp_path / "notnull.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    _seed_pre_migration(engine)
    command.upgrade(_alembic_cfg(url), "head")

    with engine.connect() as conn:
        for table in ("ocicredential", "instanceconfig", "notificationchannel"):
            cols = {c["name"]: c for c in sa.inspect(conn).get_columns(table)}
            assert "owner_id" in cols
            assert cols["owner_id"]["nullable"] is False
    engine.dispose()


def test_migration_is_idempotent(tmp_path: Path) -> None:
    db_path = tmp_path / "idem.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)
    _seed_pre_migration(engine)

    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "head")
    # Re-running upgrade to head must be a no-op (already at head); and the
    # internal helpers must tolerate the migrated state (no duplicate admin).
    command.upgrade(cfg, "head")

    with Session(engine) as s:
        admins = s.exec(select(User).where(User.role == "admin")).all()
        assert len(admins) == 1
    engine.dispose()


def test_migration_safe_without_legacy_admin(tmp_path: Path) -> None:
    """Fresh-ish DB with no AppSetting admin and no resources upgrades cleanly."""
    db_path = tmp_path / "fresh.db"
    url = f"sqlite:///{db_path}"
    engine = sa.create_engine(url)

    cfg = _alembic_cfg(url)
    command.upgrade(cfg, "1b9a876eab13")  # schema only, no seed
    command.upgrade(cfg, "head")

    with Session(engine) as s:
        users = s.exec(select(User)).all()
        assert users == []
    engine.dispose()


def test_user_model_relationships(session: Session) -> None:
    """User owns resources via owner_id; approved_by self-FK resolves."""
    admin = User(
        username="root",
        password_hash="h",
        role="admin",
        status="active",
        approved_at=datetime.utcnow(),
    )
    session.add(admin)
    session.commit()
    session.refresh(admin)

    member = User(
        username="member",
        password_hash="h2",
        role="user",
        status="active",
        approved_by=admin.id,
    )
    session.add(member)
    session.commit()
    session.refresh(member)
    assert member.approved_by == admin.id

    cred = OciCredential(
        name="c",
        tenancy_ocid="ocid1.tenancy..a",
        user_ocid="ocid1.user..a",
        fingerprint="fp",
        region="ap-chuncheon-1",
        private_key_path="/k.pem",
        owner_id=member.id,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)
    assert cred.owner_id == member.id
