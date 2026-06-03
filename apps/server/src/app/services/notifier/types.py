"""Common notification payload (PRD §7.5.6, skill: notification-channels)."""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, Field


class NotifyKind(str, Enum):
    SUCCESS = "success"  # instance created
    WARNING = "warning"  # auth error, auto-disable
    ERROR = "error"  # send failure
    INFO = "info"


class NotificationPayload(BaseModel):
    """Channel-agnostic message; each channel module renders its own format."""

    kind: NotifyKind = NotifyKind.INFO
    title: str
    body: str
    tags: list[str] = Field(default_factory=list)
    metadata: dict = Field(default_factory=dict)  # config_id, attempt_id, ...
