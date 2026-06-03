"""Telegram Bot API sender (parse_mode=HTML) (PRD §7.5.1)."""

from __future__ import annotations

from html import escape

import httpx

from app.services.notifier.types import NotificationPayload

TIMEOUT = 5.0


async def send(cfg: dict, payload: NotificationPayload) -> None:
    text = f"<b>{escape(payload.title)}</b>\n{escape(payload.body)}"
    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            url,
            json={
                "chat_id": cfg["chat_id"],
                "text": text,
                "parse_mode": "HTML",
            },
        )
        resp.raise_for_status()
