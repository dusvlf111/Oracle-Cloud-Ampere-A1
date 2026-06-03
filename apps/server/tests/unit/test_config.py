"""Settings load from environment."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    # Admin credentials are no longer env-based (DB AppSetting only).
    assert not hasattr(s, "app_username")
    assert not hasattr(s, "app_password_hash")
    assert s.oci_max_concurrent == 10
    assert s.oci_per_credential_max == 1
    assert s.log_level == "INFO"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("OCI_MAX_CONCURRENT", "42")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    s = Settings(_env_file=None)
    assert s.oci_max_concurrent == 42
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]
