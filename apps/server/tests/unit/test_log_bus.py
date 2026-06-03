"""LogBus + LogBusHandler tests (PRD §9.3.6)."""

from __future__ import annotations

import asyncio
import logging

import pytest

from app.log_bus import QUEUE_MAXSIZE, LogBus, LogBusHandler, record_to_dict


def _record(msg: str = "hi", **extra) -> logging.LogRecord:
    rec = logging.LogRecord(
        name="app.workers.poller",
        level=logging.INFO,
        pathname=__file__,
        lineno=1,
        msg=msg,
        args=(),
        exc_info=None,
    )
    for k, v in extra.items():
        setattr(rec, k, v)
    return rec


async def test_subscriber_receives_published_record() -> None:
    bus = LogBus()
    bus.bind_loop()
    async with bus.subscribe() as q:
        bus.publish({"level": "INFO", "message": "x"})
        rec = await asyncio.wait_for(q.get(), timeout=1)
        assert rec["message"] == "x"


async def test_multiple_subscribers_all_receive() -> None:
    bus = LogBus()
    bus.bind_loop()
    async with bus.subscribe() as q1, bus.subscribe() as q2:
        bus.publish({"id": 1})
        assert (await asyncio.wait_for(q1.get(), 1))["id"] == 1
        assert (await asyncio.wait_for(q2.get(), 1))["id"] == 1


async def test_full_queue_drops_without_error() -> None:
    bus = LogBus()
    bus.bind_loop()
    async with bus.subscribe() as q:
        for i in range(QUEUE_MAXSIZE + 50):
            bus.publish({"id": i})  # extra publishes must not raise
        assert q.qsize() == QUEUE_MAXSIZE
        first = await q.get()
        assert first["id"] == 0  # oldest kept, overflow dropped


async def test_no_delivery_after_unsubscribe() -> None:
    bus = LogBus()
    bus.bind_loop()
    async with bus.subscribe() as q:
        pass  # context exit unsubscribes
    assert bus.subscriber_count == 0
    bus.publish({"id": 99})  # nobody listening
    assert q.empty()


def test_record_to_dict_shape() -> None:
    out = record_to_dict(_record(msg="boot", config_id=5, region="seoul"))
    assert out["message"] == "boot"
    assert out["config_id"] == 5
    assert out["attempt_id"] is None
    assert out["extra"] == {"region": "seoul"}
    assert out["exc_info"] is None
    assert out["timestamp"].endswith("Z")


async def test_handler_publishes_to_bus() -> None:
    bus = LogBus()
    bus.bind_loop()
    handler = LogBusHandler(bus=bus)
    async with bus.subscribe() as q:
        handler.emit(_record(msg="via handler", config_id=7))
        rec = await asyncio.wait_for(q.get(), 1)
        assert rec["message"] == "via handler"
        assert rec["config_id"] == 7


async def test_handler_drops_recursive_loggers() -> None:
    bus = LogBus()
    bus.bind_loop()
    handler = LogBusHandler(bus=bus)
    rec = logging.LogRecord("sqlalchemy.engine", logging.INFO, __file__, 1,
                            "SELECT 1", (), None)
    # Mimic the root logger applying handler filters before emit.
    if all(f.filter(rec) for f in handler.filters):
        handler.emit(rec)
    async with bus.subscribe() as q:
        await asyncio.sleep(0)
        assert q.empty()
