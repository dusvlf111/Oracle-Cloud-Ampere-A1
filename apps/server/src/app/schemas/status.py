"""Polling status schema (PRD §7.3, §7.4).

``PollingStatusItem`` summarises one *enabled* ``InstanceConfig`` for the
dashboard's "currently polling" card list. It is derived purely from the DB
(config row + its credential + its attempt history) so it works without
reaching into the worker's in-memory state — the supervisor polls exactly the
``enabled=True`` configs (PRD §7.3.1).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PollingStatusItem(BaseModel):
    config_id: int
    config_name: str
    credential_name: str | None = None
    shape: str
    ocpus: int
    memory_gb: int
    retry_interval_sec: int
    last_attempt_status: str | None = None
    last_attempt_at: datetime | None = None
    total_attempts: int
