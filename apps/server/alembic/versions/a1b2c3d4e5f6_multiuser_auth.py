"""multiuser_auth — User table + AppSetting→User migration + owner_id backfill

Non-disruptive, idempotent migration (PRD §5):

  1. create ``user`` table
  2. move the legacy single admin (``AppSetting.admin_username`` /
     ``admin_password_hash``) into a ``User(role=admin, status=active)`` row,
     then delete those AppSetting keys
  3. add nullable ``owner_id`` to ``ocicredential`` / ``instanceconfig`` /
     ``notificationchannel`` and backfill every existing row with that admin id
  4. enforce ``owner_id`` NOT NULL

Designed to run once against a live DB that already has an admin + resources.
Each step is guarded so a re-run (or a fresh DB with no admin) is safe.

Revision ID: a1b2c3d4e5f6
Revises: 1b9a876eab13
Create Date: 2026-06-04
"""
from __future__ import annotations

from collections.abc import Sequence
from datetime import datetime

import sqlalchemy as sa
import sqlmodel
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a1b2c3d4e5f6"
down_revision: str | None = "1b9a876eab13"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


_OWNER_TABLES = ("ocicredential", "instanceconfig", "notificationchannel")


def _has_table(bind: sa.engine.Connection, name: str) -> bool:
    return sa.inspect(bind).has_table(name)


def _has_column(bind: sa.engine.Connection, table: str, column: str) -> bool:
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()

    # --- 1. user table (idempotent) ------------------------------------- #
    if not _has_table(bind, "user"):
        op.create_table(
            "user",
            sa.Column("id", sa.Integer(), nullable=False),
            sa.Column("username", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column(
                "password_hash", sqlmodel.sql.sqltypes.AutoString(), nullable=False
            ),
            sa.Column("role", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("status", sqlmodel.sql.sqltypes.AutoString(), nullable=False),
            sa.Column("created_at", sa.DateTime(), nullable=False),
            sa.Column("approved_at", sa.DateTime(), nullable=True),
            sa.Column("approved_by", sa.Integer(), nullable=True),
            sa.ForeignKeyConstraint(["approved_by"], ["user.id"]),
            sa.PrimaryKeyConstraint("id"),
        )
        op.create_index(op.f("ix_user_username"), "user", ["username"], unique=True)
        op.create_index(op.f("ix_user_role"), "user", ["role"], unique=False)
        op.create_index(op.f("ix_user_status"), "user", ["status"], unique=False)

    # --- 2. migrate legacy admin (AppSetting → User) -------------------- #
    admin_id = _migrate_legacy_admin(bind)

    # --- 3 + 4. owner_id columns + backfill + NOT NULL ------------------ #
    for table in _OWNER_TABLES:
        if not _has_table(bind, table):
            continue
        if not _has_column(bind, table, "owner_id"):
            # Add nullable first so existing rows are accepted.
            with op.batch_alter_table(table) as batch:
                batch.add_column(
                    sa.Column("owner_id", sa.Integer(), nullable=True)
                )
                batch.create_index(
                    op.f(f"ix_{table}_owner_id"), ["owner_id"], unique=False
                )

        # Backfill any NULL owner with the admin id (only if we have one).
        if admin_id is not None:
            op.execute(
                sa.text(
                    f"UPDATE {table} SET owner_id = :aid WHERE owner_id IS NULL"
                ).bindparams(aid=admin_id)
            )

        # Apply NOT NULL only when no NULLs remain (safe on empty/backfilled DB).
        null_count = bind.execute(
            sa.text(f"SELECT COUNT(*) FROM {table} WHERE owner_id IS NULL")
        ).scalar_one()
        if null_count == 0:
            with op.batch_alter_table(table) as batch:
                batch.alter_column(
                    "owner_id", existing_type=sa.Integer(), nullable=False
                )
                # Recreate the FK inside batch (SQLite copy-table requires it).
                batch.create_foreign_key(
                    f"fk_{table}_owner_id_user",
                    "user",
                    ["owner_id"],
                    ["id"],
                )


def _migrate_legacy_admin(bind: sa.engine.Connection) -> int | None:
    """Move the AppSetting admin pair into a User row; return its id.

    Returns the admin user's id (existing or newly created), or ``None`` if no
    legacy admin and no users exist yet (fresh DB).
    """
    if not _has_table(bind, "appsetting"):
        return _existing_admin_id(bind)

    rows = dict(
        bind.execute(
            sa.text(
                "SELECT key, value FROM appsetting "
                "WHERE key IN ('admin_username', 'admin_password_hash')"
            )
        ).all()
    )
    username = rows.get("admin_username")
    password_hash = rows.get("admin_password_hash")

    if not username or not password_hash:
        # No legacy admin to migrate.
        return _existing_admin_id(bind)

    # Idempotent: skip if a user with that username already exists.
    existing = bind.execute(
        sa.text("SELECT id FROM user WHERE username = :u").bindparams(u=username)
    ).first()
    if existing is not None:
        admin_id = existing[0]
    else:
        bind.execute(
            sa.text(
                "INSERT INTO user "
                "(username, password_hash, role, status, created_at, approved_at) "
                "VALUES (:u, :p, 'admin', 'active', :now, :now)"
            ).bindparams(u=username, p=password_hash, now=datetime.utcnow())
        )
        admin_id = bind.execute(
            sa.text("SELECT id FROM user WHERE username = :u").bindparams(u=username)
        ).scalar_one()

    # Remove the migrated keys from AppSetting.
    bind.execute(
        sa.text(
            "DELETE FROM appsetting "
            "WHERE key IN ('admin_username', 'admin_password_hash')"
        )
    )
    return admin_id


def _existing_admin_id(bind: sa.engine.Connection) -> int | None:
    """Lowest-id admin already in the user table (for re-runs), else None."""
    if not _has_table(bind, "user"):
        return None
    row = bind.execute(
        sa.text(
            "SELECT id FROM user WHERE role = 'admin' ORDER BY id LIMIT 1"
        )
    ).first()
    return row[0] if row else None


def downgrade() -> None:
    bind = op.get_bind()
    for table in _OWNER_TABLES:
        if _has_table(bind, table) and _has_column(bind, table, "owner_id"):
            with op.batch_alter_table(table) as batch:
                batch.drop_index(op.f(f"ix_{table}_owner_id"))
                batch.drop_column("owner_id")
    if _has_table(bind, "user"):
        op.drop_index(op.f("ix_user_status"), table_name="user")
        op.drop_index(op.f("ix_user_role"), table_name="user")
        op.drop_index(op.f("ix_user_username"), table_name="user")
        op.drop_table("user")
