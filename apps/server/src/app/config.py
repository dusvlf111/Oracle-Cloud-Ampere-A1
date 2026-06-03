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

    # Security
    app_secret: str = ""
    app_username: str = "admin"
    app_password_hash: str = ""
    cors_origins: str = "http://localhost:3000"

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
