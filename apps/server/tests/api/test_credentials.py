"""Credentials API tests (PRD §7.1, §8). OCI fully mocked."""

from __future__ import annotations

import os
import stat

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.services import crypto, oci_client


@pytest.fixture
def cred_settings(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Wire up keys_dir + app_secret across the modules that read settings."""
    keys = tmp_path / "keys"
    settings = Settings(
        app_secret="api-test-secret",
        keys_dir=str(keys),
    )
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr("app.api.credentials.get_settings", lambda: settings)
    monkeypatch.setattr(crypto, "get_settings", lambda: settings)
    crypto._key_for.cache_clear()
    return settings


_FINGERPRINT = "ab:cd:ef:12:34:56:78:90:ab:cd:ef:12:34:56:78:90"


async def _create(client: AsyncClient, **overrides):
    data = {
        "name": overrides.get("name", "main"),
        "tenancy_ocid": overrides.get("tenancy_ocid", "ocid1.tenancy.oc1..aaaaaaaatenancy"),
        "user_ocid": overrides.get("user_ocid", "ocid1.user.oc1..aaaaaaaauser"),
        "fingerprint": overrides.get("fingerprint", _FINGERPRINT),
        "region": overrides.get("region", "ap-chuncheon-1"),
    }
    if "passphrase" in overrides:
        data["passphrase"] = overrides["passphrase"]
    files = {"private_key": ("oci.pem", b"-----BEGIN KEY-----\nabc\n-----END KEY-----", "application/x-pem-file")}
    return await client.post("/api/credentials", data=data, files=files)


async def test_requires_auth(client: AsyncClient, cred_settings) -> None:
    resp = await client.get("/api/credentials")
    assert resp.status_code == 401


async def test_create_writes_key_file_0600_and_masks(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    resp = await _create(authed_db_client, passphrase="secret-pp")
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["name"] == "main"
    assert body["has_passphrase"] is True
    # Masked fields — no full secret leaks.
    assert body["tenancy_ocid"].endswith("***")
    assert "tenancy" not in body["tenancy_ocid"] or body["tenancy_ocid"] != "ocid1.tenancy.oc1..aaaaaaaatenancy"
    assert body["fingerprint"].startswith("ab:cd:**")

    key_path = cred_settings.keys_dir + f"/{body['id']}.pem"
    assert os.path.exists(key_path)
    mode = stat.S_IMODE(os.stat(key_path).st_mode)
    assert mode == 0o600


async def test_create_without_passphrase(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    resp = await _create(authed_db_client, name="nopw")
    assert resp.status_code == 201
    assert resp.json()["has_passphrase"] is False


async def test_list_returns_masked(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    await _create(authed_db_client, name="a")
    await _create(authed_db_client, name="b")
    resp = await authed_db_client.get("/api/credentials")
    assert resp.status_code == 200
    rows = resp.json()
    assert {r["name"] for r in rows} == {"a", "b"}
    assert all(r["user_ocid"].endswith("***") for r in rows)


async def test_verify_success(
    authed_db_client: AsyncClient, cred_settings, oci_mock
) -> None:
    created = (await _create(authed_db_client, passphrase="pp")).json()
    resp = await authed_db_client.post(f"/api/credentials/{created['id']}/verify")
    assert resp.status_code == 200
    assert resp.json() == {"ok": True, "error": None}


async def test_verify_failure(
    authed_db_client: AsyncClient, cred_settings, oci_mock
) -> None:
    from oci import exceptions as oci_exceptions

    oci_mock.return_value.list_availability_domains.side_effect = (
        oci_exceptions.ServiceError(401, "NotAuthenticated", {}, "bad signature")
    )
    created = (await _create(authed_db_client)).json()
    resp = await authed_db_client.post(f"/api/credentials/{created['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert "NotAuthenticated" in body["error"]


async def test_verify_not_found(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    resp = await authed_db_client.post("/api/credentials/999/verify")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


async def test_delete_removes_key_file(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    created = (await _create(authed_db_client)).json()
    key_path = cred_settings.keys_dir + f"/{created['id']}.pem"
    assert os.path.exists(key_path)

    resp = await authed_db_client.request(
        "DELETE", f"/api/credentials/{created['id']}"
    )
    assert resp.status_code == 204
    assert not os.path.exists(key_path)

    # gone
    resp2 = await authed_db_client.post(f"/api/credentials/{created['id']}/verify")
    assert resp2.status_code == 404


async def test_delete_not_found(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    resp = await authed_db_client.request("DELETE", "/api/credentials/12345")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


# --- input validation + normalisation (hardening §1) -----------------------


async def test_create_strips_whitespace_and_newlines(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    """Pasted values with stray whitespace/newlines are normalised, not rejected."""
    resp = await _create(
        authed_db_client,
        tenancy_ocid="  ocid1.tenancy.oc1..aaaaaaaatenancy\n",
        user_ocid="ocid1.user.oc1..aaaaaaaauser\r\n",
        fingerprint=f"  {_FINGERPRINT}  ",
        region=" ap-chuncheon-1 ",
    )
    assert resp.status_code == 201, resp.text

    # The stored value is the stripped form (masked echo still ends with ***).
    body = resp.json()
    assert body["region"] == "ap-chuncheon-1"


@pytest.mark.parametrize(
    ("field", "value", "needle"),
    [
        ("tenancy_ocid", "ocid1.user.oc1..wrong", "tenancy_ocid"),
        ("user_ocid", "ocid1.tenancy.oc1..wrong", "user_ocid"),
        ("fingerprint", "ab:cd:ef", "fingerprint"),
        ("fingerprint", "ZZ:cd:ef:12:34:56:78:90:ab:cd:ef:12:34:56:78:90", "fingerprint"),
        ("region", "AP_Chuncheon", "region"),
    ],
)
async def test_create_rejects_malformed_fields(
    authed_db_client: AsyncClient, cred_settings, field: str, value: str, needle: str
) -> None:
    resp = await _create(authed_db_client, **{field: value})
    assert resp.status_code == 422, resp.text
    body = resp.json()
    assert body["error"]["code"] == "validation_error"
    # The offending field name appears in the per-field error details.
    blob = str(body["error"]["details"])
    assert needle in blob
