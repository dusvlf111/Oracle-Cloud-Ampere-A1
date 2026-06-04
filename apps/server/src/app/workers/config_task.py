"""Per-config polling loop (PRD §7.3.1, §7.5.3, §9.2; skills: oci-sdk, notification-channels).

One ``asyncio.Task`` runs :func:`run_config_task` for each enabled
``InstanceConfig``. Each iteration:

1. acquires the global + per-credential OCI slots (:mod:`app.workers.concurrency`)
   — same account serialised, different accounts parallel;
2. calls ``launch_instance`` via ``asyncio.to_thread`` (sync SDK);
3. records an :class:`~app.db.models.Attempt` and reacts by status:

   ===================  ============================================  ==========
   outcome              action                                        notify
   ===================  ============================================  ==========
   success              Attempt(success) + enabled=False + stop       priority 5
   out_of_capacity      Attempt(out_of_capacity), keep retrying       none (noise)
   rate_limited (429)   tenacity backoff + Attempt(rate_limited),     none
                        extend next sleep
   auth_error           Attempt(auth_error) + enabled=False + stop    priority 4
   config_error         Attempt(config_error) + enabled=False + stop  priority 4
   other_error          Attempt(other_error), keep retrying           none
   ===================  ============================================  ==========

``config_error`` (hardening §2) is a permanent malformed-request error: OCI
400/404 (``CannotParseRequest`` / ``InvalidParameter`` / ``NotAuthorizedOrNotFound``).
Retrying can never succeed, so the worker disables the config and notifies
instead of looping forever.

Sessions are opened per task (PRD §9.2). Every log call carries the
``config_id``/``credential_id``/``attempt_id`` context (PRD §7.3.2).
"""

from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from sqlalchemy import func
from sqlalchemy.engine import Engine
from sqlmodel import Session, select
from tenacity import (
    retry,
    retry_if_exception,
    stop_after_attempt,
    wait_exponential,
)

from app.db.models import Attempt, InstanceConfig, NotificationChannel, OciCredential
from app.services import oci_client
from app.services.crypto import decrypt, fernet_decrypt
from app.services.notifier import fan_out
from app.services.notifier.types import NotificationPayload, NotifyKind
from app.workers.concurrency import oci_slots

logger = logging.getLogger("app.workers.config_task")

# Global floor on the polling interval so a misconfigured `retry_interval_sec`
# (e.g. 0) can never spin the loop (PRD open-question #7).
MIN_INTERVAL_SEC = 0.2

# Multiply the next sleep by this when a 429 rate-limit is hit (PRD §7.3.1).
RATE_LIMIT_BACKOFF_FACTOR = 3.0


class _RateLimited(Exception):
    """Internal marker so tenacity retries only on 429 within one attempt."""


def _is_rate_limited(exc: BaseException) -> bool:
    return isinstance(exc, _RateLimited)


# initial try + 2 retries with exponential backoff on 429 (PRD §7.3.1).
_rate_limit_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.2, min=0.2, max=2),
    retry=retry_if_exception(_is_rate_limited),
    reraise=True,
)


def _load_passphrase(cred: OciCredential) -> str | None:
    if not cred.passphrase_enc:
        return None
    return decrypt(cred.passphrase_enc).decode("utf-8")


def _build_payload(
    kind: NotifyKind,
    title: str,
    *,
    config: InstanceConfig,
    credential: OciCredential,
    instance_ocid: str | None = None,
    error: str | None = None,
) -> NotificationPayload:
    """Render the common notification body (PRD §7.5.6)."""
    ts = datetime.now(tz=timezone.utc).isoformat()
    lines = [
        f"Config: {config.name}",
        f"계정: {credential.name}",
        f"시각: {ts}",
    ]
    if instance_ocid:
        lines.append(f"인스턴스 OCID: {instance_ocid}")
    if error:
        lines.append(f"오류: {error}")
    tag = {
        NotifyKind.SUCCESS: "success",
        NotifyKind.WARNING: "warning",
        NotifyKind.ERROR: "error",
    }.get(kind, "info")
    return NotificationPayload(
        kind=kind,
        title=title,
        body="\n".join(lines),
        tags=[tag],
        metadata={"config_id": config.id, "credential_id": credential.id},
    )


def _channels_for(session: Session, config: InstanceConfig) -> list[NotificationChannel]:
    """Eagerly load the config's linked channels inside the session."""
    cfg = session.get(InstanceConfig, config.id)
    if cfg is None:
        return []
    return list(cfg.notification_channels)


