"""Notification dispatch (PRD §7.5.4, skill: notification-channels).

``send(channel, payload)`` decrypts the channel config, picks the channel
module, and posts with a 5s timeout + 2 retries (tenacity). Transient
failures (timeouts, network errors, 5xx) are retried; 4xx user-config errors
fail immediately. ``fan_out`` sends to many channels in parallel, isolating
failures so one bad channel never blocks the others (only an ERROR log).
"""

from __future__ import annotations

import asyncio
import logging

import httpx
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.db.models import NotificationChannel
from app.services.crypto import decrypt_json
from app.services.notifier import discord, ntfy, slack, telegram
from app.services.notifier.types import NotificationPayload, NotifyKind

logger = logging.getLogger("app.services.notifier")

DISPATCH = {
    "discord": discord.send,
    "slack": slack.send,
    "telegram": telegram.send,
    "ntfy": ntfy.send,
}


class UnknownChannelType(Exception):
    def __init__(self, channel_type: str) -> None:
        super().__init__(f"Unknown channel type: {channel_type}")
        self.channel_type = channel_type


def _is_retryable(exc: BaseException) -> bool:
    """Retry transport-level errors and 5xx; never retry 4xx (user error)."""
    if isinstance(exc, (httpx.TimeoutException, httpx.NetworkError)):
        return True
    if isinstance(exc, httpx.HTTPStatusError):
        return exc.response.status_code >= 500
    return False


# stop_after_attempt(3) == initial try + 2 retries (PRD §7.5.4).
_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_exception(_is_retryable),
    reraise=True,
)


async def _dispatch(channel_type: str, cfg: dict, payload: NotificationPayload) -> None:
    fn = DISPATCH.get(channel_type)
    if fn is None:
        raise UnknownChannelType(channel_type)
    await fn(cfg, payload)


async def send(channel: NotificationChannel, payload: NotificationPayload) -> None:
    """Send one notification with retry. Raises on final failure."""
    cfg = decrypt_json(channel.config_enc)

    @_retry
    async def _attempt() -> None:
        await _dispatch(channel.type, cfg, payload)

    await _attempt()


async def fan_out(
    channels: list[NotificationChannel], payload: NotificationPayload
) -> list[BaseException | None]:
    """Send to all enabled channels in parallel; failures are isolated."""
    enabled = [c for c in channels if c.enabled]
    results = await asyncio.gather(
        *[send(ch, payload) for ch in enabled],
        return_exceptions=True,
    )
    for ch, result in zip(enabled, results):
        if isinstance(result, BaseException):
            logger.error(
                "알림 발송 실패 channel=%s type=%s",
                ch.name,
                ch.type,
                extra={"channel_id": ch.id},
                exc_info=result,
            )
    return [r if isinstance(r, BaseException) else None for r in results]


__all__ = [
    "DISPATCH",
    "NotificationPayload",
    "NotifyKind",
    "UnknownChannelType",
    "fan_out",
    "send",
]
