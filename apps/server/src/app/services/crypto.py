"""AES-256-GCM encryption + masking utilities (PRD §7.1, §9.1).

Secrets at rest (OCI key passphrase, notification channel tokens / webhook
URLs) are encrypted with AES-256-GCM. The 32-byte key is derived from the
``APP_SECRET`` env via HKDF-SHA256 so the same secret can also sign sessions
without key reuse confusion.

Wire format (urlsafe-base64)::

    base64( nonce[12] || ciphertext || tag )

``encrypt_json`` / ``decrypt_json`` serialise an arbitrary JSON-able dict.
"""

from __future__ import annotations

import base64
import json
from functools import lru_cache

from cryptography.exceptions import InvalidTag
from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.hashes import SHA256
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

from app.config import get_settings

NONCE_SIZE = 12  # 96-bit nonce recommended for GCM
_HKDF_INFO = b"oci-ampere-aes256gcm-v1"
# Distinct HKDF context for the Fernet key so the OCI private-key cipher never
# reuses the AES-GCM key material (PRD §7.1 — domain separation).
_HKDF_INFO_FERNET = b"oci-ampere-fernet-v1"


class CryptoError(Exception):
    """Raised when decryption fails (tampered / wrong key / malformed)."""


def _derive_key(app_secret: str) -> bytes:
    if not app_secret:
        raise CryptoError("APP_SECRET is not configured")
    hkdf = HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO)
    return hkdf.derive(app_secret.encode("utf-8"))


@lru_cache(maxsize=8)
def _key_for(app_secret: str) -> bytes:
    return _derive_key(app_secret)


def _aesgcm() -> AESGCM:
    secret = get_settings().app_secret
    return AESGCM(_key_for(secret))


def encrypt(plaintext: bytes) -> str:
    """Encrypt raw bytes → urlsafe-base64 token (nonce prepended)."""
    import os

    nonce = os.urandom(NONCE_SIZE)
    ct = _aesgcm().encrypt(nonce, plaintext, None)
    return base64.urlsafe_b64encode(nonce + ct).decode("ascii")


def decrypt(token: str) -> bytes:
    """Decrypt a token produced by :func:`encrypt`. Raises ``CryptoError``."""
    try:
        raw = base64.urlsafe_b64decode(token.encode("ascii"))
    except (ValueError, base64.binascii.Error) as exc:  # type: ignore[attr-defined]
        raise CryptoError("malformed ciphertext") from exc
    if len(raw) <= NONCE_SIZE:
        raise CryptoError("ciphertext too short")
    nonce, ct = raw[:NONCE_SIZE], raw[NONCE_SIZE:]
    try:
        return _aesgcm().decrypt(nonce, ct, None)
    except InvalidTag as exc:
        raise CryptoError("decryption failed (tampered or wrong key)") from exc


# --------------------------------------------------------------------------- #
# Fernet — used for OCI private-key PEM blobs at rest (PRD §7.1).
#
# Fernet (AES-128-CBC + HMAC-SHA256, urlsafe-base64 token) is a good fit for
# larger opaque blobs like a PEM key: authenticated, versioned, and timestamped.
# The 32-byte Fernet key is derived from ``APP_SECRET`` via HKDF-SHA256 with a
# context distinct from the AES-GCM key so the two ciphers never share material.
# --------------------------------------------------------------------------- #


def _derive_fernet_key(app_secret: str) -> bytes:
    if not app_secret:
        raise CryptoError("APP_SECRET is not configured")
    hkdf = HKDF(algorithm=SHA256(), length=32, salt=None, info=_HKDF_INFO_FERNET)
    raw = hkdf.derive(app_secret.encode("utf-8"))
    # Fernet expects a urlsafe-base64-encoded 32-byte key.
    return base64.urlsafe_b64encode(raw)


@lru_cache(maxsize=8)
def _fernet_key_for(app_secret: str) -> bytes:
    return _derive_fernet_key(app_secret)


def _fernet() -> Fernet:
    secret = get_settings().app_secret
    return Fernet(_fernet_key_for(secret))


def fernet_encrypt(plaintext: str) -> str:
    """Encrypt a string (e.g. a PEM private key) → Fernet token (str).

    The plaintext is held in memory only; the returned token is what gets
    persisted. Raises :class:`CryptoError` if ``APP_SECRET`` is unset.
    """
    token = _fernet().encrypt(plaintext.encode("utf-8"))
    return token.decode("ascii")


def fernet_decrypt(token: str) -> str:
    """Decrypt a token produced by :func:`fernet_encrypt` back to the plaintext.

    Raises :class:`CryptoError` on a tampered / malformed / wrong-key token so
    callers converge on a single failure mode (never leaking the plaintext).
    """
    try:
        raw = _fernet().decrypt(token.encode("ascii"))
    except (InvalidToken, ValueError) as exc:
        raise CryptoError("fernet decryption failed (tampered or wrong key)") from exc
    return raw.decode("utf-8")


def encrypt_json(data: dict) -> str:
    """Serialise ``data`` to JSON and encrypt."""
    return encrypt(json.dumps(data, ensure_ascii=False, separators=(",", ":")).encode("utf-8"))


def decrypt_json(token: str) -> dict:
    """Decrypt and JSON-parse back into a dict."""
    try:
        return json.loads(decrypt(token).decode("utf-8"))
    except json.JSONDecodeError as exc:
        raise CryptoError("decrypted payload is not valid JSON") from exc


# --------------------------------------------------------------------------- #
# Masking helpers (PRD §7.5.2, §9.1) — never expose full secrets in responses.
# --------------------------------------------------------------------------- #

def mask_secret(value: str | None, *, visible: int = 4) -> str | None:
    """Generic mask: ``***`` + last ``visible`` chars.

    Short / empty values collapse to ``***`` so nothing leaks.
    """
    if value is None:
        return None
    if len(value) <= visible:
        return "***"
    return f"***{value[-visible:]}"


def mask_ocid(ocid: str | None) -> str | None:
    """Mask an OCID keeping the leading type prefix readable.

    ``ocid1.tenancy.oc1..aaaaXXXX`` → ``ocid1.tenancy.oc1..aaa***``
    """
    if not ocid:
        return ocid
    parts = ocid.split("..", 1)
    if len(parts) == 2 and parts[1]:
        head, tail = parts
        keep = tail[:3]
        return f"{head}..{keep}***"
    # Fallback: keep first ~12 chars.
    if len(ocid) > 12:
        return f"{ocid[:12]}***"
    return f"{ocid}***"


def mask_fingerprint(fp: str | None) -> str | None:
    """Mask an API key fingerprint: keep first octet, star the rest.

    ``ab:cd:ef:12:34`` → ``ab:cd:**:**:**``
    """
    if not fp:
        return fp
    octets = fp.split(":")
    if len(octets) <= 2:
        return mask_secret(fp)
    return ":".join(octets[:2] + ["**"] * (len(octets) - 2))
