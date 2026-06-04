"""Fernet crypto tests for OCI private-key PEM blobs (PRD §7.1, task 11.1).

The Fernet utilities encrypt the private-key PEM at rest. These tests cover:

  - round-trip (encrypt → decrypt yields the original PEM)
  - tampered / malformed tokens raise ``CryptoError`` (never return plaintext)
  - the Fernet key is derived independently from the AES-GCM key (domain
    separation): an AES-GCM token is not a valid Fernet token and vice versa
  - a missing ``APP_SECRET`` raises ``CryptoError``
"""

from __future__ import annotations

import pytest

from app.config import Settings
from app.services import crypto
from app.services.crypto import (
    CryptoError,
    encrypt,
    fernet_decrypt,
    fernet_encrypt,
)

_PEM = (
    "-----BEGIN PRIVATE KEY-----\n"
    "MIIEvgIBADANBgkqhkiG9w0BAQEFAASCBKgwggSkAgEAAoIBAQ\n"
    "-----END PRIVATE KEY-----\n"
)


@pytest.fixture(autouse=True)
def _secret(monkeypatch: pytest.MonkeyPatch):
    monkeypatch.setattr(
        crypto, "get_settings", lambda: Settings(app_secret="fernet-test-secret-xyz")
    )
    crypto._key_for.cache_clear()
    crypto._fernet_key_for.cache_clear()
    yield
    crypto._key_for.cache_clear()
    crypto._fernet_key_for.cache_clear()


def test_fernet_roundtrip_pem() -> None:
    token = fernet_encrypt(_PEM)
    assert token != _PEM  # not stored in plaintext
    assert _PEM not in token
    assert fernet_decrypt(token) == _PEM


def test_fernet_each_encryption_differs_but_decrypts_same() -> None:
    t1 = fernet_encrypt(_PEM)
    t2 = fernet_encrypt(_PEM)
    assert t1 != t2  # Fernet embeds a random IV + timestamp
    assert fernet_decrypt(t1) == fernet_decrypt(t2) == _PEM


def test_fernet_rejects_tampered_token() -> None:
    token = fernet_encrypt(_PEM)
    # Flip a character in the middle of the token body.
    mid = len(token) // 2
    tampered = token[:mid] + ("A" if token[mid] != "A" else "B") + token[mid + 1 :]
    with pytest.raises(CryptoError):
        fernet_decrypt(tampered)


def test_fernet_rejects_malformed_token() -> None:
    with pytest.raises(CryptoError):
        fernet_decrypt("not-a-fernet-token!!!")


def test_fernet_and_aesgcm_keys_are_independent() -> None:
    """An AES-GCM token must not be decryptable as Fernet (separate key/ctx)."""
    aes_token = encrypt(b"some-secret")
    with pytest.raises(CryptoError):
        fernet_decrypt(aes_token)


def test_fernet_requires_app_secret(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(crypto, "get_settings", lambda: Settings(app_secret=""))
    crypto._fernet_key_for.cache_clear()
    with pytest.raises(CryptoError):
        fernet_encrypt(_PEM)
