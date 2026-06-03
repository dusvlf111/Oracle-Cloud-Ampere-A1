"""Discord webhook sender (PRD §7.5.1)."""

from __future__ import annotations

import httpx

from app.services.notifier.types import NotificationPayload

COLOR = {
    "success": 0x22C55E,
    "warning": 0xF59E0B,
    "error": 0xEF4444,
    "info": 0x3B82F6,
}

TIMEOUT = 5.0


async def send(cfg: dict, payload: NotificationPayload) -> None:
    embed = {
        "title": payload.title,
        "description": payload.body,
        "color": COLOR.get(payload.kind.value, 0x6B7280),
    }
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(cfg["webhook_url"], json={"embeds": [embed]})
        resp.raise_for_status()
