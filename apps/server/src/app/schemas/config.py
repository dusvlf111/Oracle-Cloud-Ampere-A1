"""InstanceConfig schemas (PRD §6, §7.2, §8).

``ConfigCreate`` / ``ConfigUpdate`` protect read-only fields (id, enabled,
timestamps) and carry ``channel_ids`` for the m2m link. ``ConfigRead`` echoes
the full config plus the resolved ``channel_ids``.
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field, field_validator

from app.db.models import InstanceConfig
from app.services.validators import (
    IMAGE_OCID_RE,
    SSH_PUBLIC_KEY_RE,
    SUBNET_OCID_RE,
    normalize_ssh_key,
    normalize_str,
    validate_pattern,
)


class _ConfigValidators:
    """Shared field validators for create/update (hardening §1).

    Strips whitespace + internal newlines from every str field, validates the
    image/subnet OCID prefixes, requires a non-blank availability domain, and
    checks the SSH public key shape after joining wrapped lines.
    """

    @field_validator(
        "name",
        "shape",
        "image_ocid",
        "subnet_ocid",
        "availability_domain",
        mode="before",
    )
    @classmethod
    def _strip(cls, v: object) -> object:
        return normalize_str(v)

    @field_validator("ssh_public_key", mode="before")
    @classmethod
    def _strip_ssh(cls, v: object) -> object:
        return normalize_ssh_key(v)

    @field_validator("image_ocid")
    @classmethod
    def _image(cls, v: str) -> str:
        return validate_pattern(
            v, IMAGE_OCID_RE, "image_ocid must start with 'ocid1.image.'"
        )

    @field_validator("subnet_ocid")
    @classmethod
    def _subnet(cls, v: str) -> str:
        return validate_pattern(
            v, SUBNET_OCID_RE, "subnet_ocid must start with 'ocid1.subnet.'"
        )

    @field_validator("availability_domain")
    @classmethod
    def _ad(cls, v: str) -> str:
        if not v:
            raise ValueError("availability_domain must not be blank")
        return v

    @field_validator("ssh_public_key")
    @classmethod
    def _ssh(cls, v: str) -> str:
        return validate_pattern(
            v,
            SSH_PUBLIC_KEY_RE,
            "ssh_public_key must be a single-line OpenSSH public key "
            "(ssh-rsa / ssh-ed25519 / ecdsa-sha2-*)",
        )


class ConfigCreate(_ConfigValidators, BaseModel):
    name: str
    credential_id: int
    shape: str = "VM.Standard.A1.Flex"
    # A1 Free Tier limits: 1–4 OCPUs, 1–24 GB memory.
    ocpus: int = Field(default=4, ge=1, le=4)
    memory_gb: int = Field(default=24, ge=1, le=24)
    boot_volume_gb: int = Field(default=50, ge=1)
    image_ocid: str
    subnet_ocid: str
    availability_domain: str
    ssh_public_key: str
    retry_interval_sec: int = Field(default=60, ge=1)
    max_attempts: int | None = None
    channel_ids: list[int] = Field(default_factory=list)


class ConfigUpdate(_ConfigValidators, BaseModel):
    name: str
    credential_id: int
    shape: str
    ocpus: int = Field(ge=1, le=4)
    memory_gb: int = Field(ge=1, le=24)
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
