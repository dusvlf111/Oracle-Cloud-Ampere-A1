"""OCI metadata lookup API (PRD §7.2, §8, skill: oci-sdk).

GET /api/meta/availability-domains?credential_id=  → list[str]
GET /api/meta/images?credential_id=&shape=          → list[ImageOption]
GET /api/meta/subnets?credential_id=                → list[SubnetOption]

Powers the config-create form dropdowns. The compartment is always the tenancy
root (``credential.tenancy_ocid``) — the common Free Tier layout. Every route
requires an authenticated session. OCI failures are mapped to the standard
error envelope: auth → 502 ``oci_auth_error``, anything else → 502
``oci_request_failed``. A missing credential → 404 ``credential_not_found``.

All OCI calls go through ``services.oci_client`` (``asyncio.to_thread`` + exc
classification); tests mock the SDK so no real call escapes.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends
from sqlmodel import Session

from app.api.deps import AppError, is_admin, require_login
from app.db.models import OciCredential, User
from app.db.session import get_session
from app.schemas.meta import ImageOption, SubnetOption
from app.services import oci_client
from app.services.crypto import decrypt

logger = logging.getLogger("app.api.meta")

router = APIRouter(prefix="/api/meta", tags=["meta"])


def _get_or_404(
    session: Session, credential_id: int, user: User
) -> OciCredential:
    cred = session.get(OciCredential, credential_id)
    # Ownership scope (PRD §6.3): meta lookups only for owned credentials.
    if cred is None or (not is_admin(user) and cred.owner_id != user.id):
        raise AppError(
            "credential_not_found",
            404,
            f"OciCredential id={credential_id} not found",
            {"credential_id": credential_id},
        )
    return cred


def _cred_dict(cred: OciCredential) -> dict:
    return {
        "id": cred.id,
        "tenancy_ocid": cred.tenancy_ocid,
        "user_ocid": cred.user_ocid,
        "fingerprint": cred.fingerprint,
        "region": cred.region,
        "private_key_path": cred.private_key_path,
    }


def _passphrase(cred: OciCredential) -> str | None:
    return decrypt(cred.passphrase_enc).decode() if cred.passphrase_enc else None


def _to_app_error(exc: Exception) -> AppError:
    """Map an OCI exception to the standard error envelope (PRD §8)."""
    status, message = oci_client.classify_error(exc)
    if status == oci_client.AUTH_ERROR:
        return AppError("oci_auth_error", 502, message)
    return AppError("oci_request_failed", 502, message)


@router.get("/availability-domains", response_model=list[str])
async def list_availability_domains(
    credential_id: int,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[str]:
    cred = _get_or_404(session, credential_id, user)
    try:
        # _passphrase/_cred_dict inside the try so a decrypt failure also
        # converges to 502 instead of leaking a 500 (hardening §3).
        return await oci_client.fetch_availability_domains(
            _cred_dict(cred), passphrase=_passphrase(cred)
        )
    except Exception as exc:  # noqa: BLE001 — classify into standard envelope
        logger.warning(
            "OCI availability-domains lookup failed: %s",
            exc,
            extra={"credential_id": credential_id},
        )
        raise _to_app_error(exc) from exc


@router.get("/images", response_model=list[ImageOption])
async def list_images(
    credential_id: int,
    shape: str = "VM.Standard.A1.Flex",
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[ImageOption]:
    cred = _get_or_404(session, credential_id, user)
    try:
        rows = await oci_client.fetch_images(
            _cred_dict(cred), shape, passphrase=_passphrase(cred)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "OCI images lookup failed: %s",
            exc,
            extra={"credential_id": credential_id},
        )
        raise _to_app_error(exc) from exc
    return [ImageOption(**row) for row in rows]


@router.get("/subnets", response_model=list[SubnetOption])
async def list_subnets(
    credential_id: int,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[SubnetOption]:
    cred = _get_or_404(session, credential_id, user)
    try:
        rows = await oci_client.fetch_subnets(
            _cred_dict(cred), passphrase=_passphrase(cred)
        )
    except Exception as exc:  # noqa: BLE001
        logger.warning(
            "OCI subnets lookup failed: %s",
            exc,
            extra={"credential_id": credential_id},
        )
        raise _to_app_error(exc) from exc
    return [SubnetOption(**row) for row in rows]
