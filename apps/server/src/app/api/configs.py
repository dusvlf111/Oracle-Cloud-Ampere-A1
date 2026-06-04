"""InstanceConfig CRUD + toggle API (PRD §7.2, §8).

GET    /api/configs           — list (channel_ids included)
POST   /api/configs           — create (channel_ids m2m)
PUT    /api/configs/{id}      — update (channel_ids replaced)
DELETE /api/configs/{id}      — delete, 204
POST   /api/configs/{id}/toggle — flip enabled (supervisor reacts in Push 5)

Every route requires an authenticated session.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app.api.deps import AppError, is_admin, require_login
from app.db.models import InstanceConfig, NotificationChannel, OciCredential, User
from app.db.session import get_session
from app.schemas.config import ConfigCreate, ConfigRead, ConfigUpdate

logger = logging.getLogger("app.api.configs")

router = APIRouter(prefix="/api/configs", tags=["configs"])


def _get_or_404(session: Session, config_id: int, user: User) -> InstanceConfig:
    cfg = session.get(InstanceConfig, config_id)
    # Hide other owners' configs behind a 404 (PRD §6.3).
    if cfg is None or (not is_admin(user) and cfg.owner_id != user.id):
        raise AppError(
            "config_not_found",
            404,
            f"InstanceConfig id={config_id} not found",
            {"config_id": config_id},
        )
    return cfg


def _require_credential(session: Session, credential_id: int, user: User) -> None:
    cred = session.get(OciCredential, credential_id)
    # A credential the caller doesn't own is hidden (404), preventing a user
    # from attaching their config to someone else's credential.
    if cred is None or (not is_admin(user) and cred.owner_id != user.id):
        raise AppError(
            "credential_not_found",
            404,
            f"OciCredential id={credential_id} not found",
            {"credential_id": credential_id},
        )


def _resolve_channels(
    session: Session, channel_ids: list[int], user: User, owner_id: int
) -> list[NotificationChannel]:
    """Resolve channels, enforcing same-owner linkage (PRD §5).

    A config may only link channels owned by the same user (``owner_id``).
    Unknown channels → 404; a channel owned by a different user → 422
    ``owner_mismatch`` (the link itself is invalid, not a lookup miss).
    """
    if not channel_ids:
        return []
    rows = session.exec(
        select(NotificationChannel).where(NotificationChannel.id.in_(channel_ids))
    ).all()
    # Non-admins can't even see channels they don't own → treat as not found.
    if not is_admin(user):
        rows = [c for c in rows if c.owner_id == user.id]
    found = {c.id for c in rows}
    missing = [cid for cid in channel_ids if cid not in found]
    if missing:
        raise AppError(
            "channel_not_found",
            404,
            f"NotificationChannel(s) not found: {missing}",
            {"channel_ids": missing},
        )
    # Same-owner linkage: every channel must belong to the config's owner.
    mismatched = [c.id for c in rows if c.owner_id != owner_id]
    if mismatched:
        raise AppError(
            "owner_mismatch",
            422,
            "Channels must belong to the same owner as the config",
            {"channel_ids": mismatched},
        )
    return list(rows)


@router.get("", response_model=list[ConfigRead])
def list_configs(
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[ConfigRead]:
    stmt = select(InstanceConfig).order_by(InstanceConfig.id)
    if not is_admin(user):
        stmt = stmt.where(InstanceConfig.owner_id == user.id)
    rows = session.exec(stmt).all()
    return [ConfigRead.from_model(c) for c in rows]


@router.post("", response_model=ConfigRead, status_code=201)
def create_config(
    body: ConfigCreate,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> ConfigRead:
    _require_credential(session, body.credential_id, user)
    channels = _resolve_channels(session, body.channel_ids, user, user.id)

    data = body.model_dump(exclude={"channel_ids"})
    cfg = InstanceConfig(**data, owner_id=user.id)
    cfg.notification_channels = channels
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    logger.info("InstanceConfig created", extra={"config_id": cfg.id})
    return ConfigRead.from_model(cfg)


@router.put("/{config_id}", response_model=ConfigRead)
def update_config(
    config_id: int,
    body: ConfigUpdate,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> ConfigRead:
    cfg = _get_or_404(session, config_id, user)
    _require_credential(session, body.credential_id, user)
    channels = _resolve_channels(session, body.channel_ids, user, cfg.owner_id)

    for field, value in body.model_dump(exclude={"channel_ids"}).items():
        setattr(cfg, field, value)
    cfg.notification_channels = channels
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    logger.info("InstanceConfig updated", extra={"config_id": cfg.id})
    return ConfigRead.from_model(cfg)


@router.delete("/{config_id}", status_code=204)
def delete_config(
    config_id: int,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> Response:
    cfg = _get_or_404(session, config_id, user)
    session.delete(cfg)
    session.commit()
    logger.info("InstanceConfig deleted", extra={"config_id": config_id})
    return Response(status_code=204)


@router.post("/{config_id}/toggle", response_model=ConfigRead)
def toggle_config(
    config_id: int,
    user: User = Depends(require_login),
    session: Session = Depends(get_session),
) -> ConfigRead:
    cfg = _get_or_404(session, config_id, user)
    cfg.enabled = not cfg.enabled
    cfg.updated_at = datetime.utcnow()
    session.add(cfg)
    session.commit()
    session.refresh(cfg)
    logger.info(
        "InstanceConfig toggled enabled=%s",
        cfg.enabled,
        extra={"config_id": cfg.id},
    )
    return ConfigRead.from_model(cfg)
