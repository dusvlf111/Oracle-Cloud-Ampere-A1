"""Settings load from environment."""

from __future__ import annotations

import pytest

from app.config import Settings


def test_defaults() -> None:
    s = Settings(_env_file=None)
    assert s.app_username == "admin"
    assert s.oci_max_concurrent == 10
    assert s.oci_per_credential_max == 1
    assert s.log_level == "INFO"


def test_env_override(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("APP_USERNAME", "operator")
    monkeypatch.setenv("OCI_MAX_CONCURRENT", "42")
    monkeypatch.setenv("CORS_ORIGINS", "http://a.test, http://b.test")
    s = Settings(_env_file=None)
    assert s.app_username == "operator"
    assert s.oci_max_concurrent == 42
    assert s.cors_origin_list == ["http://a.test", "http://b.test"]
