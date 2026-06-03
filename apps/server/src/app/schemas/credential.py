"""OCI credential schemas (PRD §7.1, §8).

Create uses multipart form fields + a private-key file upload, so the form
binding lives in the router. ``CredentialRead`` is the masked response shape:
OCIDs / fingerprint are masked and the passphrase is never returned (only a
``has_passphrase`` flag).
"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from app.db.models import OciCredential
from app.services.crypto import mask_fingerprint, mask_ocid


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
