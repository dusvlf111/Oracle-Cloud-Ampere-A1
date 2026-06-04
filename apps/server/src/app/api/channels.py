"""Notification channel CRUD + test-send API (PRD §7.5.2, §8).

GET    /api/channels          — list (sensitive fields masked)
POST   /api/channels          — create (type-validated config, AES-encrypted)
PUT    /api/channels/{id}     — update
DELETE /api/channels/{id}     — delete, 204
POST   /api/channels/{id}/test — send a test message ({ok, error?}, always 200)

Channel configs are stored AES-256-GCM encrypted in ``config_enc``; responses
mask tokens / webhook URLs. Every route requires an authenticated session.
"""

from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, Response
from sqlmodel import Session, select

from app.api.deps import AppError, require_login
from app.db.models import NotificationChannel
from app.db.session import get_session
from app.schemas.channel import (
    ChannelCreate,
    ChannelRead,
    ChannelUpdate,
    TestSendResponse,
)
from app.services import notifier
from app.services.crypto import decrypt_json, encrypt_json
from app.services.notifier.types import NotificationPayload, NotifyKind

logger = logging.getLogger("app.api.channels")

router = APIRouter(prefix="/api/channels", tags=["channels"])


def _get_or_404(session: Session, channel_id: int) -> NotificationChannel:
    ch = session.get(NotificationChannel, channel_id)
    if ch is None:
        raise AppError(
            "channel_not_found",
            404,
            f"NotificationChannel id={channel_id} not found",
            {"channel_id": channel_id},
        )
    return ch


# Sensitive config fields per channel type. On update, a blank or masked
# (``***...``) value for one of these means "keep the existing stored secret"
# so the masked GET echo can be PUT back without corrupting the secret.
_SENSITIVE_FIELDS: dict[str, tuple[str, ...]] = {
    "discord": ("webhook_url",),
    "slack": ("webhook_url",),
    "telegram": ("bot_token",),
    "ntfy": ("token",),
}


def _is_unchanged_secret(value: object) -> bool:
    """A blank or masked (``***...``) value means the client kept the secret."""
    if value is None:
        return True
    if isinstance(value, str):
        stripped = value.strip()
        return stripped == "" or stripped.startswith("***")
    return False


def _merge_kept_secrets(
    channel_type: str, new_cfg: dict, existing_cfg: dict
) -> dict:
    """Preserve existing secrets when the incoming value is blank/masked.

    Implements the "변경 시에만 입력" behaviour: when editing a channel the web
    form shows masked secrets; submitting without retyping (blank or the
    ``***...`` echo) must keep the stored secret rather than overwrite it.
    """
    merged = dict(new_cfg)
    for field in _SENSITIVE_FIELDS.get(channel_type, ()):
        if _is_unchanged_secret(merged.get(field)) and field in existing_cfg:
            merged[field] = existing_cfg[field]
    return merged


def _validate_type_match(body: ChannelCreate | ChannelUpdate) -> dict:
    """Ensure body.type matches the discriminated config.type; return cfg dict."""
    cfg = body.config.model_dump()
    if cfg.get("type") != body.type:
        raise AppError(
            "validation_error",
            422,
            f"config.type '{cfg.get('type')}' does not match channel type '{body.type}'",
            {"type": body.type, "config_type": cfg.get("type")},
        )
    # Drop the redundant discriminator before persisting.
    cfg.pop("type", None)
    return cfg


@router.get("", response_model=list[ChannelRead])
def list_channels(
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> list[ChannelRead]:
    rows = session.exec(
        select(NotificationChannel).order_by(NotificationChannel.id)
    ).all()
    return [ChannelRead.from_model(c, decrypt_json(c.config_enc)) for c in rows]


@router.post("", response_model=ChannelRead, status_code=201)
def create_channel(
    body: ChannelCreate,
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> ChannelRead:
    cfg = _validate_type_match(body)
    ch = NotificationChannel(
        name=body.name,
        type=body.type,
        enabled=body.enabled,
        config_enc=encrypt_json(cfg),
    )
    session.add(ch)
    session.commit()
    session.refresh(ch)
    logger.info("NotificationChannel created", extra={"channel_id": ch.id})
    return ChannelRead.from_model(ch, cfg)


@router.put("/{channel_id}", response_model=ChannelRead)
def update_channel(
    channel_id: int,
    body: ChannelUpdate,
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> ChannelRead:
    ch = _get_or_404(session, channel_id)
    cfg = _validate_type_match(body)
    # When the type is unchanged, let blank/masked sensitive fields fall back to
    # the stored secret so the masked GET echo can be PUT back unchanged. If the
    # type changes the old secrets no longer apply, so we take the body as-is.
    if ch.type == body.type:
        existing_cfg = decrypt_json(ch.config_enc)
        cfg = _merge_kept_secrets(body.type, cfg, existing_cfg)
    ch.name = body.name
    ch.type = body.type
    ch.enabled = body.enabled
    ch.config_enc = encrypt_json(cfg)
    ch.updated_at = datetime.utcnow()
    session.add(ch)
    session.commit()
    session.refresh(ch)
    logger.info("NotificationChannel updated", extra={"channel_id": ch.id})
    return ChannelRead.from_model(ch, cfg)


@router.delete("/{channel_id}", status_code=204)
def delete_channel(
    channel_id: int,
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> Response:
    ch = _get_or_404(session, channel_id)
    session.delete(ch)
    session.commit()
    logger.info("NotificationChannel deleted", extra={"channel_id": channel_id})
    return Response(status_code=204)


@router.post("/{channel_id}/test", response_model=TestSendResponse)
async def test_channel(
    channel_id: int,
    _user: str = Depends(require_login),
    session: Session = Depends(get_session),
) -> TestSendResponse:
    ch = _get_or_404(session, channel_id)
    payload = NotificationPayload(
        kind=NotifyKind.INFO,
        title="테스트 알림",
        body=f"채널 '{ch.name}' 발송 테스트입니다.",
        tags=["test"],
    )
    try:
        await notifier.send(ch, payload)
        return TestSendResponse(ok=True)
    except Exception as exc:  # noqa: BLE001 — failures surface as ok=false (200)
        logger.warning(
            "Channel test send failed: %s", exc, extra={"channel_id": ch.id}
        )
        return TestSendResponse(ok=False, error=str(exc))
