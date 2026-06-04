"""argon2 auth service + User-table-backed registration/authentication.

Push 9 migrated the single-admin AppSetting pair to the ``User`` table:
``register_user`` makes the first signup an active admin and the rest pending
users; ``authenticate`` returns the ``User`` row (status-checked by the caller).
"""

from __future__ import annotations

from typer.testing import CliRunner

from app.cli import cli
from app.services import auth


def test_hash_verify_roundtrip() -> None:
    h = auth.hash_password("s3cret-pw")
    assert h.startswith("$argon2id$")
    assert auth.verify_password(h, "s3cret-pw") is True


def test_verify_rejects_wrong_password() -> None:
    h = auth.hash_password("correct-horse")
    assert auth.verify_password(h, "battery-staple") is False


def test_verify_rejects_garbage_hash() -> None:
    assert auth.verify_password("not-a-hash", "anything") is False


def test_admin_exists_false_then_true(session) -> None:
    assert auth.admin_exists(session) is False
    auth.register_user(session, "admin", "admin-pw-123")
    assert auth.admin_exists(session) is True


def test_first_user_is_active_admin(session) -> None:
    user = auth.register_user(session, "admin", "admin-pw-123")
    assert user.role == auth.ROLE_ADMIN
    assert user.status == auth.STATUS_ACTIVE
    assert user.approved_at is not None
    assert user.password_hash.startswith("$argon2id$")


def test_second_user_is_pending(session) -> None:
    auth.register_user(session, "admin", "admin-pw-123")
    member = auth.register_user(session, "member", "member-pw-123")
    assert member.role == auth.ROLE_USER
    assert member.status == auth.STATUS_PENDING
    assert member.approved_at is None


def test_register_duplicate_raises(session) -> None:
    import pytest

    auth.register_user(session, "dup", "pw-123456")
    with pytest.raises(ValueError, match="username_taken"):
        auth.register_user(session, "dup", "another-pw")


def test_authenticate_success_returns_user(session) -> None:
    auth.register_user(session, "admin", "admin-pw-123")
    user = auth.authenticate(session, "admin", "admin-pw-123")
    assert user is not None
    assert user.username == "admin"


def test_authenticate_wrong_password(session) -> None:
    auth.register_user(session, "admin", "admin-pw-123")
    assert auth.authenticate(session, "admin", "wrong") is None


def test_authenticate_wrong_username(session) -> None:
    auth.register_user(session, "admin", "admin-pw-123")
    assert auth.authenticate(session, "root", "admin-pw-123") is None


def test_authenticate_no_user_configured(session) -> None:
    assert auth.authenticate(session, "admin", "anything") is None


def test_active_admin_count(session) -> None:
    assert auth.active_admin_count(session) == 0
    auth.register_user(session, "admin", "admin-pw-123")
    assert auth.active_admin_count(session) == 1
    # Pending user does not count.
    auth.register_user(session, "member", "member-pw-123")
    assert auth.active_admin_count(session) == 1


def test_cli_hash_outputs_argon2id() -> None:
    result = CliRunner().invoke(cli, ["hash", "my-password"])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert out.startswith("$argon2id$")
    # Output is a usable, verifiable hash.
    assert auth.verify_password(out, "my-password") is True
