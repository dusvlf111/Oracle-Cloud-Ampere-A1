"""key_db_encryption — move OCI private keys from disk into Fernet DB column

PRD §7.1 — Push 11. Replaces the on-disk ``/data/keys/{id}.pem`` files with a
Fernet-encrypted ``private_key_enc`` column on ``ocicredential``.

Migration safety (task 11.2):

  1. add nullable ``private_key_enc`` column (idempotent)
  2. for every credential, read its key file (``private_key_path``), Fernet-
     encrypt the PEM, and store it in ``private_key_enc``
  3. **only after** the encrypted value is committed do we delete the file —
     so an interrupted run never loses a key (re-run re-reads + re-encrypts)
  4. a credential whose key file is missing gets an empty ``private_key_enc``
     and a WARNING log; verify will fail so the user re-uploads (no silent
     data invention, no crash)
  5. drop the now-unused ``private_key_path`` column
  6. enforce NOT NULL on ``private_key_enc``

The plaintext PEM lives only in a local variable for the duration of the
encrypt call — it is never logged or re-written elsewhere.

downgrade() is intentionally unsupported: the plaintext key files have been
deleted, so we cannot reconstruct the old on-disk layout.

Revision ID: b2c3d4e5f6a7
Revises: a1b2c3d4e5f6
Create Date: 2026-06-04
"""
from __future__ import annotations

import logging
from collections.abc import Sequence
from pathlib import Path

import sqlalchemy as sa
import sqlmodel
from alembic import op

from app.services.crypto import fernet_encrypt

# revision identifiers, used by Alembic.
revision: str = "b2c3d4e5f6a7"
down_revision: str | None = "a1b2c3d4e5f6"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

logger = logging.getLogger("alembic.key_db_encryption")


def _has_column(bind: sa.engine.Connection, table: str, column: str) -> bool:
    cols = {c["name"] for c in sa.inspect(bind).get_columns(table)}
    return column in cols


def upgrade() -> None:
    bind = op.get_bind()
    if not sa.inspect(bind).has_table("ocicredential"):
        return

    # --- 1. add nullable private_key_enc (idempotent) ------------------- #
    if not _has_column(bind, "ocicredential", "private_key_enc"):
        with op.batch_alter_table("ocicredential") as batch:
            batch.add_column(
                sa.Column(
                    "private_key_enc",
                    sqlmodel.sql.sqltypes.AutoString(),
                    nullable=True,
                )
            )

    has_path = _has_column(bind, "ocicredential", "private_key_path")

    # --- 2 + 3 + 4. encrypt each key file into the DB, then delete it --- #
    if has_path:
        rows = bind.execute(
            sa.text(
                "SELECT id, private_key_path, private_key_enc "
                "FROM ocicredential"
            )
        ).all()
        for cred_id, key_path, existing_enc in rows:
            # Re-run safety: skip rows already migrated.
            if existing_enc:
                continue

            path = Path(key_path) if key_path else None
            if path is None or not path.exists():
                # Missing file → warn + leave empty so verify fails (re-upload).
                logger.warning(
                    "credential %s: key file missing (%s) — storing empty "
                    "private_key_enc; user must re-upload",
                    cred_id,
                    key_path,
                )
                bind.execute(
                    sa.text(
                        "UPDATE ocicredential SET private_key_enc = '' "
                        "WHERE id = :id"
                    ).bindparams(id=cred_id)
                )
                continue

            pem = path.read_text(encoding="utf-8")
            enc = fernet_encrypt(pem)
            # Persist the ciphertext FIRST.
            bind.execute(
                sa.text(
                    "UPDATE ocicredential SET private_key_enc = :enc "
                    "WHERE id = :id"
                ).bindparams(enc=enc, id=cred_id)
            )
            # Only now that the encrypted value is stored do we delete the file.
            try:
                path.unlink()
            except OSError as exc:  # pragma: no cover - best effort cleanup
                logger.warning(
                    "credential %s: could not remove key file %s: %s",
                    cred_id,
                    key_path,
                    exc,
                )

    # Backfill any remaining NULLs (e.g. column existed without path source).
    bind.execute(
        sa.text(
            "UPDATE ocicredential SET private_key_enc = '' "
            "WHERE private_key_enc IS NULL"
        )
    )

    # --- 5. drop the legacy private_key_path column --------------------- #
    if has_path:
        with op.batch_alter_table("ocicredential") as batch:
            batch.drop_column("private_key_path")

    # --- 6. enforce NOT NULL on private_key_enc ------------------------- #
    with op.batch_alter_table("ocicredential") as batch:
        batch.alter_column(
            "private_key_enc",
            existing_type=sqlmodel.sql.sqltypes.AutoString(),
            nullable=False,
        )


def downgrade() -> None:
    raise NotImplementedError(
        "key_db_encryption is not reversible: plaintext key files were deleted "
        "during upgrade and cannot be reconstructed."
    )
