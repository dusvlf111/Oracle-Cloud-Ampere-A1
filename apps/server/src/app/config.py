"""Application settings (pydantic-settings).

Loads from environment / .env. See PRD §10 for the full env contract.
"""

from __future__ import annotations

from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "sqlite:////data/app.db"
    # Connection pool tuning — only applied to non-SQLite (e.g. PostgreSQL)
    # engines; SQLite uses its own connect_args/WAL path (PRD §9.2, §10).
    db_pool_size: int = 5
    db_max_overflow: int = 10
    db_pool_pre_ping: bool = True

    # Filesystem — OCI private keys stored here, chmod 600 (PRD §7.1, §9.1).
    keys_dir: str = "/data/keys"

    # Security — APP_SECRET signs the session cookie and derives the AES-256-GCM
    # key (required). Admin credentials are NOT env-based: they live in the
    # AppSetting table (admin_username / admin_password_hash), created via the
    # first-signup flow (POST /api/auth/setup). See PRD §7.7.
    app_secret: str = ""
    cors_origins: str = "http://localhost:3000"
    # Session cookie Secure flag — enable in production (HTTPS). PRD §7.7.2.
    session_secure: bool = False

    # Rate-limit storage — empty = in-memory (default). Set to a redis URL
    # (e.g. redis://redis:6379/0) to share the login limiter across processes
    # (task 8.4, PRD §7.7.3).
    redis_url: str = ""

    # Concurrency
    oci_max_concurrent: int = 10
    oci_per_credential_max: int = 1

    # Logging
    log_level: str = "INFO"
    log_level_db: str | None = None
    log_retention_days: int = 7
    log_retention_rows: int = 10000

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
