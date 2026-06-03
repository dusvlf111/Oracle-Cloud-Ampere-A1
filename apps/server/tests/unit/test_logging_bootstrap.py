"""Logging bootstrap + lifespan smoke tests (PRD §9.3.1)."""

from __future__ import annotations

import logging
from collections.abc import Iterator

import pytest

from app.log_bus import LogBusHandler, attach_log_bus
from app.logging_config import DbLogHandler, JsonFormatter, configure_logging


@pytest.fixture
def _restore_root_handlers() -> Iterator[None]:
    """Snapshot/restore root logger handlers so bootstrap tests don't leak."""
    root = logging.getLogger()
    saved = list(root.handlers)
    saved_level = root.level
    try:
        yield
    finally:
        root.handlers[:] = saved
        root.setLevel(saved_level)


def test_configure_logging_is_idempotent(engine, _restore_root_handlers) -> None:
    root = logging.getLogger()
    configure_logging(engine=engine)
    configure_logging(engine=engine)  # second call must not duplicate handlers
    managed = [h for h in root.handlers if getattr(h, "_app_managed", False)]
    json_handlers = [
        h for h in managed if isinstance(getattr(h, "formatter", None), JsonFormatter)
    ]
    db_handlers = [h for h in managed if isinstance(h, DbLogHandler)]
    assert len(json_handlers) == 1
    assert len(db_handlers) == 1


def test_configure_logging_quiets_noisy_libraries(
    engine, _restore_root_handlers
) -> None:
    configure_logging(engine=engine)
    assert logging.getLogger("sqlalchemy.engine").level == logging.WARNING
    assert logging.getLogger("uvicorn.access").level == logging.WARNING


def test_attach_log_bus_installs_three_sinks(engine, _restore_root_handlers) -> None:
    """configure_logging + attach_log_bus = stdout JSON + DB + bus handlers."""
    configure_logging(engine=engine)
    attach_log_bus()
    managed = [
        h for h in logging.getLogger().handlers if getattr(h, "_app_managed", False)
    ]
    assert any(isinstance(h, DbLogHandler) for h in managed)
    assert any(isinstance(h, LogBusHandler) for h in managed)
    assert any(
        isinstance(getattr(h, "formatter", None), JsonFormatter) for h in managed
    )
