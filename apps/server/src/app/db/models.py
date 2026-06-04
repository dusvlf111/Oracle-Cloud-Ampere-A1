"""SQLModel table definitions (PRD §6).

The full domain model: ``OciCredential``, ``InstanceConfig``,
``NotificationChannel``, ``ConfigChannelLink`` (m2m), ``Attempt``,
``AppSetting`` plus the logging ``LogEntry`` (landed in Push 3).

SQLModel classes double as DB tables and Pydantic response schemas; create /
update *requests* use dedicated ``*Create`` / ``*Update`` models (see
``app.schemas``) so read-only fields stay protected (PRD §6, §8).
"""

from datetime import datetime

from sqlmodel import Field, Relationship, SQLModel


class ConfigChannelLink(SQLModel, table=True):
    """Many-to-many link between ``InstanceConfig`` and ``NotificationChannel``."""

    config_id: int = Field(foreign_key="instanceconfig.id", primary_key=True)
    channel_id: int = Field(foreign_key="notificationchannel.id", primary_key=True)


class OciCredential(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    tenancy_ocid: str
    user_ocid: str
    fingerprint: str
    region: str  # e.g. "ap-chuncheon-1"
    private_key_path: str  # /data/keys/{id}.pem
    passphrase_enc: str | None = None  # AES-256-GCM encrypted
    created_at: datetime = Field(default_factory=datetime.utcnow)

    configs: list["InstanceConfig"] = Relationship(back_populates="credential")


class InstanceConfig(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    credential_id: int = Field(foreign_key="ocicredential.id")
    enabled: bool = True

    shape: str = "VM.Standard.A1.Flex"
    ocpus: int = 4
    memory_gb: int = 24
    boot_volume_gb: int = 50
    image_ocid: str
    subnet_ocid: str
    availability_domain: str
    ssh_public_key: str

    retry_interval_sec: int = 60
    max_attempts: int | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    credential: OciCredential = Relationship(back_populates="configs")
    attempts: list["Attempt"] = Relationship(
        back_populates="config",
        sa_relationship_kwargs={"cascade": "all, delete-orphan"},
    )
    notification_channels: list["NotificationChannel"] = Relationship(
        back_populates="configs",
        link_model=ConfigChannelLink,
    )


class NotificationChannel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    type: str = Field(index=True)  # "discord" | "slack" | "telegram" | "ntfy"
    enabled: bool = True
    config_enc: str  # AES-256-GCM encrypted JSON (channel-specific config)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    configs: list[InstanceConfig] = Relationship(
        back_populates="notification_channels",
        link_model=ConfigChannelLink,
    )


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    config_id: int = Field(foreign_key="instanceconfig.id", index=True)
    attempted_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    # "success" | "out_of_capacity" | "rate_limited" | "auth_error"
    #          | "config_error" | "other_error"
    status: str
    message: str | None = None
    instance_ocid: str | None = None
    duration_ms: int | None = None

    config: InstanceConfig = Relationship(back_populates="attempts")


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class LogEntry(SQLModel, table=True):
    """Structured, persisted log record (PRD §6, §9.3).

    Doubles as the FastAPI read schema. ``DbLogHandler`` populates it by
    extracting the predefined context keys (``config_id``/``attempt_id``/
    ``credential_id``) from ``record.__dict__``; anything else lands in
    ``extra`` as a JSON string. ``exc_info`` carries the formatted traceback
    for ERROR/CRITICAL records.
    """

    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    level: str = Field(index=True)
    logger: str = Field(index=True)
    message: str
    config_id: int | None = Field(default=None, index=True)
    attempt_id: int | None = None
    credential_id: int | None = None
    extra: str | None = None
    exc_info: str | None = None


# Re-export the shared metadata for Alembic's target_metadata.
metadata = SQLModel.metadata
