"""AES-256-GCM crypto + masking tests (PRD §7.1, §9.1)."""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services import crypto
from app.services.crypto import (
    CryptoError,
    decrypt_json,
    encrypt_json,
    mask_fingerprint,
    mask_ocid,
    mask_secret,
)


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        crypto, "get_settings", lambda: Settings(app_secret="unit-test-secret-abc")
    )
    crypto._key_for.cache_clear()
    yield
    crypto._key_for.cache_clear()


def test_roundtrip_json() -> None:
    data = {"webhook_url": "https://discord.com/api/webhooks/123/abc", "n": 4}
    token = encrypt_json(data)
    assert token != str(data)  # not plaintext
    assert decrypt_json(token) == data


def test_each_encryption_uses_fresh_nonce() -> None:
    t1 = encrypt_json({"a": 1})
    t2 = encrypt_json({"a": 1})
    assert t1 != t2  # nonce randomised
    assert decrypt_json(t1) == decrypt_json(t2) == {"a": 1}


def test_tampered_ciphertext_fails() -> None:
    token = encrypt_json({"token": "tk_secret"})
    # Flip the last char of the base64 body.
    bad = token[:-2] + ("A" if token[-1] != "A" else "B") + token[-1]
    with pytest.raises(CryptoError):
        decrypt_json(bad)


def test_wrong_key_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    token = encrypt_json({"x": 1})
    monkeypatch.setattr(
        crypto, "get_settings", lambda: Settings(app_secret="a-totally-different-secret")
    )
    crypto._key_for.cache_clear()
    with pytest.raises(CryptoError):
        decrypt_json(token)


def test_malformed_token_fails() -> None:
    with pytest.raises(CryptoError):
        decrypt_json("!!! not base64 !!!")
    with pytest.raises(CryptoError):
        decrypt_json("c2hvcnQ=")  # decodes but too short


def test_mask_secret_format() -> None:
    assert mask_secret("tk_abcdefgh") == "***efgh"
    assert mask_secret("abc") == "***"  # shorter than visible
    assert mask_secret("") == "***"
    assert mask_secret(None) is None


def test_mask_ocid() -> None:
    ocid = "ocid1.tenancy.oc1..aaaaaaaabcdefg"
    assert mask_ocid(ocid) == "ocid1.tenancy.oc1..aaa***"
    assert mask_ocid(None) is None


def test_mask_fingerprint() -> None:
    assert mask_fingerprint("ab:cd:ef:12:34") == "ab:cd:**:**:**"
    assert mask_fingerprint(None) is None
