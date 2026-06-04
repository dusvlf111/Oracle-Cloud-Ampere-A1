"""Credentials API tests (PRD §7.1, §8). OCI fully mocked.

Push 11: private keys are Fernet-encrypted in ``private_key_enc`` (no file on
disk). The plaintext PEM only lives in memory during upload / verify.
"""

from __future__ import annotations

import pytest
from httpx import AsyncClient

from app.config import Settings
from app.services import crypto, oci_client

_PLAINTEXT_PEM = b"-----BEGIN KEY-----\nabc\n-----END KEY-----"


@pytest.fixture
def cred_settings(tmp_path, monkeypatch: pytest.MonkeyPatch) -> Settings:
    """Wire up app_secret across the modules that read settings."""
    settings = Settings(app_secret="api-test-secret")
    monkeypatch.setattr("app.config.get_settings", lambda: settings)
    monkeypatch.setattr(crypto, "get_settings", lambda: settings)
    crypto._key_for.cache_clear()
    crypto._fernet_key_for.cache_clear()
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
    files = {"private_key": ("oci.pem", _PLAINTEXT_PEM, "application/x-pem-file")}
    return await client.post("/api/credentials", data=data, files=files)


async def test_requires_auth(client: AsyncClient, cred_settings) -> None:
    resp = await client.get("/api/credentials")
    assert resp.status_code == 401


async def test_create_encrypts_key_to_db_and_masks(
    authed_db_client: AsyncClient, cred_settings, session
) -> None:
    from app.db.models import OciCredential

    resp = await _create(authed_db_client, passphrase="secret-pp")
    assert resp.status_code == 201, resp.text
    body = resp.json()

    assert body["name"] == "main"
    assert body["has_passphrase"] is True
    # Masked fields — no full secret leaks.
    assert body["tenancy_ocid"].endswith("***")
    assert "tenancy" not in body["tenancy_ocid"] or body["tenancy_ocid"] != "ocid1.tenancy.oc1..aaaaaaaatenancy"
    assert body["fingerprint"].startswith("ab:cd:**")
    # The PEM is never echoed back in the response (no key field at all).
    assert "private_key" not in body
    assert "private_key_enc" not in body

    # Stored as a Fernet token (not plaintext) that decrypts back to the PEM.
    row = session.get(OciCredential, body["id"])
    session.refresh(row)
    assert row.private_key_enc
    assert _PLAINTEXT_PEM.decode() not in row.private_key_enc
    assert crypto.fernet_decrypt(row.private_key_enc).encode() == _PLAINTEXT_PEM


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


