"""SSE /api/logs/stream tests (PRD §8, §9.3.7).

The event generator is exercised directly via :func:`sse_event_stream` (driven
by ``log_bus.publish``) rather than over a live HTTP stream — ASGITransport +
EventSourceResponse keeps the connection open indefinitely, which is unsuitable
for a deterministic unit test. A separate lightweight check covers the route's
auth guard.
"""

from __future__ import annotations

import asyncio
import json

import pytest
from httpx import AsyncClient

from app.api.logs import _record_matches, sse_event_stream
from app.log_bus import log_bus


def test_record_matches_filters() -> None:
    rec = {"level": "ERROR", "logger": "app.workers.poller", "config_id": 5}
    assert _record_matches(rec, levels=None, logger=None, config_id=None)
    assert _record_matches(rec, levels=["ERROR"], logger="app.workers", config_id=5)
    assert not _record_matches(rec, levels=["INFO"], logger=None, config_id=None)
    assert not _record_matches(rec, levels=None, logger="app.api", config_id=None)
    assert not _record_matches(rec, levels=None, logger=None, config_id=9)


async def _collect(gen, n: int, *, timeout: float = 2.0) -> list[dict]:
    out: list[dict] = []

    async def _run() -> None:
        async for ev in gen:
            out.append(ev)
            if len(out) >= n:
                break

    await asyncio.wait_for(_run(), timeout)
    await gen.aclose()
    return out


async def test_publish_delivers_log_event() -> None:
    log_bus.bind_loop()
    gen = sse_event_stream(
        is_disconnected=lambda: _false(),
        levels=None,
        logger=None,
        config_id=None,
    )
    # Prime the subscription (first iteration enters the async-with + queue.get).
    task = asyncio.ensure_future(_collect(gen, 1))
    await asyncio.sleep(0.05)
    log_bus.publish({"id": 1, "level": "INFO", "logger": "app.x", "message": "hi"})
    events = await task
    assert events[0]["event"] == "log"
    assert json.loads(events[0]["data"])["message"] == "hi"


async def test_filter_excludes_nonmatching() -> None:
    log_bus.bind_loop()
    gen = sse_event_stream(
        is_disconnected=lambda: _false(),
        levels=["ERROR"],
        logger=None,
        config_id=None,
    )
    task = asyncio.ensure_future(_collect(gen, 1))
    await asyncio.sleep(0.05)
    log_bus.publish({"id": 2, "level": "INFO", "logger": "app.x", "message": "drop"})
    log_bus.publish({"id": 3, "level": "ERROR", "logger": "app.x", "message": "keep"})
    events = await task
    assert json.loads(events[0]["data"])["message"] == "keep"


async def test_heartbeat_emitted_on_idle() -> None:
    log_bus.bind_loop()
    gen = sse_event_stream(
        is_disconnected=lambda: _false(),
        levels=None,
        logger=None,
        config_id=None,
        heartbeat=0.05,
    )
    events = await _collect(gen, 1)
    assert events[0]["event"] == "ping"


async def test_disconnect_stops_stream() -> None:
    log_bus.bind_loop()
    gen = sse_event_stream(
        is_disconnected=lambda: _true(),
        levels=None,
        logger=None,
        config_id=None,
    )
    events = [ev async for ev in gen]
    assert events == []  # disconnected before first yield


async def test_stream_requires_auth(client: AsyncClient) -> None:
    async with client.stream("GET", "/api/logs/stream") as resp:
        assert resp.status_code == 401


async def _false() -> bool:
    return False


async def _true() -> bool:
    return True
