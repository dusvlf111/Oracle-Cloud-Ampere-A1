"""Settings load from a `.env` file + cli hash regression (task 8.1).

Verifies the operational `.env` contract: an explicit env-file path overrides
defaults, and the bootstrap `cli hash` command still emits a verifiable
Argon2id hash (manual-recovery helper). Admin credentials are no longer
env-based — they live in the AppSetting table.
"""

from __future__ import annotations

from typer.testing import CliRunner

from app.cli import cli
from app.config import Settings
from app.services.auth import verify_password


def test_settings_load_from_env_file(tmp_path) -> None:
    env = tmp_path / ".env"
    env.write_text(
        "\n".join(
            [
                "APP_SECRET=base64secretvalue==",
                "DATABASE_URL=sqlite:///./data/app.db",
                "KEYS_DIR=./data/keys",
                "SESSION_SECURE=true",
                "OCI_MAX_CONCURRENT=7",
            ]
        ),
        encoding="utf-8",
    )
    s = Settings(_env_file=str(env))
    assert s.app_secret == "base64secretvalue=="
    assert s.database_url == "sqlite:///./data/app.db"
    assert s.keys_dir == "./data/keys"
    assert s.session_secure is True
    assert s.oci_max_concurrent == 7


def test_real_env_overrides_env_file(tmp_path, monkeypatch) -> None:
    # Process env must win over the .env file (pydantic-settings precedence).
    env = tmp_path / ".env"
    env.write_text("OCI_MAX_CONCURRENT=3\n", encoding="utf-8")
    monkeypatch.setenv("OCI_MAX_CONCURRENT", "9")
    s = Settings(_env_file=str(env))
    assert s.oci_max_concurrent == 9


def test_cli_hash_emits_verifiable_argon2id_hash() -> None:
    result = CliRunner().invoke(cli, ["hash", "s3cret-pw"])
    assert result.exit_code == 0
    out = result.stdout.strip()
    assert out.startswith("$argon2id$")
    # The emitted hash must verify against the plaintext (round-trip).
    assert verify_password(out, "s3cret-pw") is True
    assert verify_password(out, "wrong") is False
