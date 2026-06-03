"""argon2 auth service + cli hash helper (task 2.2)."""

from __future__ import annotations

import pytest
from typer.testing import CliRunner

from app.cli import cli
from app.config import Settings, get_settings
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


@pytest.fixture
def admin_settings(monkeypatch: pytest.MonkeyPatch):
    pw = "admin-pw-123"
    settings = Settings(
        app_username="admin",
        app_password_hash=auth.hash_password(pw),
        app_secret="x" * 32,
    )
    monkeypatch.setattr("app.services.auth.get_settings", lambda: settings)
    get_settings.cache_clear()
    return pw


def test_authenticate_success(admin_settings: str) -> None:
    assert auth.authenticate("admin", admin_settings) is True


def test_authenticate_wrong_password(admin_settings: str) -> None:
    assert auth.authenticate("admin", "wrong") is False


def test_authenticate_wrong_username(admin_settings: str) -> None:
    assert auth.authenticate("root", admin_settings) is False


def test_authenticate_no_hash_configured(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = Settings(app_username="admin", app_password_hash="")
    monkeypatch.setattr("app.services.auth.get_settings", lambda: settings)
    assert auth.authenticate("admin", "anything") is False


def test_cli_hash_outputs_argon2id() -> None:
    result = CliRunner().invoke(cli, ["hash", "my-password"])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert out.startswith("$argon2id$")
    # Output is a usable, verifiable hash.
    assert auth.verify_password(out, "my-password") is True
