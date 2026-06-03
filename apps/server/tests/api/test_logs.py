"""GET/DELETE /api/logs tests (PRD §8)."""

from __future__ import annotations

from datetime import datetime, timedelta

import pytest
from httpx import AsyncClient
from sqlmodel import Session

from app.db.models import LogEntry

BASE = datetime(2026, 6, 3, 12, 0, 0)


@pytest.fixture
def seed_logs(session: Session) -> list[LogEntry]:
    rows = []
    specs = [
        ("INFO", "app.workers.poller", "poll start", 1),
        ("WARNING", "app.api.auth", "login ok for auth", 1),
        ("ERROR", "app.workers.config_task", "auth error", 2),
        ("INFO", "app.workers.poller", "poll done", 2),
        ("ERROR", "app.services.oci_client", "launch failed", None),
    ]
    for i, (level, logger, msg, cfg) in enumerate(specs):
        e = LogEntry(
            timestamp=BASE + timedelta(minutes=i),
            level=level,
            logger=logger,
            message=msg,
            config_id=cfg,
        )
        session.add(e)
        rows.append(e)
    session.commit()
    for e in rows:
        session.refresh(e)
    return rows


async def test_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/logs")
    assert resp.status_code == 401


async def test_list_returns_newest_first(
    authed_db_client: AsyncClient, seed_logs
) -> None:
    resp = await authed_db_client.get("/api/logs")
    assert resp.status_code == 200
    body = resp.json()
    assert len(body["items"]) == 5
    ids = [item["id"] for item in body["items"]]
    assert ids == sorted(ids, reverse=True)
    assert body["has_more"] is False
    assert body["next_cursor"] is None


async def test_filter_by_levels_multi(
    authed_db_client: AsyncClient, seed_logs
) -> None:
    resp = await authed_db_client.get("/api/logs?levels=ERROR&levels=WARNING")
    items = resp.json()["items"]
    assert {i["level"] for i in items} == {"ERROR", "WARNING"}
    assert len(items) == 3


async def test_filter_by_logger_prefix_and_config(
    authed_db_client: AsyncClient, seed_logs
) -> None:
    resp = await authed_db_client.get("/api/logs?logger=app.workers")
    assert all(i["logger"].startswith("app.workers") for i in resp.json()["items"])

    resp2 = await authed_db_client.get("/api/logs?config_id=2")
    assert {i["config_id"] for i in resp2.json()["items"]} == {2}


async def test_search_q_substring(
    authed_db_client: AsyncClient, seed_logs
) -> None:
    resp = await authed_db_client.get("/api/logs?q=auth")
    msgs = [i["message"] for i in resp.json()["items"]]
    assert msgs == ["auth error", "login ok for auth"]  # newest first


async def test_cursor_pagination_walks_all(
    authed_db_client: AsyncClient, seed_logs
) -> None:
    seen: list[int] = []
    resp = await authed_db_client.get("/api/logs?limit=2")
    body = resp.json()
    assert body["has_more"] is True
    assert body["next_cursor"] is not None
    seen += [i["id"] for i in body["items"]]

    while body["has_more"]:
        resp = await authed_db_client.get(
            f"/api/logs?limit=2&cursor={body['next_cursor']}"
        )
        body = resp.json()
        seen += [i["id"] for i in body["items"]]

    assert len(seen) == 5
    assert len(set(seen)) == 5  # no duplicates across pages


async def test_delete_before(authed_db_client: AsyncClient, seed_logs) -> None:
    cutoff = (BASE + timedelta(minutes=3)).isoformat()
    resp = await authed_db_client.request("DELETE", f"/api/logs?before={cutoff}")
    assert resp.status_code == 204

    remaining = (await authed_db_client.get("/api/logs")).json()["items"]
    # Only the two records at/after minute 3 survive.
    assert len(remaining) == 2
    assert all(i["timestamp"] >= "2026-06-03T12:03:00" for i in remaining)
