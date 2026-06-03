"""OCI client service (PRD §7.1, §7.3, skill: oci-sdk).

The ``oci`` SDK is synchronous; every blocking call is wrapped in
``asyncio.to_thread``. This module owns:

- ``build_config``   — credential dict → oci config dict
- ``verify``         — ``ListAvailabilityDomains`` smoke test (auth check)
- ``classify_error`` — map an OCI exception to a domain status string

Domain statuses (also used by ``Attempt.status``):
``auth_error`` | ``out_of_capacity`` | ``rate_limited`` | ``other_error``.

All tests mock the SDK — no real OCI calls are ever made.
"""

from __future__ import annotations

import asyncio
import logging
from dataclasses import dataclass

import oci
from oci import exceptions as oci_exceptions

logger = logging.getLogger("app.services.oci_client")

# Domain error classes (subset relevant to verification / launch).
AUTH_ERROR = "auth_error"
OUT_OF_CAPACITY = "out_of_capacity"
RATE_LIMITED = "rate_limited"
OTHER_ERROR = "other_error"

_AUTH_CODES = {
    "NotAuthenticated",
    "NotAuthorizedOrNotFound",
    "NotAuthorized",
    "SignatureDoesNotMatch",
    "InvalidParameter",
}


@dataclass(slots=True)
class VerifyResult:
    ok: bool
    error: str | None = None
    status: str | None = None  # domain classification when ok is False


def build_config(
    cred: dict,
    *,
    key_file: str | None = None,
    passphrase: str | None = None,
) -> dict:
    """Build an oci config dict from a credential mapping.

    ``cred`` carries ``tenancy_ocid``/``user_ocid``/``fingerprint``/``region``.
    ``key_file`` defaults to ``cred['private_key_path']`` (key stays on disk).
    """
    config = {
        "tenancy": cred["tenancy_ocid"],
        "user": cred["user_ocid"],
        "fingerprint": cred["fingerprint"],
        "region": cred["region"],
        "key_file": key_file or cred["private_key_path"],
    }
    if passphrase:
        config["pass_phrase"] = passphrase
    return config


def classify_error(exc: Exception) -> tuple[str, str]:
    """Return ``(status, message)`` for an OCI / generic exception."""
    if isinstance(exc, oci_exceptions.ServiceError):
        msg = (exc.message or "").lower()
        if "out of host capacity" in msg or "out of capacity" in msg:
            return OUT_OF_CAPACITY, exc.message or "out of host capacity"
        if exc.status == 429:
            return RATE_LIMITED, exc.message or "rate limited"
        if exc.code in _AUTH_CODES or exc.status in {401, 403}:
            return AUTH_ERROR, f"{exc.code}: {exc.message}"
        return OTHER_ERROR, f"{exc.code}: {exc.message}"
    return OTHER_ERROR, str(exc)


def _verify_sync(config: dict) -> None:
    """Blocking verification call (runs inside a thread)."""
    client = oci.identity.IdentityClient(config)
    client.list_availability_domains(compartment_id=config["tenancy"])


async def verify(
    cred: dict,
    *,
    key_file: str | None = None,
    passphrase: str | None = None,
) -> VerifyResult:
    """Verify a credential by listing availability domains.

    Returns a :class:`VerifyResult` — never raises for OCI-level failures.
    """
    config = build_config(cred, key_file=key_file, passphrase=passphrase)
    try:
        await asyncio.to_thread(_verify_sync, config)
    except Exception as exc:  # noqa: BLE001 — surface as result, not raise
        status, message = classify_error(exc)
        logger.warning(
            "OCI credential verification failed: %s",
            message,
            extra={"credential_id": cred.get("id")},
        )
        return VerifyResult(ok=False, error=message, status=status)
    return VerifyResult(ok=True)
