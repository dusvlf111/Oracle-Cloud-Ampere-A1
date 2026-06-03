"""Brute-force defense for login (PRD §7.7.3).

- slowapi: 5 requests / minute / IP on POST /api/auth/login → 429.
- In-memory tracker: 10 consecutive failures from an IP → 5-minute block.
- Time source is injectable (`_now`) so tests can advance/expire the block.
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field

from fastapi import Request
from slowapi import Limiter
from slowapi.util import get_remote_address

from app.api.deps import AppError

MAX_CONSECUTIVE_FAILURES = 10
BLOCK_DURATION_SEC = 5 * 60
LOGIN_RATE = "5/minute"


def client_key(request: Request) -> str:
    """Stable per-IP key; falls back to a constant for ASGI test transport."""
    return get_remote_address(request) or "testclient"


# slowapi limiter with explicit in-memory storage (SQLite-friendly, no Redis).
limiter = Limiter(
    key_func=client_key,
    storage_uri="memory://",
    default_limits=[],
)


def _now() -> float:
    return time.monotonic()


@dataclass
class _IpState:
    failures: int = 0
    blocked_until: float = 0.0


@dataclass
class FailureTracker:
    """Tracks consecutive login failures per IP and applies temporary blocks."""

    _by_ip: dict[str, _IpState] = field(default_factory=dict)

    def reset(self) -> None:
        self._by_ip.clear()

    def check_blocked(self, ip: str) -> None:
        state = self._by_ip.get(ip)
        if state and state.blocked_until > _now():
            retry = int(state.blocked_until - _now()) + 1
            raise AppError(
                "rate_limited",
                429,
                "Too many failed login attempts; IP temporarily blocked",
                {"retry_after_sec": retry},
            )

    def record_failure(self, ip: str) -> None:
        state = self._by_ip.setdefault(ip, _IpState())
        state.failures += 1
        if state.failures >= MAX_CONSECUTIVE_FAILURES:
            state.blocked_until = _now() + BLOCK_DURATION_SEC

    def record_success(self, ip: str) -> None:
        self._by_ip.pop(ip, None)


failure_tracker = FailureTracker()
