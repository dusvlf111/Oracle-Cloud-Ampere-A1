"""OCI credential management API (PRD §7.1, §8).

GET    /api/credentials            — list (masked)
POST   /api/credentials            — create (multipart form + PEM upload)
POST   /api/credentials/{id}/verify — OCI ListAvailabilityDomains smoke test
DELETE /api/credentials/{id}        — delete (+ remove key file), 204

Private keys are written to ``{keys_dir}/{id}.pem`` with mode 600. The
passphrase is AES-256-GCM encrypted before persistence. Every route requires
an authenticated session.
"""

from __future__ import annotations

import logging
import os
from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, Response, UploadFile
from sqlmodel import Session, select

from app.api.deps import AppError, require_login
from app.config import get_settings
from app.db.models import OciCredential
from app.db.session import get_session
from app.schemas.credential import CredentialRead, VerifyResponse
from app.services import oci_client
from app.services.crypto import decrypt, encrypt

logger = logging.getLogger("app.api.credentials")

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


def _key_path(credential_id: int) -> Path:
    return Path(get_settings().keys_dir) / f"{credential_id}.pem"


def _get_or_404(session: Session, credential_id: int) -> OciCredential:
    cred = session.get(OciCredential, credential_id)
    if cred is None:
        raise AppError(
            "credential_not_found",
            404,
            f"OciCredential id={credential_id} not found",
            {"credential_id": credential_id},
        )
    return cred


@router.get("", response_model=list[CredentialRead])
def list_credentials(
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[CredentialRead]:
    rows = session.exec(select(OciCredential).order_by(OciCredential.id)).all()
    return [CredentialRead.from_model(c) for c in rows]


@router.post("", response_model=CredentialRead, status_code=201)
async def create_credential(
    name: str = Form(...),
    tenancy_ocid: str = Form(...),
    user_ocid: str = Form(...),
    fingerprint: str = Form(...),
    region: str = Form(...),
    private_key: UploadFile = File(...),
    passphrase: str | None = Form(default=None),
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> CredentialRead:
    # Persist first to obtain the id used in the key file name.
    cred = OciCredential(
        name=name,
        tenancy_ocid=tenancy_ocid,
        user_ocid=user_ocid,
        fingerprint=fingerprint,
        region=region,
        private_key_path="",  # set after we know the id
        passphrase_enc=encrypt((passphrase or "").encode()) if passphrase else None,
    )
    session.add(cred)
    session.commit()
    session.refresh(cred)

    key_path = _key_path(cred.id)
    key_path.parent.mkdir(parents=True, exist_ok=True)
    content = await private_key.read()
    # Write with 0600 from the start (umask-safe).
    fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    try:
        os.write(fd, content)
    finally:
        os.close(fd)
    os.chmod(key_path, 0o600)

    cred.private_key_path = str(key_path)
    session.add(cred)
    session.commit()
    session.refresh(cred)

    logger.info(
        "OCI credential created", extra={"credential_id": cred.id}
    )
    return CredentialRead.from_model(cred)


@router.post("/{credential_id}/verify", response_model=VerifyResponse)
async def verify_credential(
    credential_id: int,
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> VerifyResponse:
    cred = _get_or_404(session, credential_id)
    passphrase = decrypt(cred.passphrase_enc).decode() if cred.passphrase_enc else None
    result = await oci_client.verify(
        {
            "id": cred.id,
            "tenancy_ocid": cred.tenancy_ocid,
            "user_ocid": cred.user_ocid,
            "fingerprint": cred.fingerprint,
            "region": cred.region,
            "private_key_path": cred.private_key_path,
        },
        passphrase=passphrase,
    )
    return VerifyResponse(ok=result.ok, error=result.error)


@router.delete("/{credential_id}", status_code=204)
def delete_credential(
    credential_id: int,
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> Response:
    cred = _get_or_404(session, credential_id)
    if cred.private_key_path:
        try:
            os.remove(cred.private_key_path)
        except FileNotFoundError:
            pass
    session.delete(cred)
    session.commit()
    logger.info("OCI credential deleted", extra={"credential_id": credential_id})
    return Response(status_code=204)
