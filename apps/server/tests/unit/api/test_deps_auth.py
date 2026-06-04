"""require_login / require_admin guard unit tests (PRD §6.3, task 9.3).

Exercises the dependency functions directly with a fake Request so we can drive
the session dict (incl. the legacy ``user``-only shape) without a signed cookie.
"""

from __future__ import annotations

from types import SimpleNamespace

import pytest
from sqlmodel import Session

from app.api.deps import AppError, require_admin, require_login
from app.services import auth as auth_service


def _fake_request(session_data: dict | None) -> SimpleNamespace:
    scope = {"session": session_data} if session_data is not None else {}
    return SimpleNamespace(scope=scope, session=session_data or {})


def _seed_admin(session: Session) -> object:
    return auth_service.register_user(session, "admin", "admin-pw-123")


def test_require_login_resolves_user_id(session: Session) -> None:
    admin = _seed_admin(session)
    req = _fake_request({"user_id": admin.id, "role": "admin"})
    user = require_login(req, session)
    assert user.id == admin.id
    assert user.role == "admin"


def test_require_login_legacy_username_only(session: Session) -> None:
    """Pre-Push-9 session carrying only ``user`` (username) still resolves."""
    admin = _seed_admin(session)
    req = _fake_request({"user": admin.username})
    user = require_login(req, session)
    assert user.id == admin.id


def test_require_login_no_session_401(session: Session) -> None:
    req = _fake_request(None)
    with pytest.raises(AppError) as exc:
        require_login(req, session)
    assert exc.value.status_code == 401


def test_require_login_missing_user_401(session: Session) -> None:
    _seed_admin(session)
    req = _fake_request({"user_id": 9999})
    with pytest.raises(AppError) as exc:
        require_login(req, session)
    assert exc.value.status_code == 401


def test_require_login_disabled_user_revoked_401(session: Session) -> None:
    """A session whose user was disabled afterward is rejected (re-login)."""
    admin = _seed_admin(session)
    member = auth_service.register_user(session, "member", "member-pw-123")
    member.status = auth_service.STATUS_DISABLED
    session.add(member)
    session.commit()

    req = _fake_request({"user_id": member.id})
    with pytest.raises(AppError) as exc:
        require_login(req, session)
    assert exc.value.status_code == 401
    # Sanity: the admin is still fine.
    assert require_login(_fake_request({"user_id": admin.id}), session).id == admin.id


def test_require_admin_allows_admin(session: Session) -> None:
    admin = _seed_admin(session)
    assert require_admin(admin).id == admin.id


def test_require_admin_rejects_user_403(session: Session) -> None:
    _seed_admin(session)
    member = auth_service.register_user(session, "member", "member-pw-123")
    member.status = auth_service.STATUS_ACTIVE
    session.add(member)
    session.commit()
    with pytest.raises(AppError) as exc:
        require_admin(member)
    assert exc.value.status_code == 403
    assert exc.value.code == "forbidden"
