"""InstanceConfig schemas (PRD §6, §7.2, §8).

``ConfigCreate`` / ``ConfigUpdate`` protect read-only fields (id, enabled,
timestamps) and carry ``channel_ids`` for the m2m link. ``ConfigRead`` echoes
the full config plus the resolved ``channel_ids``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.db.models import InstanceConfig


class ConfigCreate(BaseModel):
    name: str
    credential_id: int
    shape: str = "VM.Standard.A1.Flex"
    ocpus: int = Field(default=4, ge=1)
    memory_gb: int = Field(default=24, ge=1)
    boot_volume_gb: int = Field(default=50, ge=1)
    image_ocid: str
    subnet_ocid: str
    availability_domain: str
    ssh_public_key: str
    retry_interval_sec: int = Field(default=60, ge=1)
    max_attempts: int | None = None
    channel_ids: list[int] = Field(default_factory=list)


class ConfigUpdate(BaseModel):
    name: str
    credential_id: int
    shape: str
    ocpus: int = Field(ge=1)
    memory_gb: int = Field(ge=1)
    boot_volume_gb: int = Field(ge=1)
    image_ocid: str
    subnet_ocid: str
    availability_domain: str
    ssh_public_key: str
    retry_interval_sec: int = Field(ge=1)
    max_attempts: int | None = None
    channel_ids: list[int] = Field(default_factory=list)


class ConfigRead(BaseModel):
    id: int
    name: str
    credential_id: int
    enabled: bool
    shape: str
    ocpus: int
    memory_gb: int
    boot_volume_gb: int
    image_ocid: str
    subnet_ocid: str
    availability_domain: str
    ssh_public_key: str
    retry_interval_sec: int
    max_attempts: int | None
    channel_ids: list[int]
    created_at: datetime
    updated_at: datetime

    @classmethod
    def from_model(cls, cfg: InstanceConfig) -> "ConfigRead":
        return cls(
            id=cfg.id,
            name=cfg.name,
            credential_id=cfg.credential_id,
            enabled=cfg.enabled,
            shape=cfg.shape,
            ocpus=cfg.ocpus,
            memory_gb=cfg.memory_gb,
            boot_volume_gb=cfg.boot_volume_gb,
            image_ocid=cfg.image_ocid,
            subnet_ocid=cfg.subnet_ocid,
            availability_domain=cfg.availability_domain,
            ssh_public_key=cfg.ssh_public_key,
            retry_interval_sec=cfg.retry_interval_sec,
            max_attempts=cfg.max_attempts,
            channel_ids=sorted(c.id for c in cfg.notification_channels),
            created_at=cfg.created_at,
            updated_at=cfg.updated_at,
        )
