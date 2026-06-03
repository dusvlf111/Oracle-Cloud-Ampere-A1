"""Slack notifier format tests (PRD §7.5.1)."""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock

from app.services.notifier import slack
from app.services.notifier.types import NotificationPayload

WEBHOOK = "https://hooks.slack.com/services/T/B/x"


async def test_slack_block_kit_format(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=WEBHOOK, status_code=200, text="ok")
    payload = NotificationPayload(title="Header", body="*bold* body")
    await slack.send({"webhook_url": WEBHOOK}, payload)

    body = json.loads(httpx_mock.get_request().content)
    blocks = body["blocks"]
    assert blocks[0]["type"] == "header"
    assert blocks[0]["text"]["text"] == "Header"
    assert blocks[1]["type"] == "section"
    assert blocks[1]["text"]["text"] == "*bold* body"
