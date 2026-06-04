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
from fastapi.exceptions import RequestValidationError
from pydantic import ValidationError
from sqlmodel import Session, select

from app.api.deps import AppError, is_admin, require_login
from app.config import get_settings
from app.db.models import OciCredential, User
from app.db.session import get_session
from app.schemas.credential import (
    CredentialCreate,
    CredentialRead,
    CredentialUpdate,
    VerifyResponse,
)
from app.services import oci_client
from app.services.crypto import decrypt, encrypt

logger = logging.getLogger("app.api.credentials")

router = APIRouter(prefix="/api/credentials", tags=["credentials"])


def _key_path(credential_id: int) -> Path:
    return Path(get_settings().keys_dir) / f"{credential_id}.pem"


def _get_or_404(
    session: Session, credential_id: int, user: User
) -> OciCredential:
    cred = session.get(OciCredential, credential_id)
    # Hide other owners' resources behind a 404 (PRD §6.3 — no existence leak).
    if cred is None or (not is_admin(user) and cred.owner_id != user.id):
        raise AppError(
            "credential_not_found",
            404,
            f"OciCredential id={credential_id} not found",
            {"credential_id": credential_id},
        )
    return cred


@router.get("", response_model=list[CredentialRead])
def list_credentials(
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[CredentialRead]:
    stmt = select(OciCredential).order_by(OciCredential.id)
    if not is_admin(user):
        stmt = stmt.where(OciCredential.owner_id == user.id)
    rows = session.exec(stmt).all()
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
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> CredentialRead:
    # Validate + normalise the multipart Form fields. The credentials route is
    # multipart (PEM upload) so it does not go through a Pydantic body; we run
    # the same rules manually and re-raise as RequestValidationError so the
    # global handler emits the 422 ``validation_error`` envelope with per-field
    # details (hardening §1).
    try:
        payload = CredentialCreate(
            name=name,
            tenancy_ocid=tenancy_ocid,
            user_ocid=user_ocid,
            fingerprint=fingerprint,
            region=region,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    # Persist first to obtain the id used in the key file name.
    cred = OciCredential(
        name=payload.name,
        tenancy_ocid=payload.tenancy_ocid,
        user_ocid=payload.user_ocid,
        fingerprint=payload.fingerprint,
        region=payload.region,
        private_key_path="",  # set after we know the id
        passphrase_enc=encrypt((passphrase or "").encode()) if passphrase else None,
        owner_id=user.id,
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


@router.put("/{credential_id}", response_model=CredentialRead)
async def update_credential(
    credential_id: int,
    name: str = Form(...),
    tenancy_ocid: str = Form(...),
    user_ocid: str = Form(...),
    fingerprint: str = Form(...),
    region: str = Form(...),
    # Optional re-upload: if omitted (or empty), the existing key file is kept.
    private_key: UploadFile | None = File(default=None),
    # Optional passphrase: empty/omitted keeps the existing encrypted value;
    # a non-empty value re-encrypts. There is currently no way to clear a
    # passphrase via this route (matches the create form's behaviour).
    passphrase: str | None = Form(default=None),
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> CredentialRead:
    cred = _get_or_404(session, credential_id, user)

    # The list/read response masks OCIDs / fingerprint (``...aaa***`` /
    # ``ab:cd:**:**``). When the edit form submits a value back unchanged it is
    # still masked, so a literal ``*`` means "keep the stored value": substitute
    # the existing value before validation so the masked echo never fails the
    # strict patterns nor overwrites the real secret.
    def _kept(submitted: str, existing: str) -> str:
        return existing if "*" in submitted else submitted

    tenancy_ocid = _kept(tenancy_ocid, cred.tenancy_ocid)
    user_ocid = _kept(user_ocid, cred.user_ocid)
    fingerprint = _kept(fingerprint, cred.fingerprint)

    # Validate + normalise the multipart Form fields (same rules as create).
    try:
        payload = CredentialUpdate(
            name=name,
            tenancy_ocid=tenancy_ocid,
            user_ocid=user_ocid,
            fingerprint=fingerprint,
            region=region,
        )
    except ValidationError as exc:
        raise RequestValidationError(exc.errors()) from exc

    cred.name = payload.name
    cred.tenancy_ocid = payload.tenancy_ocid
    cred.user_ocid = payload.user_ocid
    cred.fingerprint = payload.fingerprint
    cred.region = payload.region

    # Only re-encrypt the passphrase when a non-empty value is provided; an
    # empty string means "leave the stored passphrase untouched".
    if passphrase:
        cred.passphrase_enc = encrypt(passphrase.encode())

    # Only overwrite the key file when a non-empty upload is provided.
    if private_key is not None:
        content = await private_key.read()
        if content:
            key_path = _key_path(cred.id)
            key_path.parent.mkdir(parents=True, exist_ok=True)
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

    logger.info("OCI credential updated", extra={"credential_id": cred.id})
    return CredentialRead.from_model(cred)


@router.post("/{credential_id}/verify", response_model=VerifyResponse)
async def verify_credential(
    credential_id: int,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> VerifyResponse:
    cred = _get_or_404(session, credential_id, user)
    # verify must NEVER 500: any unexpected error (decrypt failure, malformed
    # config, OCI exception) collapses into {ok: false, error} (hardening §3).
    try:
        passphrase = (
            decrypt(cred.passphrase_enc).decode() if cred.passphrase_enc else None
        )
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
    except Exception as exc:  # noqa: BLE001 — verify never raises to the client
        logger.warning(
            "Credential verify hit an unexpected error: %s",
            exc,
            extra={"credential_id": credential_id},
        )
        return VerifyResponse(ok=False, error=str(exc))


@router.delete("/{credential_id}", status_code=204)
def delete_credential(
    credential_id: int,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> Response:
    cred = _get_or_404(session, credential_id, user)
    if cred.private_key_path:
        try:
            os.remove(cred.private_key_path)
        except FileNotFoundError:
            pass
    session.delete(cred)
    session.commit()
    logger.info("OCI credential deleted", extra={"credential_id": credential_id})
    return Response(status_code=204)
