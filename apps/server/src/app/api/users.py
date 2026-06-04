"""Admin user-management API (PRD §6.2, task 9.4).

GET    /api/users               — list all users (admin only)
POST   /api/users/{id}/approve  — pending → active
POST   /api/users/{id}/reject   — delete a pending user
POST   /api/users/{id}/disable  — active → disabled (+ disable owned configs)
POST   /api/users/{id}/enable   — disabled → active

Every route requires an admin session (``require_admin``). The last active admin
cannot be disabled (409 ``last_admin``). Disabling a user flips every config
they own to ``enabled=False`` so the poller supervisor cancels those tasks on
its next reconcile pass (PRD Open Question #4); their session is implicitly
revoked because ``require_login`` rejects non-active accounts.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel
from sqlmodel import Session, select

from app.api.deps import AppError, require_admin
from app.db.models import InstanceConfig, User
from app.db.session import get_session
from app.services.auth import (
    ROLE_ADMIN,
    STATUS_ACTIVE,
    STATUS_DISABLED,
    STATUS_PENDING,
    active_admin_count,
)

logger = logging.getLogger("app.api.users")

router = APIRouter(prefix="/api/users", tags=["users"])


class UserListItem(BaseModel):
    id: int
    username: str
    role: str
    status: str
    created_at: datetime
    approved_at: datetime | None = None

    @classmethod
    def from_model(cls, u: User) -> "UserListItem":
        return cls(
            id=u.id,
            username=u.username,
            role=u.role,
            status=u.status,
            created_at=u.created_at,
            approved_at=u.approved_at,
        )


def _get_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None:
        raise AppError(
            "user_not_found", 404, f"User id={user_id} not found", {"user_id": user_id}
        )
    return user


@router.get("", response_model=list[UserListItem])
def list_users(
    _admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> list[UserListItem]:
    rows = session.exec(select(User).order_by(User.id)).all()
    return [UserListItem.from_model(u) for u in rows]


@router.post("/{user_id}/approve", response_model=UserListItem)
def approve_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserListItem:
    user = _get_or_404(session, user_id)
    if user.status != STATUS_PENDING:
        raise AppError(
            "invalid_state",
            409,
            f"Only pending users can be approved (current: {user.status})",
            {"status": user.status},
        )
    user.status = STATUS_ACTIVE
    user.approved_at = datetime.utcnow()
    user.approved_by = admin.id
    session.add(user)
    session.commit()
    session.refresh(user)
    logger.warning("User approved id=%s by admin=%s", user.id, admin.id)
    return UserListItem.from_model(user)


@router.post("/{user_id}/reject", status_code=204)
def reject_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> Response:
    user = _get_or_404(session, user_id)
    if user.status != STATUS_PENDING:
        raise AppError(
            "invalid_state",
            409,
            f"Only pending users can be rejected (current: {user.status})",
            {"status": user.status},
        )
    session.delete(user)
    session.commit()
    logger.warning("User rejected/deleted id=%s by admin=%s", user_id, admin.id)
    return Response(status_code=204)


@router.post("/{user_id}/disable", response_model=UserListItem)
def disable_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserListItem:
    user = _get_or_404(session, user_id)
    # Protect the last active admin (covers self-disable of the only admin).
    if (
        user.role == ROLE_ADMIN
        and user.status == STATUS_ACTIVE
        and active_admin_count(session) <= 1
    ):
        raise AppError(
            "last_admin", 409, "Cannot disable the last active admin"
        )

    user.status = STATUS_DISABLED
    session.add(user)

    # Disable every config the user owns so the supervisor cancels its tasks on
    # the next reconcile pass (PRD Open Question #4).
    owned = session.exec(
        select(InstanceConfig).where(InstanceConfig.owner_id == user.id)
    ).all()
    now = datetime.utcnow()
    for cfg in owned:
        if cfg.enabled:
            cfg.enabled = False
            cfg.updated_at = now
            session.add(cfg)
    session.commit()
    session.refresh(user)
    logger.warning(
        "User disabled id=%s by admin=%s (%d configs disabled)",
        user.id,
        admin.id,
        len(owned),
    )
    return UserListItem.from_model(user)


@router.post("/{user_id}/enable", response_model=UserListItem)
def enable_user(
    user_id: int,
    admin: User = Depends(require_admin),
    session: Session = Depends(get_session),
) -> UserListItem:
    user = _get_or_404(session, user_id)
    if user.status != STATUS_DISABLED:
        raise AppError(
            "invalid_state",
            409,
            f"Only disabled users can be enabled (current: {user.status})",
            {"status": user.status},
        )
    user.status = STATUS_ACTIVE
    session.add(user)
    session.commit()
    session.refresh(user)
    logger.warning("User enabled id=%s by admin=%s", user.id, admin.id)
    return UserListItem.from_model(user)
