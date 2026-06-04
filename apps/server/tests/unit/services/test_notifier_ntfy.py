"""ntfy notifier tests — headers, self-host, auth (PRD §7.5.1, §7.5.5)."""

from __future__ import annotations

from pytest_httpx import HTTPXMock

from app.services.notifier import ntfy
from app.services.notifier.types import NotificationPayload, NotifyKind

SERVER = "https://ntfy.supabin.com"
TOPIC = "oci-arm-alerts"
URL = f"{SERVER}/{TOPIC}"


async def test_ntfy_headers_and_body(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=200)
    payload = NotificationPayload(
        kind=NotifyKind.SUCCESS, title="Success", body="Body", tags=["rocket"]
    )
    cfg = {
        "server_url": SERVER,
        "topic": TOPIC,
        "token": "tk_secret",
        "priority": 4,
        "tags": ["oracle"],
    }
    await ntfy.send(cfg, payload)

    req = httpx_mock.get_request()
    assert str(req.url) == URL
    # Non-ASCII title is transmitted as UTF-8 bytes (ntfy decodes UTF-8).
    raw = dict(req.headers.raw)
    assert raw[b"Title"].decode("utf-8") == "Success"
    assert req.headers["Priority"] == "4"
    assert raw[b"Tags"].decode("utf-8") == "rocket,oracle"
    assert req.headers["Authorization"] == "Bearer tk_secret"
    assert req.content == "Body".encode()


async def test_ntfy_priority_defaults_to_kind(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=200)
    payload = NotificationPayload(kind=NotifyKind.SUCCESS, title="t", body="b")
    await ntfy.send({"server_url": SERVER, "topic": TOPIC}, payload)
    # success kind → priority 5 when not overridden.
    assert httpx_mock.get_request().headers["Priority"] == "5"


async def test_ntfy_no_token_omits_authorization(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=200)
    payload = NotificationPayload(title="t", body="b")
    await ntfy.send({"server_url": SERVER, "topic": TOPIC}, payload)
    assert "Authorization" not in httpx_mock.get_request().headers


async def test_ntfy_trailing_slash_normalised(httpx_mock: HTTPXMock) -> None:
    httpx_mock.add_response(url=URL, status_code=200)
    payload = NotificationPayload(title="t", body="b")
    await ntfy.send({"server_url": SERVER + "/", "topic": TOPIC}, payload)
    assert str(httpx_mock.get_request().url) == URL