async def _notify(
    session: Session,
    config: InstanceConfig,
    credential: OciCredential,
    payload: NotificationPayload,
) -> None:
    channels = _channels_for(session, config)
    if not channels:
        return
    await fan_out(channels, payload)


def _record_attempt(
    session: Session,
    *,
    config_id: int,
    status: str,
    message: str | None = None,
    instance_ocid: str | None = None,
    duration_ms: int | None = None,
) -> Attempt:
    attempt = Attempt(
        config_id=config_id,
        status=status,
        message=message,
        instance_ocid=instance_ocid,
        duration_ms=duration_ms,
    )
    session.add(attempt)
    session.commit()
    session.refresh(attempt)
    return attempt


def _disable_config(session: Session, config_id: int) -> None:
    cfg = session.get(InstanceConfig, config_id)
    if cfg is not None:
        cfg.enabled = False
        cfg.updated_at = datetime.now(tz=timezone.utc)
        session.add(cfg)
        session.commit()


async def _one_launch(config: InstanceConfig, cred: OciCredential, passphrase: str | None) -> str:
    """A single OCI launch attempt with 429 backoff. Returns the instance OCID.

    Raises ``_RateLimited`` (after exhausting tenacity retries) or the original
    OCI exception for the caller to classify.
    """
    cfg_dict = {
        "id": cred.id,
        "tenancy_ocid": cred.tenancy_ocid,
        "user_ocid": cred.user_ocid,
        "fingerprint": cred.fingerprint,
        "region": cred.region,
    }
    # Decrypt the PEM into memory only (never logged / written to disk).
    key_content = fernet_decrypt(cred.private_key_enc) if cred.private_key_enc else ""
    oci_config = oci_client.build_config(
        cfg_dict, key_content=key_content, passphrase=passphrase
    )
    details = oci_client.build_launch_details(config, cred.tenancy_ocid)

    @_rate_limit_retry
    async def _attempt() -> str:
        try:
            return await asyncio.to_thread(
                oci_client.launch_instance_sync, oci_config, details
            )
        except Exception as exc:  # noqa: BLE001
            status, _msg = oci_client.classify_error(exc)
            if status == oci_client.RATE_LIMITED:
                raise _RateLimited() from exc
            raise

    return await _attempt()


