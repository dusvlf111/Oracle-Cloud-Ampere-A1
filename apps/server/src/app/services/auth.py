"""User-based authentication (PRD §5, §6).

Argon2id password hashing/verification against the ``User`` table. Push 9
replaces the legacy single-admin ``AppSetting`` key-value pair with proper user
rows: the first signup becomes ``role=admin, status=active``; every subsequent
signup lands as ``role=user, status=pending`` until an admin approves it.

Only ``active`` users may authenticate; ``pending`` / ``disabled`` accounts are
surfaced to the caller (login endpoint) so it can emit the right 403 code.
"""

from __future__ import annotations

from datetime import datetime

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerifyMismatchError
from sqlmodel import Session, func, select

from app.db.models import User

# User status values (PRD §5).
STATUS_PENDING = "pending"
STATUS_ACTIVE = "active"
STATUS_DISABLED = "disabled"

# Roles (PRD §5).
ROLE_ADMIN = "admin"
ROLE_USER = "user"

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


def user_count(session: Session) -> int:
    """Total number of user rows (0 ⇒ the next signup is the bootstrap admin)."""
    return int(session.exec(select(func.count()).select_from(User)).one())


def get_user_by_username(session: Session, username: str) -> User | None:
    return session.exec(select(User).where(User.username == username)).first()


def admin_exists(session: Session) -> bool:
    """True iff at least one user exists (legacy ``needs_setup`` semantics).

    Retained so ``GET /api/auth/setup`` keeps reporting whether the bootstrap
    flow is still available.
    """
    return user_count(session) > 0


def active_admin_count(session: Session) -> int:
    """Number of admins that can currently log in (status=active)."""
    return int(
        session.exec(
            select(func.count())
            .select_from(User)
            .where(User.role == ROLE_ADMIN, User.status == STATUS_ACTIVE)
        ).one()
    )


def register_user(session: Session, username: str, password: str) -> User:
    """Create a user. The first ever user is an active admin; rest are pending.

    Raises ``ValueError("username_taken")`` if the username already exists. The
    caller maps that to a 409. Commits and returns the persisted row.
    """
    if get_user_by_username(session, username) is not None:
        raise ValueError("username_taken")

    is_bootstrap = user_count(session) == 0
    now = datetime.utcnow()
    user = User(
        username=username,
        password_hash=hash_password(password),
        role=ROLE_ADMIN if is_bootstrap else ROLE_USER,
        status=STATUS_ACTIVE if is_bootstrap else STATUS_PENDING,
        created_at=now,
        approved_at=now if is_bootstrap else None,
    )
    session.add(user)
    session.commit()
    session.refresh(user)
    return user


def authenticate(session: Session, username: str, password: str) -> User | None:
    """Return the ``User`` iff credentials are valid, else ``None``.

    A return value does NOT imply the user may log in — the caller must check
    ``status`` (only ``active`` is allowed) and emit ``account_pending`` /
    ``account_disabled`` as appropriate. Password is always verified (even for a
    missing user, against a dummy hash) to keep timing uniform.
    """
    user = get_user_by_username(session, username)
    if user is None:
        # Verify against a throwaway hash to avoid a username-enumeration timing
        # side channel, then fail.
        verify_password(
            "$argon2id$v=19$m=65536,t=3,p=4$"
            "c29tZXNhbHR2YWx1ZQ$0000000000000000000000000000000000000000000",
            password,
        )
        return None
    if not verify_password(user.password_hash, password):
        return None
    return user
