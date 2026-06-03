"""NotificationChannel schemas with Pydantic discriminated union (PRD §6, §8).

The channel config is validated per-type via a discriminated union on the
``type`` field, so a ``ntfy`` payload can't carry Discord fields and vice
versa. Responses mask sensitive fields (tokens / webhook URLs).
"""

from __future__ import annotations

from datetime import datetime
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

from app.db.models import NotificationChannel
from app.services.crypto import mask_secret

# --------------------------------------------------------------------------- #
# Per-type config models (discriminated on ``type``).
# --------------------------------------------------------------------------- #


class DiscordConfig(BaseModel):
    type: Literal["discord"] = "discord"
    webhook_url: str


class SlackConfig(BaseModel):
    type: Literal["slack"] = "slack"
    webhook_url: str


class TelegramConfig(BaseModel):
    type: Literal["telegram"] = "telegram"
    bot_token: str
    chat_id: str


class NtfyConfig(BaseModel):
    type: Literal["ntfy"] = "ntfy"
    server_url: str
    topic: str
    token: str | None = None
    priority: int = Field(default=3, ge=1, le=5)
    tags: list[str] = Field(default_factory=list)


ChannelConfig = Annotated[
    Union[DiscordConfig, SlackConfig, TelegramConfig, NtfyConfig],
    Field(discriminator="type"),
]


# --------------------------------------------------------------------------- #
# Request / response envelopes.
# --------------------------------------------------------------------------- #


class ChannelCreate(BaseModel):
    name: str
    type: Literal["discord", "slack", "telegram", "ntfy"]
    enabled: bool = True
    config: ChannelConfig


class ChannelUpdate(BaseModel):
    name: str
    type: Literal["discord", "slack", "telegram", "ntfy"]
    enabled: bool = True
    config: ChannelConfig


def mask_config(channel_type: str, cfg: dict) -> dict:
    """Return a copy of ``cfg`` with sensitive fields masked for responses."""
    masked = dict(cfg)
    if channel_type in {"discord", "slack"}:
        if "webhook_url" in masked:
            masked["webhook_url"] = mask_secret(masked["webhook_url"])
    elif channel_type == "telegram":
        if "bot_token" in masked:
            masked["bot_token"] = mask_secret(masked["bot_token"])
    elif channel_type == "ntfy":
        if masked.get("token"):
            masked["token"] = mask_secret(masked["token"])
    return masked


class ChannelRead(BaseModel):
    id: int
    name: str
    type: str
    enabled: bool
    config: dict
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, channel: NotificationChannel, cfg: dict) -> "ChannelRead":
        return cls(
            id=channel.id,
            name=channel.name,
            type=channel.type,
            enabled=channel.enabled,
            config=mask_config(channel.type, cfg),
            created_at=channel.created_at,
            updated_at=channel.updated_at,
        )


class TestSendResponse(BaseModel):
    ok: bool
    error: str | None = None