async def test_verify_unexpected_exception_converges_to_ok_false(
    authed_db_client: AsyncClient, cred_settings, oci_mock
) -> None:
    """An unexpected (non-OCI) exception must collapse to {ok: false}, not 500.

    Regression for the prod ERROR `Unhandled exception` on verify (hardening §3).
    """
    oci_mock.return_value.list_availability_domains.side_effect = RuntimeError(
        "totally unexpected"
    )
    created = (await _create(authed_db_client)).json()
    resp = await authed_db_client.post(f"/api/credentials/{created['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]


async def test_verify_uses_key_content_not_file(
    authed_db_client: AsyncClient, cred_settings, oci_mock
) -> None:
    """verify builds the OCI config from the decrypted PEM (key_content)."""
    created = (await _create(authed_db_client, passphrase="pp")).json()
    resp = await authed_db_client.post(f"/api/credentials/{created['id']}/verify")
    assert resp.status_code == 200
    assert resp.json()["ok"] is True
    # The config handed to the SDK carried key_content (PEM in memory), no file.
    cfg = oci_mock.call_args.args[0]
    assert cfg["key_content"] == _PLAINTEXT_PEM.decode()
    assert "key_file" not in cfg


async def test_verify_missing_key_converges_to_ok_false(
    authed_db_client: AsyncClient, cred_settings, oci_mock, session
) -> None:
    """A credential whose key was missing at migration (empty enc) → ok: false."""
    from app.db.models import OciCredential

    created = (await _create(authed_db_client)).json()
    row = session.get(OciCredential, created["id"])
    row.private_key_enc = ""  # simulate missing-at-migration
    session.add(row)
    session.commit()

    resp = await authed_db_client.post(f"/api/credentials/{created['id']}/verify")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is False
    assert body["error"]


async def test_verify_not_found(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    resp = await authed_db_client.post("/api/credentials/999/verify")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


async def _update(client: AsyncClient, credential_id: int, *, with_key: bool, **overrides):
    data = {
        "name": overrides.get("name", "renamed"),
        "tenancy_ocid": overrides.get("tenancy_ocid", "ocid1.tenancy.oc1..aaaaaaaatenancy2"),
        "user_ocid": overrides.get("user_ocid", "ocid1.user.oc1..aaaaaaaauser2"),
        "fingerprint": overrides.get("fingerprint", _FINGERPRINT),
        "region": overrides.get("region", "ap-seoul-1"),
    }
    if "passphrase" in overrides:
        data["passphrase"] = overrides["passphrase"]
    files = None
    if with_key:
        files = {
            "private_key": (
                "oci2.pem",
                b"-----BEGIN KEY-----\nNEWKEY\n-----END KEY-----",
                "application/x-pem-file",
            )
        }
    return await client.put(
        f"/api/credentials/{credential_id}", data=data, files=files
    )


async def test_update_without_key_keeps_existing_enc(
    authed_db_client: AsyncClient, cred_settings, session
) -> None:
    """PUT without a re-uploaded key keeps the stored encrypted key untouched."""
    from app.db.models import OciCredential

    created = (await _create(authed_db_client)).json()
    before = session.get(OciCredential, created["id"]).private_key_enc

    resp = await _update(
        authed_db_client, created["id"], with_key=False, name="renamed"
    )
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert body["name"] == "renamed"
    assert body["region"] == "ap-seoul-1"
    # Stored ciphertext is unchanged.
    row = session.get(OciCredential, created["id"])
    session.refresh(row)
    assert row.private_key_enc == before


async def test_update_with_key_re_encrypts(
    authed_db_client: AsyncClient, cred_settings, session
) -> None:
    from app.db.models import OciCredential

    created = (await _create(authed_db_client)).json()
    before = session.get(OciCredential, created["id"]).private_key_enc

    resp = await _update(authed_db_client, created["id"], with_key=True)
    assert resp.status_code == 200, resp.text
    row = session.get(OciCredential, created["id"])
    session.refresh(row)
    assert row.private_key_enc != before  # re-encrypted
    assert crypto.fernet_decrypt(row.private_key_enc) == (
        "-----BEGIN KEY-----\nNEWKEY\n-----END KEY-----"
    )


async def test_update_blank_passphrase_keeps_existing(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    created = (await _create(authed_db_client, passphrase="orig-pp")).json()
    assert created["has_passphrase"] is True
    # No passphrase field in the update → kept.
    resp = await _update(authed_db_client, created["id"], with_key=False)
    assert resp.status_code == 200
    assert resp.json()["has_passphrase"] is True


async def test_update_new_passphrase_re_encrypts(
    authed_db_client: AsyncClient, cred_settings, session
) -> None:
    from app.db.models import OciCredential

    created = (await _create(authed_db_client)).json()
    assert created["has_passphrase"] is False
    resp = await _update(
        authed_db_client, created["id"], with_key=False, passphrase="newpp"
    )
    assert resp.status_code == 200
    assert resp.json()["has_passphrase"] is True
    # The stored value decrypts back to the new passphrase.
    row = session.get(OciCredential, created["id"])
    session.refresh(row)
    assert crypto.decrypt(row.passphrase_enc).decode() == "newpp"


async def test_update_keeps_ocid_when_masked_echo_sent(
    authed_db_client: AsyncClient, cred_settings, session
) -> None:
    """Submitting the masked OCID/fingerprint echo keeps the stored values."""
    from app.db.models import OciCredential

    created = (await _create(authed_db_client)).json()
    # The read response masks these; the edit form would PUT them back as-is.
    masked_tenancy = created["tenancy_ocid"]
    masked_user = created["user_ocid"]
    masked_fp = created["fingerprint"]
    assert "*" in masked_tenancy and "*" in masked_fp

    resp = await _update(
        authed_db_client,
        created["id"],
        with_key=False,
        name="kept-ocids",
        tenancy_ocid=masked_tenancy,
        user_ocid=masked_user,
        fingerprint=masked_fp,
        region="ap-seoul-1",
    )
    assert resp.status_code == 200, resp.text

    # The stored values are the originals, not the masked echo.
    row = session.get(OciCredential, created["id"])
    session.refresh(row)
    assert row.tenancy_ocid == "ocid1.tenancy.oc1..aaaaaaaatenancy"
    assert row.user_ocid == "ocid1.user.oc1..aaaaaaaauser"
    assert row.fingerprint == _FINGERPRINT
    assert row.region == "ap-seoul-1"
    assert row.name == "kept-ocids"


async def test_update_rejects_malformed_field(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    created = (await _create(authed_db_client)).json()
    resp = await _update(
        authed_db_client, created["id"], with_key=False, region="NOPE"
    )
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "validation_error"


async def test_update_not_found(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    resp = await _update(authed_db_client, 99999, with_key=False)
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "credential_not_found"


async def test_delete_removes_credential(
    authed_db_client: AsyncClient, cred_settings
) -> None:
    created = (await _create(authed_db_client)).json()

    resp = await authed_db_client.request(
        "DELETE", f"/api/credentials/{created['id']}"
    )
    assert resp.status_code == 204

    # gone — no file cleanup needed (key was only in the encrypted DB column).
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
