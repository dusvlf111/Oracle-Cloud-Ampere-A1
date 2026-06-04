"""Attempt read schema (PRD §7.4, §8).

``AttemptRead`` mirrors the ``Attempt`` table but enriches each row with the
human-readable ``config_name`` / ``credential_name`` resolved via join. Both are
``None``-able because a config (and therefore its credential) may have been
deleted after the attempt was recorded — the dashboard falls back to the raw
``config_id`` in that case.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class AttemptRead(BaseModel):
    id: int
    config_id: int
    config_name: str | None = None
    credential_name: str | None = None
    attempted_at: datetime
    status: str
    message: str | None = None
    instance_ocid: str | None = None
    duration_ms: int | None = None