async def poll_once(
    engine: Engine,
    config_id: int,
) -> tuple[str, float]:
    """Run one polling iteration in its own session.

    Returns ``(status, sleep_multiplier)`` — the worker loop stops on
    ``success``/``auth_error`` and sleeps ``retry_interval * multiplier``
    otherwise.
    """
    with Session(engine) as session:
        config = session.get(InstanceConfig, config_id)
        if config is None or not config.enabled:
            return "stopped", 1.0
        credential = session.get(OciCredential, config.credential_id)
        if credential is None:
            logger.error(
                "config %s has no credential %s — disabling",
                config_id,
                config.credential_id if config else None,
                extra={"config_id": config_id, "credential_id": config.credential_id},
            )
            _disable_config(session, config_id)
            return "auth_error", 1.0

        passphrase = _load_passphrase(credential)
        cred_id = credential.id

        # max_attempts cap (PRD §7.2): when set, stop polling once the config
        # has accumulated that many attempts — disable + notify, no new launch.
        if config.max_attempts is not None:
            made = session.exec(
                select(func.count())
                .select_from(Attempt)
                .where(Attempt.config_id == config_id)
            ).one()
            if made >= config.max_attempts:
                logger.warning(
                    "최대 시도 횟수(%s) 도달 — config 자동 비활성화",
                    config.max_attempts,
                    extra={"config_id": config_id, "credential_id": cred_id},
                )
                _disable_config(session, config_id)
                payload = _build_payload(
                    NotifyKind.WARNING,
                    f"⚠️ 최대 시도 횟수({config.max_attempts}회) 도달로 자동 중지",
                    config=config,
                    credential=credential,
                    error=f"attempts={made}/{config.max_attempts}",
                )
                await _notify(session, config, credential, payload)
                return "max_attempts", 1.0

        async with oci_slots(cred_id):
            started = time.monotonic()
            logger.info(
                "OCI launch_instance 시도",
                extra={"config_id": config_id, "credential_id": cred_id},
            )
            try:
                instance_ocid = await _one_launch(config, credential, passphrase)
            except _RateLimited as exc:
                duration_ms = int((time.monotonic() - started) * 1000)
                _, msg = oci_client.classify_error(exc.__cause__ or exc)
                _record_attempt(
                    session,
                    config_id=config_id,
                    status=oci_client.RATE_LIMITED,
                    message=msg,
                    duration_ms=duration_ms,
                )
                logger.warning(
                    "OCI rate limited — backing off",
                    extra={"config_id": config_id, "credential_id": cred_id},
                )
                return oci_client.RATE_LIMITED, RATE_LIMIT_BACKOFF_FACTOR
            except Exception as exc:  # noqa: BLE001
                duration_ms = int((time.monotonic() - started) * 1000)
                status, msg = oci_client.classify_error(exc)
                attempt = _record_attempt(
                    session,
                    config_id=config_id,
                    status=status,
                    message=msg,
                    duration_ms=duration_ms,
                )
                if status == oci_client.OUT_OF_CAPACITY:
                    logger.info(
                        "OutOfCapacity — 재시도 예정 (무알림)",
                        extra={
                            "config_id": config_id,
                            "credential_id": cred_id,
                            "attempt_id": attempt.id,
                        },
                    )
                    return status, 1.0
                if status == oci_client.AUTH_ERROR:
                    logger.error(
                        "OCI 인증/권한 오류로 config 자동 비활성화",
                        extra={
                            "config_id": config_id,
                            "credential_id": cred_id,
                            "attempt_id": attempt.id,
                        },
                    )
                    _disable_config(session, config_id)
                    payload = _build_payload(
                        NotifyKind.WARNING,
                        "⚠️ OCI 인증 오류",
                        config=config,
                        credential=credential,
                        error=msg,
                    )
                    await _notify(session, config, credential, payload)
                    return status, 1.0
                if status == oci_client.CONFIG_ERROR:
                    # Permanent client error (malformed request) — retrying can
                    # never succeed and only burns rate-limit budget. Disable the
                    # config and notify, same priority as auth_error (hardening §2).
                    logger.error(
                        "OCI 설정 오류(영구)로 config 자동 비활성화: %s",
                        msg,
                        extra={
                            "config_id": config_id,
                            "credential_id": cred_id,
                            "attempt_id": attempt.id,
                        },
                    )
                    _disable_config(session, config_id)
                    payload = _build_payload(
                        NotifyKind.WARNING,
                        f"⚠️ 설정 오류로 자동 중지: {msg}",
                        config=config,
                        credential=credential,
                        error=msg,
                    )
                    await _notify(session, config, credential, payload)
                    return status, 1.0
                # other_error — record and keep retrying.
                logger.warning(
                    "OCI 호출 실패 (기타) — 재시도 예정: %s",
                    msg,
                    extra={
                        "config_id": config_id,
                        "credential_id": cred_id,
                        "attempt_id": attempt.id,
                    },
                )
                return status, 1.0

            # success
            duration_ms = int((time.monotonic() - started) * 1000)
            attempt = _record_attempt(
                session,
                config_id=config_id,
                status="success",
                instance_ocid=instance_ocid,
                duration_ms=duration_ms,
            )
            logger.info(
                "OCI 인스턴스 생성 성공 — config 비활성화",
                extra={
                    "config_id": config_id,
                    "credential_id": cred_id,
                    "attempt_id": attempt.id,
                },
            )
            _disable_config(session, config_id)
            payload = _build_payload(
                NotifyKind.SUCCESS,
                "✅ OCI 인스턴스 생성 성공",
                config=config,
                credential=credential,
                instance_ocid=instance_ocid,
            )
            await _notify(session, config, credential, payload)
            return "success", 1.0


async def run_config_task(engine: Engine, config_id: int) -> None:
    """Poll until success / auth error / cancellation (PRD §7.3.1).

    Restart semantics (task 8.2): the rate-limit backoff multiplier and the
    tenacity retry counter are *local* to this coroutine — they are never
    persisted. On a process restart the supervisor re-spawns a fresh task for
    every still-``enabled`` config, so any prior ``rate_limited`` backoff is
    discarded and the loop retries immediately. Only the durable ``enabled``
    flag decides whether a config resumes.
    """
    logger.info("config task 시작", extra={"config_id": config_id})
    try:
        while True:
            status, multiplier = await poll_once(engine, config_id)
            if status in {
                "success",
                "auth_error",
                "config_error",
                "max_attempts",
                "stopped",
            }:
                logger.info(
                    "config task 종료 status=%s",
                    status,
                    extra={"config_id": config_id},
                )
                return
            # Re-read the (possibly updated) interval each loop.
            with Session(engine) as s:
                cfg = s.get(InstanceConfig, config_id)
                interval = cfg.retry_interval_sec if cfg else 60
            sleep_for = max(interval * multiplier, MIN_INTERVAL_SEC)
            await asyncio.sleep(sleep_for)
    except asyncio.CancelledError:
        logger.info("config task 취소됨", extra={"config_id": config_id})
        raise
