"""OCI meta lookup API tests (PRD §7.2, §8). OCI SDK fully mocked.

Patches ``oci.identity.IdentityClient`` / ``oci.core.ComputeClient`` /
``oci.core.VirtualNetworkClient`` on the ``app.services.oci_client`` module so
no real OCI call is ever made.
"""

from __future__ import annotations

from unittest.mock import MagicMock

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.services import crypto


@pytest.fixture
def cred_settings(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    settings = Settings(app_secret="meta-test-secret")
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr(crypto, "get_settings", lambda: settings)
    crypto._key_for.cache_clear()
    crypto._fernet_key_for.cache_clear()
    return settings


async def _create_credential(client: AsyncClient, name: str = "main") -> int:
    data = {
        "name": name,
        "tenancy_ocid": "ocid1.tenancy.oc1..aaaaaaaatenancy",
        "user_ocid": "ocid1.user.oc1..aaaaaaaauser",
        "fingerprint": "ab:cd:ef:12:34:56:78:90:ab:cd:ef:12:34:56:78:90",
        "region": "ap-chuncheon-1",
    }
    files = {
        "private_key": (
            "oci.pem",
            b"-----BEGIN KEY-----\nabc\n-----END KEY-----",
            "application/x-pem-file",
        )
    }
    resp = await client.post("/api/credentials", data=data, files=files)
    assert resp.status_code == 201, resp.text
    return resp.json()["id"]


def _ad(name: str) -> MagicMock:
    m = MagicMock()
    m.name = name  # set after construction — `name=` kwarg is reserved by Mock
    return m


def _image(ocid: str, display: str, os_: str, ver: str) -> MagicMock:
    m = MagicMock()
    m.id = ocid
    m.display_name = display
    m.operating_system = os_
    m.operating_system_version = ver
    return m


def _subnet(ocid: str, display: str, cidr: str) -> MagicMock:
    m = MagicMock()
    m.id = ocid
    m.display_name = display
    m.cidr_block = cidr
    return m


@pytest.fixture
def oci_meta_mock(monkeypatch: pytest.MonkeyPatch):
    """Patch all three OCI clients used by the meta lookups with MagicMocks."""
    import app.services.oci_client as oc

    identity = MagicMock(name="IdentityClient")
    identity.return_value.list_availability_domains.return_value = MagicMock(
        data=[_ad("Uocm:AP-CHUNCHEON-1-AD-1"), _ad("Uocm:AP-CHUNCHEON-1-AD-2")]
    )
    compute = MagicMock(name="ComputeClient")
    compute.return_value.list_images.return_value = MagicMock(
        data=[
            _image(
                "ocid1.image.oc1..aaaaubuntu",
                "Canonical-Ubuntu-22.04-aarch64-2026.05.01",
                "Canonical Ubuntu",
                "22.04",
            ),
            _image(
                "ocid1.image.oc1..aaaaoracle",
                "Oracle-Linux-9-aarch64-2026.05.01",
                "Oracle Linux",
                "9",
            ),
        ]
    )
    vcn = MagicMock(name="VirtualNetworkClient")
    vcn.return_value.list_subnets.return_value = MagicMock(
        data=[_subnet("ocid1.subnet.oc1..aaaapub", "public-subnet", "10.0.0.0/24")]
    )

    monkeypatch.setattr(oc.oci.identity, "IdentityClient", identity)
    monkeypatch.setattr(oc.oci.core, "ComputeClient", compute)
    monkeypatch.setattr(oc.oci.core, "VirtualNetworkClient", vcn)
    return {"identity": identity, "compute": compute, "vcn": vcn}


# --------------------------------------------------------------------------- #
# auth
# --------------------------------------------------------------------------- #


async def test_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/meta/availability-domains?credential_id=1")
    assert resp.status_code == 401


async def test_images_requires_auth(client: AsyncClient) -> None:
    resp = await client.get("/api/meta/images?credential_id=1")
    assert resp.status_code == 401


# --------------------------------------------------------------------------- #
# availability-domains
# --------------------------------------------------------------------------- #


async def test_availability_domains_success(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    cid = await _create_credential(authed_db_client)
    resp = await authed_db_client.get(
        f"/api/meta/availability-domains?credential_id={cid}"
    )
    assert resp.status_code == 200, resp.text
    assert resp.json() == [
        "Uocm:AP-CHUNCHEON-1-AD-1",
        "Uocm:AP-CHUNCHEON-1-AD-2",
    ]


async def test_availability_domains_auth_error(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    from oci import exceptions as oci_exceptions

    cid = await _create_credential(authed_db_client)
    oci_meta_mock["identity"].return_value.list_availability_domains.side_effect = (
        oci_exceptions.ServiceError(401, "NotAuthenticated", {}, "bad signature")
    )
    resp = await authed_db_client.get(
        f"/api/meta/availability-domains?credential_id={cid}"
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "oci_auth_error"


async def test_availability_domains_credential_not_found(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    resp = await authed_db_client.get(
        "/api/meta/availability-domains?credential_id=999"
    )
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


# --------------------------------------------------------------------------- #
# images
# --------------------------------------------------------------------------- #


async def test_images_success_and_shape_passed(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    cid = await _create_credential(authed_db_client)
    resp = await authed_db_client.get(
        f"/api/meta/images?credential_id={cid}&shape=VM.Standard.A1.Flex"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body[0] == {
        "ocid": "ocid1.image.oc1..aaaaubuntu",
        "display_name": "Canonical-Ubuntu-22.04-aarch64-2026.05.01",
        "operating_system": "Canonical Ubuntu",
        "os_version": "22.04",
    }
    # shape forwarded to ListImages so only ARM-compatible images come back.
    _, kwargs = oci_meta_mock["compute"].return_value.list_images.call_args
    assert kwargs["shape"] == "VM.Standard.A1.Flex"
    assert kwargs["sort_order"] == "DESC"


async def test_images_default_shape(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    cid = await _create_credential(authed_db_client)
    resp = await authed_db_client.get(f"/api/meta/images?credential_id={cid}")
    assert resp.status_code == 200
    _, kwargs = oci_meta_mock["compute"].return_value.list_images.call_args
    assert kwargs["shape"] == "VM.Standard.A1.Flex"


async def test_images_credential_not_found(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    resp = await authed_db_client.get("/api/meta/images?credential_id=999")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


# --------------------------------------------------------------------------- #
# subnets
# --------------------------------------------------------------------------- #


async def test_subnets_success(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    cid = await _create_credential(authed_db_client)
    resp = await authed_db_client.get(f"/api/meta/subnets?credential_id={cid}")
    assert resp.status_code == 200, resp.text
    assert resp.json() == [
        {
            "ocid": "ocid1.subnet.oc1..aaaapub",
            "display_name": "public-subnet",
            "cidr_block": "10.0.0.0/24",
        }
    ]


async def test_subnets_generic_oci_error(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    from oci import exceptions as oci_exceptions

    cid = await _create_credential(authed_db_client)
    oci_meta_mock["vcn"].return_value.list_subnets.side_effect = (
        oci_exceptions.ServiceError(500, "InternalError", {}, "boom")
    )
    resp = await authed_db_client.get(f"/api/meta/subnets?credential_id={cid}")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "oci_request_failed"


async def test_meta_unexpected_exception_converges_to_502(
    authed_db_client: AsyncClient, cred_settings, oci_meta_mock
) -> None:
    """A non-OCI exception must converge to 502 oci_request_failed, never 500.

    Regression for the prod ERROR `Unhandled exception` on /api/meta/*
    (hardening §3).
    """
    cid = await _create_credential(authed_db_client)
    oci_meta_mock["identity"].return_value.list_availability_domains.side_effect = (
        RuntimeError("unexpected boom")
    )
    resp = await authed_db_client.get(
        f"/api/meta/availability-domains?credential_id={cid}"
    )
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "oci_request_failed"
