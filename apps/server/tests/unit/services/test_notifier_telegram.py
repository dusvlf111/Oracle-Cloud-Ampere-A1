"""Telegram notifier format tests (PRD §7.5.1)."""

from __future__ import annotations

import json

from pytest_httpx import HTTPXMock

from app.services.notifier import telegram
from app.services.notifier.types import NotificationPayload

TOKEN = "123456:ABC"
URL = f"https://api.telegram.org/bot{TOKEN}/sendMessage"


async def test_telegram_html_format(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, json={"ok": True})
    payload = NotificationPayload(title="Title <b>", body="a & b")
    await telegram.send({"bot_token": TOKEN, "chat_id": "-100123"}, payload)

    body = json.loads(httpx_mock.get_request().content)
    assert body["chat_id"] == "-100123"
    assert body["parse_mode"] == "HTML"
    # HTML-escaped to avoid breaking parse_mode.
    assert "&lt;b&gt;" in body["text"]
    assert "a &amp; b" in body["text"]
