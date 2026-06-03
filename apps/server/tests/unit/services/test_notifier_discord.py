"""Discord notifier format tests (PRD §7.5.1)."""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock

from app.services.notifier import discord
from app.services.notifier.types import NotificationPayload, NotifyKind

WEBHOOK = "https://discord.com/api/webhooks/123/abc"


async def test_discord_embed_format(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=WEBHOOK, status_code=204)
    payload = NotificationPayload(
        kind=NotifyKind.SUCCESS, title="OK", body="line1\nline2", tags=["x"]
    )
    await discord.send({"webhook_url": WEBHOOK}, payload)

    req = httpx_mock.get_request()
    assert req.method == "POST"
    body = json.loads(req.content)
    embed = body["embeds"][0]
    assert embed["title"] == "OK"
    assert embed["description"] == "line1\nline2"
    assert embed["color"] == discord.COLOR["success"]
