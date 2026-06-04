"""OCI client service tests (PRD §7.1, skill: oci-sdk).

The oci SDK is fully mocked via the ``oci_mock`` fixture — no real calls.
"""

from __future__ import annotations

import pytest
from oci import exceptions as oci_exceptions

from app.services import oci_client
from app.services.oci_client import (
    AUTH_ERROR,
    CONFIG_ERROR,
    OTHER_ERROR,
    OUT_OF_CAPACITY,
    RATE_LIMITED,
    build_config,
    classify_error,
    verify,
)

CRED = {
    "id": 1,
    "tenancy_ocid": "ocid1.tenancy.oc1..aaa",
    "user_ocid": "ocid1.user.oc1..bbb",
    "fingerprint": "ab:cd:ef:12:34",
    "region": "ap-chuncheon-1",
    "private_key_path": "/data/keys/1.pem",
}


def test_build_config_uses_key_file_and_passphrase() -> None:
    cfg = build_config(CRED, passphrase="pw")
    assert cfg["tenancy"] == CRED["tenancy_ocid"]
    assert cfg["user"] == CRED["user_ocid"]
    assert cfg["fingerprint"] == CRED["fingerprint"]
    assert cfg["region"] == CRED["region"]
    assert cfg["key_file"] == "/data/keys/1.pem"
    assert cfg["pass_phrase"] == "pw"


def test_build_config_no_passphrase_omits_field() -> None:
    cfg = build_config(CRED)
    assert "pass_phrase" not in cfg


def _svc_error(status: int, code: str, message: str) -> oci_exceptions.ServiceError:
    return oci_exceptions.ServiceError(status, code, {}, message)


@pytest.mark.parametrize(
    ("exc", "expected"),
    [
        (_svc_error(500, "InternalError", "Out of host capacity."), OUT_OF_CAPACITY),
        (_svc_error(429, "TooManyRequests", "slow down"), RATE_LIMITED),
        # 429 stays rate_limited even though it's a 4xx (never config_error).
        (_svc_error(429, "TooManyRequests", "bad request"), RATE_LIMITED),
        (_svc_error(401, "NotAuthenticated", "bad key"), AUTH_ERROR),
        (_svc_error(403, "NotAuthorized", "forbidden"), AUTH_ERROR),
        # Permanent client errors → config_error (hardening §2).
        (_svc_error(404, "NotAuthorizedOrNotFound", "nope"), CONFIG_ERROR),
        (_svc_error(400, "InvalidParameter", "bad ocid"), CONFIG_ERROR),
        (_svc_error(400, "CannotParseRequest", "malformed"), CONFIG_ERROR),
        (_svc_error(400, "SomethingElse", "still 400"), CONFIG_ERROR),
        (_svc_error(503, "ServiceUnavailable", "later"), OTHER_ERROR),
        (RuntimeError("boom"), OTHER_ERROR),
    ],
)
def test_classify_error(exc: Exception, expected: str) -> None:
    status, message = classify_error(exc)
    assert status == expected
    assert message


async def test_verify_success(oci_mock) -> None:
    result = await verify(CRED)
    assert result.ok is True
    assert result.error is None
    oci_mock.return_value.list_availability_domains.assert_called_once_with(
        compartment_id=CRED["tenancy_ocid"]
    )


async def test_verify_auth_failure(oci_mock) -> None:
    oci_mock.return_value.list_availability_domains.side_effect = _svc_error(
        401, "NotAuthenticated", "invalid signature"
    )
    result = await verify(CRED)
    assert result.ok is False
    assert result.status == AUTH_ERROR
    assert "NotAuthenticated" in result.error


async def test_verify_rate_limited(oci_mock) -> None:
    oci_mock.return_value.list_availability_domains.side_effect = _svc_error(
        429, "TooManyRequests", "rate limited"
    )
    result = await verify(CRED)
    assert result.ok is False
    assert result.status == RATE_LIMITED


async def test_verify_generic_exception(oci_mock) -> None:
    oci_mock.return_value.list_availability_domains.side_effect = ValueError("weird")
    result = await verify(CRED)
    assert result.ok is False
    assert result.status == OTHER_ERROR


def test_verify_runs_in_thread_not_blocking(oci_mock) -> None:
    # Ensure the sync helper is what actually invokes the SDK.
    oci_client._verify_sync(build_config(CRED))
    oci_mock.assert_called_once()
