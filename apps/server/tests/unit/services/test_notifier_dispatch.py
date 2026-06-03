"""Notifier dispatch / retry / fan-out tests (PRD §7.5.4)."""

from __future__ import annotations

import httpx
import pytest
from pytest_httpx import HTTPXMock

from app.config import Settings
from app.db.models import NotificationChannel
from app.services import crypto
from app.services.notifier import UnknownChannelType, fan_out, send
from app.services.notifier.types import NotificationPayload

NTFY_URL = "https://ntfy.example.com/topic"


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "get_settings", lambda: Settings(app_secret="notif-secret"))
    crypto._key_for.cache_clear()
    yield
    crypto._key_for.cache_clear()


def _ntfy_channel(name: str = "n", enabled: bool = True) -> NotificationChannel:
    enc = crypto.encrypt_json({"server_url": "https://ntfy.example.com", "topic": "topic"})
    return NotificationChannel(id=1, name=name, type="ntfy", enabled=enabled, config_enc=enc)


def _payload() -> NotificationPayload:
    return NotificationPayload(title="t", body="b")


async def test_send_dispatches_to_ntfy(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=NTFY_URL, status_code=200)
    await send(_ntfy_channel(), _payload())
    assert len(httpx_mock.get_requests()) == 1


async def test_send_retries_on_5xx_then_succeeds(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=NTFY_URL, status_code=503)
    httpx_mock.add_response(url=NTFY_URL, status_code=200)
    await send(_ntfy_channel(), _payload())
    assert len(httpx_mock.get_requests()) == 2  # 1 retry


async def test_send_retries_twice_then_fails(httpx_mock: HTTPXMock) -> None:
    # 3 attempts total (initial + 2 retries), all 500 → raises.
    for _ in range(3):
        httpx_mock.add_response(url=NTFY_URL, status_code=500)
    with pytest.raises(httpx.HTTPStatusError):
        await send(_ntfy_channel(), _payload())
    assert len(httpx_mock.get_requests()) == 3


async def test_send_does_not_retry_on_4xx(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=NTFY_URL, status_code=403)
    with pytest.raises(httpx.HTTPStatusError):
        await send(_ntfy_channel(), _payload())
    assert len(httpx_mock.get_requests()) == 1  # no retry on user-config error


async def test_unknown_channel_type() -> None:
    enc = crypto.encrypt_json({"foo": "bar"})
    ch = NotificationChannel(id=9, name="x", type="carrier-pigeon", config_enc=enc)
    with pytest.raises(UnknownChannelType):
        await send(ch, _payload())


async def test_fan_out_isolates_failures(httpx_mock: HTTPXMock) -> None:
    # ok channel succeeds, bad channel (4xx) fails — exception captured, not raised.
    ok = _ntfy_channel(name="ok")
    bad_enc = crypto.encrypt_json({"server_url": "https://bad.example.com", "topic": "t"})
    bad = NotificationChannel(id=2, name="bad", type="ntfy", config_enc=bad_enc)

    httpx_mock.add_response(url="https://ntfy.example.com/topic", status_code=200)
    httpx_mock.add_response(url="https://bad.example.com/t", status_code=400)

    results = await fan_out([ok, bad], _payload())
    assert results[0] is None
    assert isinstance(results[1], BaseException)


async def test_fan_out_skips_disabled(httpx_mock: HTTPXMock) -> None:
    disabled = _ntfy_channel(name="off", enabled=False)
    results = await fan_out([disabled], _payload())
    assert results == []
    assert httpx_mock.get_requests() == []
