"""Single-admin authentication (PRD §7.7).

Argon2id password hashing/verification + credential comparison against the
``APP_USERNAME`` / ``APP_PASSWORD_HASH`` environment settings. No signup, no
multi-user — exactly one admin pair is allowed.
"""

from __future__ import annotations

import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError

from app.config import get_settings

# Module-level hasher with OWASP-reasonable defaults.
_hasher = PasswordHasher()


def hash_password(password: str) -> str:
    """Return an Argon2id hash (``$argon2id$...``) for the given password."""
    return _hasher.hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Return True iff ``password`` matches ``password_hash`` (constant-time)."""
    try:
        return _hasher.verify(password_hash, password)
    except (VerifyMismatchError, InvalidHashError, ValueError):
        return False


def authenticate(username: str, password: str) -> bool:
    """Validate credentials against the configured single admin.

    Username compared in constant time; password verified via Argon2.
    """
    settings = get_settings()
    if not settings.app_password_hash:
        return False
    username_ok = hmac.compare_digest(username, settings.app_username)
    password_ok = verify_password(settings.app_password_hash, password)
    # Evaluate both before returning to avoid short-circuit timing leaks.
    return username_ok and password_ok
