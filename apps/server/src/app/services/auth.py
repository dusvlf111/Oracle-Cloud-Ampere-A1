"""Single-admin authentication (PRD §7.7).

Argon2id password hashing/verification + credential comparison against the
admin pair stored in the ``AppSetting`` key-value table (keys
``admin_username`` / ``admin_password_hash``). No env-based credentials: the
admin is created at runtime via the first-signup flow (``POST /api/auth/setup``)
and persisted in the database, sidestepping PaaS env interpolation issues with
the ``$`` characters in Argon2 hashes. Exactly one admin is allowed.
"""

from __future__ import annotations

import hmac

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlmodel import Session

from app.db.models import AppSetting

# AppSetting keys for the single admin credential pair.
ADMIN_USERNAME_KEY = "admin_username"
ADMIN_PASSWORD_HASH_KEY = "admin_password_hash"

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


def _get_setting(session: Session, key: str) -> str | None:
    row = session.get(AppSetting, key)
    return row.value if row is not None else None


def admin_exists(session: Session) -> bool:
    """Return True iff an admin password hash has been persisted."""
    return _get_setting(session, ADMIN_PASSWORD_HASH_KEY) is not None


def get_admin_username(session: Session) -> str | None:
    """Return the persisted admin username, or None if no admin exists."""
    return _get_setting(session, ADMIN_USERNAME_KEY)


def create_admin(session: Session, username: str, password: str) -> None:
    """Persist the single admin (username + Argon2id hash) and commit.

    Callers must ensure ``admin_exists`` is False first; this performs an
    unconditional upsert of both keys.
    """
    password_hash = hash_password(password)
    for key, value in (
        (ADMIN_USERNAME_KEY, username),
        (ADMIN_PASSWORD_HASH_KEY, password_hash),
    ):
        row = session.get(AppSetting, key)
        if row is None:
            session.add(AppSetting(key=key, value=value))
        else:
            row.value = value
            session.add(row)
    session.commit()


def authenticate(session: Session, username: str, password: str) -> bool:
    """Validate credentials against the persisted single admin.

    Username compared in constant time; password verified via Argon2. Returns
    False if no admin has been created yet.
    """
    stored_username = _get_setting(session, ADMIN_USERNAME_KEY)
    stored_hash = _get_setting(session, ADMIN_PASSWORD_HASH_KEY)
    if not stored_hash or stored_username is None:
        return False
    username_ok = hmac.compare_digest(username, stored_username)
    password_ok = verify_password(stored_hash, password)
    # Evaluate both before returning to avoid short-circuit timing leaks.
    return username_ok and password_ok
