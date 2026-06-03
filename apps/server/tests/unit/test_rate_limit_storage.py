"""Rate-limit storage backend selection (task 8.4, PRD §7.7.3).

The login limiter uses an in-memory store by default and switches to Redis when
``REDIS_URL`` is set. These tests cover the selection logic and exercise a
Redis-backed limiter counter via fakeredis (no live Redis needed).
"""

from __future__ import annotations

from unittest.mock import patch

import fakeredis
import pytest
import redis
from limits import parse
from limits.storage import MemoryStorage, RedisStorage, storage_from_string
from limits.strategies import FixedWindowRateLimiter

from app.api.ratelimit import (
    BLOCK_DURATION_SEC,
    FailureTracker,
    rate_limit_storage_uri,
)
from app.config import Settings


# --- storage URI selection -------------------------------------------------


def test_uri_defaults_to_memory_when_redis_unset(monkeypatch):
    monkeypatch.setattr(
        "app.api.ratelimit.get_settings", lambda: Settings(_env_file=None, redis_url="")
    )
    assert rate_limit_storage_uri() == "memory://"


def test_uri_uses_redis_when_set(monkeypatch):
    monkeypatch.setattr(
        "app.api.ratelimit.get_settings",
        lambda: Settings(_env_file=None, redis_url="redis://cache:6379/0"),
    )
    assert rate_limit_storage_uri() == "redis://cache:6379/0"


def test_uri_blank_redis_falls_back_to_memory():
    assert rate_limit_storage_uri("   ") == "memory://"


def test_explicit_arg_overrides_settings():
    assert rate_limit_storage_uri("redis://x:6379") == "redis://x:6379"


# --- backend wiring --------------------------------------------------------


def test_memory_uri_builds_memory_storage():
    assert isinstance(storage_from_string(rate_limit_storage_uri("")), MemoryStorage)


def test_redis_uri_builds_redis_storage_with_counter(monkeypatch):
    # Back the RedisStorage with fakeredis so the real limits code path runs
    # (Lua incr/expire) without a live server.
    fake = fakeredis.FakeStrictRedis()
    monkeypatch.setattr(redis.Redis, "from_url", lambda *a, **k: fake)

    storage = storage_from_string(rate_limit_storage_uri("redis://localhost:6379/0"))
    assert isinstance(storage, RedisStorage)

    limiter = FixedWindowRateLimiter(storage)
    item = parse("3/minute")
    results = [limiter.hit(item, "1.2.3.4") for _ in range(4)]
    # 3 allowed within the window, the 4th rejected.
    assert results == [True, True, True, False]


# --- in-memory IP block counter (unchanged behavior, regression) ----------


def test_failure_tracker_blocks_after_threshold():
    clock = {"t": 0.0}
    import app.api.ratelimit as rl

    orig_now = rl._now
    rl._now = lambda: clock["t"]
    try:
        tracker = FailureTracker()
        for _ in range(10):
            tracker.record_failure("9.9.9.9")
        with pytest.raises(Exception) as exc:
            tracker.check_blocked("9.9.9.9")
        assert "rate_limited" in str(exc.value) or exc.value.code == "rate_limited"

        # Block expires after the window.
        clock["t"] += BLOCK_DURATION_SEC + 1
        tracker.check_blocked("9.9.9.9")  # no raise
    finally:
        rl._now = orig_now


def test_failure_tracker_resets_on_success():
    tracker = FailureTracker()
    for _ in range(5):
        tracker.record_failure("8.8.8.8")
    tracker.record_success("8.8.8.8")
    # Counter cleared → fewer than threshold, no block.
    tracker.check_blocked("8.8.8.8")
