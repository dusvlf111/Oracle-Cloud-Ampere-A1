"""In-memory pub/sub for live log streaming (PRD §9.3.6).

``LogBusHandler.emit()`` (a synchronous logging handler) calls
:meth:`LogBus.publish`, which fans each record dict out to every subscriber's
bounded :class:`asyncio.Queue`. The SSE endpoint (Task 3.5) consumes a queue
via :meth:`LogBus.subscribe`.

Slow subscribers exert no back-pressure on the logging path: a full queue
simply drops the record (``QueueFull`` is swallowed). Because ``emit`` may run
off the event loop (worker threads, sync request handlers), publish is
scheduled onto the bound loop thread-safely when one is captured.
"""

from __future__ import annotations

import asyncio
import logging
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.logging_config import (
    JsonFormatter,
    NoRecursionFilter,
    _extract_context,
    _iso,
)

QUEUE_MAXSIZE = 500


class LogBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict]] = set()
        self._loop: asyncio.AbstractEventLoop | None = None

    def bind_loop(self, loop: asyncio.AbstractEventLoop | None = None) -> None:
        """Remember the event loop publish should marshal onto (app startup)."""
        self._loop = loop or asyncio.get_running_loop()

    def _deliver(self, record: dict) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(record)
            except asyncio.QueueFull:
                pass  # drop for slow subscribers (back-pressure relief)

    def publish(self, record: dict) -> None:
        """Fan a record dict out to all subscribers (loop-safe)."""
        loop = self._loop
        if loop is not None and not loop.is_closed():
            try:
                running = asyncio.get_running_loop()
            except RuntimeError:
                running = None
            if running is loop:
                self._deliver(record)
            else:
                loop.call_soon_threadsafe(self._deliver, record)
        else:
            # No bound loop (tests / pre-startup): best-effort direct delivery.
            self._deliver(record)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict]]:
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=QUEUE_MAXSIZE)
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)

    @property
    def subscriber_count(self) -> int:
        return len(self._subscribers)


log_bus = LogBus()


def record_to_dict(record: logging.LogRecord) -> dict:
    """Serialise a LogRecord into the dict shape published on the bus / SSE."""
    context, extra = _extract_context(record)
    payload: dict = {
        "timestamp": _iso(record.created),
        "level": record.levelname,
        "logger": record.name,
        "message": record.getMessage(),
    }
    for key, value in context.items():
        payload[key] = value
    payload["extra"] = extra or None
    if record.exc_info:
        payload["exc_info"] = JsonFormatter().formatException(record.exc_info)
    else:
        payload["exc_info"] = None
    return payload


class LogBusHandler(logging.Handler):
    """Logging handler that publishes each record onto :data:`log_bus`."""

    def __init__(self, bus: LogBus = log_bus, level: int = logging.INFO) -> None:
        super().__init__(level=level)
        self._bus = bus
        self.addFilter(NoRecursionFilter())

    def emit(self, record: logging.LogRecord) -> None:
        try:
            self._bus.publish(record_to_dict(record))
        except Exception:  # noqa: BLE001 — never break the app
            self.handleError(record)


def attach_log_bus(level: int = logging.INFO) -> LogBusHandler:
    """Attach a :class:`LogBusHandler` to the root logger (idempotent)."""
    root = logging.getLogger()
    for h in list(root.handlers):
        if isinstance(h, LogBusHandler):
            root.removeHandler(h)
    handler = LogBusHandler(level=level)
    handler._app_managed = True  # type: ignore[attr-defined]
    root.addHandler(handler)
    return handler
