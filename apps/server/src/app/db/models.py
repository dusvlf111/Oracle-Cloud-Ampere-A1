"""SQLModel table definitions.

The full data model (OciCredential, InstanceConfig, NotificationChannel, ...)
lands in later Pushes (PRD §6). For Push 1 we only need a non-empty metadata
so Alembic's autogenerate / upgrade machinery has a target. `AppSetting` is a
trivial key/value table that is genuinely used (PRD §6) and lets us produce a
real initial migration.
"""

from __future__ import annotations

from sqlmodel import Field, SQLModel


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


# Re-export the shared metadata for Alembic's target_metadata.
metadata = SQLModel.metadata
