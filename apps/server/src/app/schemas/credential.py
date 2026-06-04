"""OCI credential schemas (PRD §7.1, §8).

Create uses multipart form fields + a private-key file upload, so the form
binding lives in the router. ``CredentialRead`` is the masked response shape:
OCIDs / fingerprint are masked and the passphrase is never returned (only a
``has_passphrase`` flag).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, field_validator

from app.db.models import OciCredential
from app.services.crypto import mask_fingerprint, mask_ocid
from app.services.validators import (
    FINGERPRINT_RE,
    REGION_RE,
    TENANCY_OCID_RE,
    USER_OCID_RE,
    normalize_str,
    validate_pattern,
)


class CredentialCreate(BaseModel):
    """Validated credential create payload (hardening §1).

    The router collects multipart Form fields then ``model_validate``s this so
    field errors surface as a 422 ``validation_error`` envelope. Every str field
    is stripped of surrounding whitespace and internal newlines first.
    """

    name: str
    tenancy_ocid: str
    user_ocid: str
    fingerprint: str
    region: str

    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return normalize_str(v)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("tenancy_ocid")
    @classmethod
    def _tenancy(cls, v: str) -> str:
        return validate_pattern(
            v, TENANCY_OCID_RE, "tenancy_ocid must start with 'ocid1.tenancy.'"
        )

    @field_validator("user_ocid")
    @classmethod
    def _user(cls, v: str) -> str:
        return validate_pattern(
            v, USER_OCID_RE, "user_ocid must start with 'ocid1.user.'"
        )

    @field_validator("fingerprint")
    @classmethod
    def _fingerprint(cls, v: str) -> str:
        return validate_pattern(
            v,
            FINGERPRINT_RE,
            "fingerprint must be 16 colon-separated hex octets "
            "(e.g. ab:cd:ef:...:90)",
        )

    @field_validator("region")
    @classmethod
    def _region(cls, v: str) -> str:
        return validate_pattern(
            v, REGION_RE, "region must look like 'ap-chuncheon-1'"
        )


class CredentialUpdate(BaseModel):
    """Validated credential update payload (PUT /api/credentials/{id}).

    Same field rules as :class:`CredentialCreate`. The private key file is
    optional on update (handled in the router): if no file is re-uploaded the
    existing key on disk is kept. ``passphrase`` is likewise optional and only
    re-encrypted when a non-empty value is provided.
    """

    name: str
    tenancy_ocid: str
    user_ocid: str
    fingerprint: str
    region: str

    @field_validator("*", mode="before")
    @classmethod
    def _strip(cls, v: object) -> object:
        return normalize_str(v)

    @field_validator("name")
    @classmethod
    def _name_not_blank(cls, v: str) -> str:
        if not v:
            raise ValueError("name must not be blank")
        return v

    @field_validator("tenancy_ocid")
    @classmethod
    def _tenancy(cls, v: str) -> str:
        return validate_pattern(
            v, TENANCY_OCID_RE, "tenancy_ocid must start with 'ocid1.tenancy.'"
        )

    @field_validator("user_ocid")
    @classmethod
    def _user(cls, v: str) -> str:
        return validate_pattern(
            v, USER_OCID_RE, "user_ocid must start with 'ocid1.user.'"
        )

    @field_validator("fingerprint")
    @classmethod
    def _fingerprint(cls, v: str) -> str:
        return validate_pattern(
            v,
            FINGERPRINT_RE,
            "fingerprint must be 16 colon-separated hex octets "
            "(e.g. ab:cd:ef:...:90)",
        )

    @field_validator("region")
    @classmethod
    def _region(cls, v: str) -> str:
        return validate_pattern(
            v, REGION_RE, "region must look like 'ap-chuncheon-1'"
        )


class CredentialRead(BaseModel):
    id: int
    name: str
    tenancy_ocid: str
    user_ocid: str
    fingerprint: str
    region: str
    has_passphrase: bool
    created_at: datetime

    @classmethod
    def from_model(cls, cred: OciCredential) -> "CredentialRead":
        return cls(
            id=cred.id,
            name=cred.name,
            tenancy_ocid=mask_ocid(cred.tenancy_ocid) or "",
            user_ocid=mask_ocid(cred.user_ocid) or "",
            fingerprint=mask_fingerprint(cred.fingerprint) or "",
            region=cred.region,
            has_passphrase=cred.passphrase_enc is not None,
            created_at=cred.created_at,
        )


class VerifyResponse(BaseModel):
    ok: bool
    error: str | None = None
