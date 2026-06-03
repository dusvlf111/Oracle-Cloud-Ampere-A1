"""argon2 auth service + DB-backed admin credentials + cli hash helper."""

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
    auth.create_admin(session, "admin", "admin-pw-123")
    assert auth.admin_exists(session) is True
    assert auth.get_admin_username(session) == "admin"


def test_create_admin_stores_argon2_hash(session) -> None:
    auth.create_admin(session, "admin", "admin-pw-123")
    row = session.get(_appsetting_cls(), auth.ADMIN_PASSWORD_HASH_KEY)
    assert row is not None
    assert row.value.startswith("$argon2id$")


def test_authenticate_success(session) -> None:
    auth.create_admin(session, "admin", "admin-pw-123")
    assert auth.authenticate(session, "admin", "admin-pw-123") is True


def test_authenticate_wrong_password(session) -> None:
    auth.create_admin(session, "admin", "admin-pw-123")
    assert auth.authenticate(session, "admin", "wrong") is False


def test_authenticate_wrong_username(session) -> None:
    auth.create_admin(session, "admin", "admin-pw-123")
    assert auth.authenticate(session, "root", "admin-pw-123") is False


def test_authenticate_no_admin_configured(session) -> None:
    assert auth.authenticate(session, "admin", "anything") is False


def test_create_admin_is_idempotent_upsert(session) -> None:
    auth.create_admin(session, "admin", "first-pass-1")
    auth.create_admin(session, "admin2", "second-pass-2")
    assert auth.get_admin_username(session) == "admin2"
    assert auth.authenticate(session, "admin2", "second-pass-2") is True
    assert auth.authenticate(session, "admin", "first-pass-1") is False


def test_cli_hash_outputs_argon2id() -> None:
    result = CliRunner().invoke(cli, ["hash", "my-password"])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert out.startswith("$argon2id$")
    # Output is a usable, verifiable hash.
    assert auth.verify_password(out, "my-password") is True


def _appsetting_cls():
    from app.db.models import AppSetting

    return AppSetting
