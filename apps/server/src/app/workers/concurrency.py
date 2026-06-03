"""Worker concurrency guards (PRD §7.3.1, §9.2).

Two layers of back-pressure protect the OCI API:

- a **global** semaphore (``OCI_MAX_CONCURRENT``, default 10) caps the total
  number of in-flight ``launch_instance`` calls across every account;
- a **per-credential** semaphore (``OCI_PER_CREDENTIAL_MAX``, default 1)
  serialises calls for a single OCI tenancy so the same account never hammers
  the API in parallel — while *different* accounts still run concurrently.

Both live process-wide and are created lazily. They must be acquired in a
fixed order (global → per-credential) to avoid deadlock; :func:`oci_slots`
encapsulates that.
"""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from collections.abc import AsyncIterator

from app.config import get_settings

_global_sem: asyncio.Semaphore | None = None
_credential_sems: dict[int, asyncio.Semaphore] = {}


def reset_semaphores() -> None:
    """Drop cached semaphores (test isolation / settings reload)."""
    global _global_sem
    _global_sem = None
    _credential_sems.clear()


def global_semaphore() -> asyncio.Semaphore:
    global _global_sem
    if _global_sem is None:
        _global_sem = asyncio.Semaphore(get_settings().oci_max_concurrent)
    return _global_sem


def credential_semaphore(credential_id: int) -> asyncio.Semaphore:
    sem = _credential_sems.get(credential_id)
    if sem is None:
        sem = asyncio.Semaphore(get_settings().oci_per_credential_max)
        _credential_sems[credential_id] = sem
    return sem


@asynccontextmanager
async def oci_slots(credential_id: int) -> AsyncIterator[None]:
    """Acquire the global then the per-credential slot (ordered, deadlock-free)."""
    async with global_semaphore():
        async with credential_semaphore(credential_id):
            yield
