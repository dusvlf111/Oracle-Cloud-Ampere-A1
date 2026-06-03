"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

import app.db.models as _models  # noqa: F401  (register tables on metadata)
from app.config import Settings
from app.db.session import create_db_engine
from app.main import app
from app.services import auth as _auth

# Known single-admin pair used across auth tests.
TEST_USERNAME = "admin"
TEST_PASSWORD = "test-admin-pw"


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_settings(monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Configure the single-admin credentials for auth tests (call-time)."""
    settings = Settings(
        app_username=TEST_USERNAME,
        app_password_hash=_auth.hash_password(TEST_PASSWORD),
        app_secret="x" * 32,
    )
    monkeypatch.setattr("app.services.auth.get_settings", lambda: settings)
    return settings


@pytest_asyncio.fixture
async def authed_client(admin_settings: Settings) -> AsyncClient:
    """AsyncClient that has logged in and carries the session cookie."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        yield ac


@pytest.fixture
def engine():
    # Shared in-memory DB across connections within the test.
    eng = create_db_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    try:
        yield eng
    finally:
        SQLModel.metadata.drop_all(eng)
        eng.dispose()


@pytest.fixture
def session(engine) -> Iterator[Session]:
    with Session(engine) as s:
        yield s
