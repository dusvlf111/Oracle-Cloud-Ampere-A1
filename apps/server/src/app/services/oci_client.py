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
import oci.core
import oci.identity
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


def build_launch_details(cfg, compartment_id: str):
    """Build a ``LaunchInstanceDetails`` from an instance config (skill: oci-sdk).

    ``cfg`` is any object exposing the InstanceConfig launch fields. Imported
    lazily so the heavyweight ``oci.core.models`` is only loaded when a launch
    actually happens (keeps test import cost low).
    """
    from oci.core.models import (
        CreateVnicDetails,
        LaunchInstanceDetails,
        LaunchInstanceShapeConfigDetails,
    )

    return LaunchInstanceDetails(
        availability_domain=cfg.availability_domain,
        compartment_id=compartment_id,
        display_name=cfg.name,
        shape=cfg.shape,
        shape_config=LaunchInstanceShapeConfigDetails(
            ocpus=cfg.ocpus,
            memory_in_gbs=cfg.memory_gb,
        ),
        image_id=cfg.image_ocid,
        subnet_id=cfg.subnet_ocid,
        create_vnic_details=CreateVnicDetails(
            subnet_id=cfg.subnet_ocid,
            assign_public_ip=True,
        ),
        metadata={"ssh_authorized_keys": cfg.ssh_public_key},
    )


def launch_instance_sync(config: dict, details) -> str:
    """Blocking ``ComputeClient.launch_instance`` → returns the instance OCID.

    Runs inside ``asyncio.to_thread`` from the worker. Raises on failure so the
    caller can :func:`classify_error` the exception.
    """
    from oci.core import ComputeClient

    client = ComputeClient(config)
    response = client.launch_instance(details)
    return response.data.id


# ---------------------------------------------------------------------------
# Metadata lookup helpers (PRD §7.2, §8 /api/meta/*).
#
# Unlike :func:`verify` these RAISE on OCI failure so the router can classify
# the exception (auth → 502 oci_auth_error, else → 502 oci_request_failed).
# The blocking SDK calls run inside ``asyncio.to_thread``. ``oci.*`` clients are
# accessed via the module attribute (``oci.core.ComputeClient`` etc.) so tests
# can monkeypatch them without a real OCI call ever escaping.
# ---------------------------------------------------------------------------


def list_availability_domains_sync(config: dict) -> list[str]:
    """Blocking ``ListAvailabilityDomains`` → AD names (compartment = tenancy)."""
    client = oci.identity.IdentityClient(config)
    response = client.list_availability_domains(compartment_id=config["tenancy"])
    return [ad.name for ad in response.data]


def list_images_sync(config: dict, shape: str) -> list[dict]:
    """Blocking ``ListImages`` filtered by ``shape`` (ARM-compatible only).

    ``shape`` makes OCI return only images that support that shape, so passing
    ``VM.Standard.A1.Flex`` yields ARM64 boot images. Newest 50 by create time.
    """
    client = oci.core.ComputeClient(config)
    response = client.list_images(
        compartment_id=config["tenancy"],
        shape=shape,
        sort_by="TIMECREATED",
        sort_order="DESC",
        limit=50,
    )
    return [
        {
            "ocid": img.id,
            "display_name": img.display_name,
            "operating_system": img.operating_system,
            "os_version": img.operating_system_version,
        }
        for img in response.data
    ]


def list_subnets_sync(config: dict) -> list[dict]:
    """Blocking ``ListSubnets`` (compartment = tenancy root)."""
    client = oci.core.VirtualNetworkClient(config)
    response = client.list_subnets(compartment_id=config["tenancy"])
    return [
        {
            "ocid": subnet.id,
            "display_name": subnet.display_name,
            "cidr_block": subnet.cidr_block,
        }
        for subnet in response.data
    ]


async def fetch_availability_domains(
    cred: dict,
    *,
    key_file: str | None = None,
    passphrase: str | None = None,
) -> list[str]:
    """Async wrapper for AD lookup. Raises on OCI failure (caller classifies)."""
    config = build_config(cred, key_file=key_file, passphrase=passphrase)
    return await asyncio.to_thread(list_availability_domains_sync, config)


async def fetch_images(
    cred: dict,
    shape: str,
    *,
    key_file: str | None = None,
    passphrase: str | None = None,
) -> list[dict]:
    """Async wrapper for image lookup. Raises on OCI failure."""
    config = build_config(cred, key_file=key_file, passphrase=passphrase)
    return await asyncio.to_thread(list_images_sync, config, shape)


async def fetch_subnets(
    cred: dict,
    *,
    key_file: str | None = None,
    passphrase: str | None = None,
) -> list[dict]:
    """Async wrapper for subnet lookup. Raises on OCI failure."""
    config = build_config(cred, key_file=key_file, passphrase=passphrase)
    return await asyncio.to_thread(list_subnets_sync, config)


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
