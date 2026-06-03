---
name: notification-channels
description: |
  Discord/Slack/Telegram/ntfy 알림 발송 패턴. "알림 보내", "webhook", "ntfy 발송", "Discord 메시지", "Slack notify", "Telegram bot", "채널 추가" 등에서 트리거.
  본 프로젝트는 `NotificationChannel` 모델에 채널별 config_enc 저장. ntfy 는 self-host 지원 (예: ntfy.supabin.com). 모든 채널 httpx 로 통일 발송.
---

# Notification Channels

본 프로젝트 4채널 (Discord/Slack/Telegram/ntfy) 발송 패턴.

## 공용 페이로드

```python
# app/services/notifier/types.py
from pydantic import BaseModel
from enum import Enum

class NotifyKind(str, Enum):
    SUCCESS = "success"     # 인스턴스 생성 성공
    WARNING = "warning"     # 인증 오류, 자동 비활성화
    ERROR = "error"         # 발송 실패
    INFO = "info"

class NotificationPayload(BaseModel):
    kind: NotifyKind
    title: str
    body: str
    tags: list[str] = []
    metadata: dict = {}     # config_id, attempt_id 등
```

## 디스패치

```python
# app/services/notifier/__init__.py
from app.services.notifier import discord, slack, telegram, ntfy
from app.services.crypto import decrypt_json

DISPATCH = {
    "discord": discord.send,
    "slack": slack.send,
    "telegram": telegram.send,
    "ntfy": ntfy.send,
}

async def send(channel: NotificationChannel, payload: NotificationPayload) -> None:
    cfg = decrypt_json(channel.config_enc)
    fn = DISPATCH[channel.type]
    await fn(cfg, payload)
```

## 다중 채널 병렬

```python
async def fan_out(channels: list[NotificationChannel], payload: NotificationPayload) -> list[BaseException | None]:
    results = await asyncio.gather(
        *[send(ch, payload) for ch in channels if ch.enabled],
        return_exceptions=True,
    )
    for ch, r in zip(channels, results):
        if isinstance(r, Exception):
            logger.error("알림 발송 실패", extra={"channel_id": ch.id, "channel_type": ch.type}, exc_info=r)
    return results
```

## Discord

```python
# app/services/notifier/discord.py
import httpx

COLOR = {"success": 0x22c55e, "warning": 0xf59e0b, "error": 0xef4444, "info": 0x3b82f6}

async def send(cfg: dict, payload: NotificationPayload) -> None:
    embed = {
        "title": payload.title,
        "description": payload.body,
        "color": COLOR.get(payload.kind, 0x6b7280),
    }
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(cfg["webhook_url"], json={"embeds": [embed]})
        r.raise_for_status()
```

## Slack

```python
async def send(cfg: dict, payload: NotificationPayload) -> None:
    blocks = [
        {"type": "header", "text": {"type": "plain_text", "text": payload.title}},
        {"type": "section", "text": {"type": "mrkdwn", "text": payload.body}},
    ]
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(cfg["webhook_url"], json={"blocks": blocks})
        r.raise_for_status()
```

## Telegram

```python
async def send(cfg: dict, payload: NotificationPayload) -> None:
    text = f"<b>{escape(payload.title)}</b>\n{escape(payload.body)}"
    url = f"https://api.telegram.org/bot{cfg['bot_token']}/sendMessage"
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(url, json={"chat_id": cfg["chat_id"], "text": text, "parse_mode": "HTML"})
        r.raise_for_status()
```

## ntfy (self-host 지원)

```python
# app/services/notifier/ntfy.py
PRIORITY_BY_KIND = {"success": 5, "warning": 4, "error": 4, "info": 3}

async def send(cfg: dict, payload: NotificationPayload) -> None:
    headers = {
        "Title": payload.title,
        "Priority": str(cfg.get("priority") or PRIORITY_BY_KIND.get(payload.kind, 3)),
    }
    tags = payload.tags + cfg.get("tags", [])
    if tags:
        headers["Tags"] = ",".join(tags)
    if token := cfg.get("token"):
        headers["Authorization"] = f"Bearer {token}"

    url = f"{cfg['server_url'].rstrip('/')}/{cfg['topic']}"
    async with httpx.AsyncClient(timeout=5.0) as c:
        r = await c.post(url, content=payload.body.encode("utf-8"), headers=headers)
        r.raise_for_status()
```

**self-host 주의**:
- `server_url` 에 protocol 포함 (`https://ntfy.supabin.com`)
- 인증이 있는 서버는 `Authorization: Bearer {token}` 필수
- HTTPS 가 아닌 경우 거부 (개발 시만 명시적 허용)

## 테스트 발송 (API)

```python
@router.post("/{channel_id}/test")
async def test_channel(channel_id: int, session = Depends(get_session)) -> dict:
    ch = session.get(NotificationChannel, channel_id)
    if not ch:
        raise AppError("channel_not_found", 404, "...")
    payload = NotificationPayload(
        kind="info",
        title="테스트 알림",
        body=f"채널 '{ch.name}' 발송 테스트입니다.",
        tags=["test"],
    )
    try:
        await send(ch, payload)
        return {"ok": True}
    except Exception as e:
        return {"ok": False, "error": str(e)}
```

## 재시도

```python
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=0.5, min=0.5, max=4),
    retry=retry_if_exception_type((httpx.TimeoutException, httpx.NetworkError)),
)
async def send_with_retry(cfg, payload):
    await send_impl(cfg, payload)
```

서버 5xx 는 재시도, 4xx 는 즉시 실패 (사용자 설정 오류).

## 발송 시점 매트릭스 (PRD §7.5.3 동기화)

| 이벤트 | kind | tags | 발송 |
|---|---|---|---|
| 인스턴스 생성 성공 | success | ["rocket", "oci"] | 필수 |
| 인증 오류로 비활성화 | warning | ["warning"] | 필수 |
| `OutOfCapacity` (개별) | — | — | **안 함** (노이즈) |
| 5분 이상 rate_limited | warning | ["throttle"] | v0.2 |

## 안티패턴

- webhook URL 평문 저장 → AES-GCM 암호화 (`config_enc`)
- 모든 채널 같은 메시지 — Discord 마크다운/Slack 블록/ntfy 헤더 형식 차이 무시
- 발송 실패 시 전체 워커 중단 — 실패는 ERROR 로그만, 워커 계속
- 단일 채널 사용 강제 — 사용자가 여러 채널 원할 수 있음 (M:N 관계)
- "알림 폭주" — `OutOfCapacity` 매번 알림 안 함, 진짜 의미 있는 이벤트만
