"""Shared pytest fixtures."""

from __future__ import annotations

from collections.abc import Iterator

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy.pool import StaticPool
from sqlmodel import Session, SQLModel

import app.db.models as _models  # noqa: F401  (register tables on metadata)
from app.db.session import create_db_engine
from app.main import app
from app.services import auth as _auth

# Known single-admin pair used across auth tests. Password is >= 8 chars so it
# also satisfies the setup-flow validation rules.
TEST_USERNAME = "admin"
TEST_PASSWORD = "test-admin-pw"


@pytest.fixture(autouse=True)
def _reset_rate_limit() -> Iterator[None]:
    """Isolate slowapi storage + failure tracker between tests."""
    from app.api.ratelimit import failure_tracker, limiter

    limiter.reset()
    failure_tracker.reset()
    yield
    limiter.reset()
    failure_tracker.reset()


@pytest_asyncio.fixture
async def client() -> AsyncClient:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        yield ac


@pytest.fixture
def admin_settings(engine, db_app):
    """Seed the bootstrap admin User in the test DB (DB-based auth, Push 9).

    Activates the in-memory ``get_session`` override (via ``db_app``) and
    persists an active admin so ``/api/auth/login`` succeeds. Returns the admin
    ``User`` so ownership-scope tests can reference its id.
    """
    from app.db.models import User

    with Session(engine) as s:
        admin = _auth.register_user(s, TEST_USERNAME, TEST_PASSWORD)
        # Detach a simple record the caller can read post-commit.
        return User(
            id=admin.id,
            username=admin.username,
            password_hash=admin.password_hash,
            role=admin.role,
            status=admin.status,
        )


@pytest_asyncio.fixture
async def authed_client(admin_settings) -> AsyncClient:
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


@pytest.fixture
def db_app(engine) -> Iterator[None]:
    """Point the app's ``get_session`` dependency at the in-memory test engine."""
    from app.db.session import get_session as real_get_session

    def _override() -> Iterator[Session]:
        with Session(engine) as s:
            yield s

    app.dependency_overrides[real_get_session] = _override
    try:
        yield
    finally:
        app.dependency_overrides.pop(real_get_session, None)


@pytest.fixture
def oci_mock(monkeypatch: pytest.MonkeyPatch):
    """Patch ``oci.identity.IdentityClient`` used by the OCI client service.

    Returns the MagicMock class so tests can configure
    ``oci_mock.return_value.list_availability_domains.side_effect`` etc.
    Never lets a real OCI call escape.
    """
    from unittest.mock import MagicMock

    import app.services.oci_client as oci_client

    client_cls = MagicMock(name="IdentityClient")
    client_cls.return_value.list_availability_domains.return_value = MagicMock(
        data=["AD-1", "AD-2", "AD-3"]
    )
    monkeypatch.setattr(oci_client.oci.identity, "IdentityClient", client_cls)
    return client_cls


@pytest_asyncio.fixture
async def authed_db_client(admin_settings) -> AsyncClient:
    """Logged-in AsyncClient whose log routes hit the in-memory test DB."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as ac:
        resp = await ac.post(
            "/api/auth/login",
            json={"username": TEST_USERNAME, "password": TEST_PASSWORD},
        )
        assert resp.status_code == 200, resp.text
        yield ac


@pytest.fixture
def make_user(engine):
    """Factory: create an active (default) ``User`` and return its id.

    Used by ownership-scope / user-management tests to seed multiple accounts.
    """
    from app.db.models import User
    from app.services.auth import hash_password

    def _make(
        username: str,
        password: str = "user-pass-123",
        *,
        role: str = "user",
        status: str = "active",
    ) -> int:
        with Session(engine) as s:
            u = User(
                username=username,
                password_hash=hash_password(password),
                role=role,
                status=status,
            )
            s.add(u)
            s.commit()
            s.refresh(u)
            return u.id

    return _make


@pytest_asyncio.fixture
async def login_as():
    """Factory: return a logged-in AsyncClient for the given credentials.

    The caller is responsible for having seeded an active user (e.g. via
    ``make_user``). The returned clients share the in-memory app/DB override.
    """
    clients: list[AsyncClient] = []

    async def _login(username: str, password: str = "user-pass-123") -> AsyncClient:
        transport = ASGITransport(app=app)
        ac = AsyncClient(transport=transport, base_url="http://test")
        resp = await ac.post(
            "/api/auth/login", json={"username": username, "password": password}
        )
        assert resp.status_code == 200, resp.text
        clients.append(ac)
        return ac

    yield _login
    for ac in clients:
        await ac.aclose()
