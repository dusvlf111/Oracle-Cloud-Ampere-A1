"""SQLModel table definitions.

The full data model (OciCredential, InstanceConfig, NotificationChannel, ...)
lands in later Pushes (PRD §6). For Push 1 we only need a non-empty metadata
so Alembic's autogenerate / upgrade machinery has a target. `AppSetting` is a
trivial key/value table that is genuinely used (PRD §6) and lets us produce a
real initial migration.
"""

from __future__ import annotations

from datetime import datetime

from sqlmodel import Field, SQLModel


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class LogEntry(SQLModel, table=True):
    """Structured, persisted log record (PRD §6, §9.3).

    Doubles as the FastAPI read schema. ``DbLogHandler`` populates it by
    extracting the predefined context keys (``config_id``/``attempt_id``/
    ``credential_id``) from ``record.__dict__``; anything else lands in
    ``extra`` as a JSON string. ``exc_info`` carries the formatted traceback
    for ERROR/CRITICAL records.
    """

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    level: str = Field(index=True)
    logger: str = Field(index=True)
    message: str
    config_id: int | None = Field(default=None, index=True)
    attempt_id: int | None = None
    credential_id: int | None = None
    extra: str | None = None
    exc_info: str | None = None


# Re-export the shared metadata for Alembic's target_metadata.
metadata = SQLModel.metadata
