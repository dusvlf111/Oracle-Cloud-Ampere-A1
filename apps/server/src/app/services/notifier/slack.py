"""Slack incoming-webhook sender (Block Kit) (PRD §7.5.1)."""

from __future__ import annotations

import httpx

from app.services.notifier.types import NotificationPayload

TIMEOUT = 5.0


async def send(cfg: dict, payload: NotificationPayload) -> None:
    blocks = [
        {
            "type": "header",
            "text": {"type": "plain_text", "text": payload.title, "emoji": True},
        },
        {"type": "section", "text": {"type": "mrkdwn", "text": payload.body}},
    ]
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(cfg["webhook_url"], json={"blocks": blocks})
        resp.raise_for_status()
