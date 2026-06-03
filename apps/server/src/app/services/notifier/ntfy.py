"""ntfy sender — self-hosted server supported (PRD §7.5.1, §7.5.5).

POST ``{server_url}/{topic}`` with a plain-text body and the ntfy headers:
``Title`` / ``Priority`` / ``Tags`` / optional ``Authorization: Bearer``.
"""

from __future__ import annotations

import httpx

from app.services.notifier.types import NotificationPayload

TIMEOUT = 5.0

PRIORITY_BY_KIND = {
    "success": 5,
    "warning": 4,
    "error": 4,
    "info": 3,
}


def _header_value(value: str) -> str | bytes:
    """HTTP headers are latin-1; send UTF-8 bytes when the value isn't ASCII.

    ntfy decodes header bytes as UTF-8, so a Korean title survives the round
    trip while httpx (which rejects non-ASCII str headers) stays happy.
    """
    try:
        value.encode("ascii")
        return value
    except UnicodeEncodeError:
        return value.encode("utf-8")


async def send(cfg: dict, payload: NotificationPayload) -> None:
    priority = cfg.get("priority") or PRIORITY_BY_KIND.get(payload.kind.value, 3)
    headers: dict[str, str | bytes] = {
        "Title": _header_value(payload.title),
        "Priority": str(priority),
    }
    tags = list(payload.tags) + list(cfg.get("tags", []))
    if tags:
        headers["Tags"] = _header_value(",".join(tags))
    if token := cfg.get("token"):
        headers["Authorization"] = f"Bearer {token}"

    url = f"{cfg['server_url'].rstrip('/')}/{cfg['topic']}"
    async with httpx.AsyncClient(timeout=TIMEOUT) as client:
        resp = await client.post(
            url, content=payload.body.encode("utf-8"), headers=headers
        )
        resp.raise_for_status()
