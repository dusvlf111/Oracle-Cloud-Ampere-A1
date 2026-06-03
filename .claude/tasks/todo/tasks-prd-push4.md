# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 4

> PRD: `.claude/tasks/prd.md` (§6 데이터 모델, §7.1/7.2/7.5 기능, §8 API, §11 MVP Push 4 서버 파트)
> Push 범위: 서버 도메인 — 모델 6종 + 마이그레이션, AES-256-GCM 암호화, OCI 클라이언트 서비스, 자격증명/설정/채널/시도 API, notifier 4종 (Discord/Slack/Telegram/ntfy) + 테스트 발송
> 상태: 🔲 진행 중

---

### 관련 파일

- `apps/server/src/app/db/models.py` - `OciCredential`, `InstanceConfig`, `NotificationChannel`, `ConfigChannelLink`, `Attempt`, `AppSetting`
- `apps/server/src/app/services/crypto.py` - AES-256-GCM 암복호화 + 마스킹
- `apps/server/src/app/services/oci_client.py` - `asyncio.to_thread` 래핑, verify
- `apps/server/src/app/api/{credentials,configs,channels,attempts}.py` - 라우터
- `apps/server/src/app/schemas/` - `*Create`/`*Update`/`*Read` + 채널 discriminated union
- `apps/server/src/app/services/notifier/` - `__init__`(디스패치), `discord/slack/telegram/ntfy.py`
- `apps/server/tests/` - unit/api 테스트 (OCI mock, pytest-httpx)

---

### 에이전트 실행 전략 (push-lead)

전 작업 `server-worker` 담당 — 단, 파일 영역이 분리되는 두 레인으로 **server-worker 2개 병렬 spawn** 가능:

| 레인 | 작업 | 의존성 |
|---|---|---|
| A (도메인/API) | 4.1 → 4.2 → 4.3 → 4.4 → 4.5 | 4.4 는 4.1+4.2+4.3 필요, 4.5 는 4.1 필요 |
| B (알림) | 4.6 | — (notifier 는 모델/crypto 와 독립 — 복호화된 cfg dict 를 인자로 받음) |
| 합류 | 4.7 | 4.1 + 4.2 + 4.6 (channels API 가 crypto·notifier 사용) |

```
[server-worker A] 4.1 → 4.2 → 4.3 → 4.4 → 4.5 ──┬→ 4.7
[server-worker B] 4.6 ──────────────────────────┘
```

- **주의**: 두 레인 모두 `services/` 하위지만 파일 비중첩 (`crypto.py`/`oci_client.py` vs `notifier/`) — 충돌 없음. conftest 공용 fixture 변경은 레인 A 가 소유
- 각 T2 커밋 직전 `test-runner` 검증, 4.7.T2 에서 커버리지 70%+ 게이트
- 참조 스킬: `fastapi-patterns`, `python-testing`, `oci-sdk` (4.3/4.4), `notification-channels` (4.6/4.7)

---

## 작업

- [ ] 4.0 서버 도메인 API + 알림 채널 (Push 4)
    - [x] 4.1 도메인 모델 + 마이그레이션 — `OciCredential`/`InstanceConfig`/`NotificationChannel`/`ConfigChannelLink`(m2m)/`Attempt`/`AppSetting` SQLModel 정의 (PRD §6) + Alembic revision
        - [x] 4.1.T1 pytest 테스트 작성 — `tests/unit/db/test_models.py` (관계 탐색: credential→configs, config↔channels m2m, attempt→config; polyfactory 팩토리 정의)
        - [x] 4.1.T2 `pytest -q tests/unit/db/test_models.py` + `alembic upgrade head` 실행 및 검증
    - [x] 4.2 crypto 서비스 — `services/crypto.py` (`APP_SECRET` 에서 AES-256-GCM 키 도출, encrypt/decrypt JSON), 마스킹 유틸 (`***` + 마지막 4자, OCID/fingerprint 마스킹)
        - [x] 4.2.T1 pytest 테스트 작성 — `tests/unit/services/test_crypto.py` (암복호화 라운드트립, 변조 시 복호화 실패, 마스킹 형식)
        - [x] 4.2.T2 `pytest -q tests/unit/services/test_crypto.py` 실행 및 검증
    - [x] 4.3 OCI 클라이언트 서비스 — `services/oci_client.py` (자격증명 dict → oci config 구성, `asyncio.to_thread` 래핑, `ListAvailabilityDomains` 호출 verify, OCI 예외 → 도메인 분류: auth_error/out_of_capacity/rate_limited/other)
        - [x] 4.3.T1 pytest 테스트 작성 — `tests/unit/services/test_oci_client.py` (oci SDK mock: verify 성공/실패, 예외 분류 매핑), conftest 에 `oci_mock` fixture 추가
        - [x] 4.3.T2 `pytest -q tests/unit/services/test_oci_client.py` 실행 및 검증
    - [x] 4.4 credentials API — `POST /api/credentials` (multipart: form + private key 파일 → `/data/keys/{id}.pem` chmod 600, passphrase 암호화), `GET` 목록 (마스킹), `POST /{id}/verify` (`{ok, error?}`), `DELETE` 204 + 키 파일 삭제, 에러 코드 `credential_not_found`/`oci_auth_error` (PRD §8)
        - [x] 4.4.T1 pytest 테스트 작성 — `tests/api/test_credentials.py` (multipart 생성→파일 권한 600, 응답 마스킹, verify mock 성공/실패, 삭제, 미인증 401)
        - [x] 4.4.T2 `pytest -q tests/api/test_credentials.py` 실행 및 검증
    - [x] 4.5 configs API — CRUD (`GET`/`POST`/`PUT`/`DELETE`) + `POST /{id}/toggle`, `channel_ids` m2m 갱신, `*Create`/`*Update` 스키마로 read-only 필드 보호, `config_not_found` 에러, 라우터 태그 `configs`
        - [x] 4.5.T1 pytest 테스트 작성 — `tests/api/test_configs.py` (CRUD 전체, channel_ids 연결/갱신, toggle 후 enabled 반전, 존재하지 않는 credential_id 422/404)
        - [x] 4.5.T2 `pytest -q tests/api/test_configs.py` 실행 및 검증
    - [ ] 4.6 notifier 모듈 — `services/notifier/` (`NotificationPayload{title,body,tags}` 공통 포맷, `send(channel, payload)` 디스패치, discord embed/slack block/telegram HTML/ntfy 헤더 변환, httpx 타임아웃 5초 + tenacity 재시도 2회, 최종 실패 ERROR 로그만, ntfy self-hosted `server_url` + Bearer 토큰 옵션) (PRD §7.5)
        - [ ] 4.6.T1 pytest 테스트 작성 — `tests/unit/services/test_notifier_*.py` (pytest-httpx: 채널별 요청 포맷/헤더 검증 — ntfy Title/Priority/Tags/Authorization, 재시도 동작, 실패 시 예외 미전파)
        - [ ] 4.6.T2 `pytest -q tests/unit/services/ -k notifier` 실행 및 검증
    - [ ] 4.7 channels + attempts API — channels CRUD (`config_enc` AES 암호화 저장, Pydantic discriminated union 타입 검증, 응답 sensitive 마스킹), `POST /{id}/test` (`{ok, error?}` — 실패도 200), `GET /api/attempts` (config_id/status/limit 쿼리), `channel_not_found` 에러
        - [ ] 4.7.T1 pytest 테스트 작성 — `tests/api/test_channels.py` (타입별 생성/검증 실패 422, 마스킹 응답, 테스트 발송 mock ok/실패), `tests/api/test_attempts.py` (필터 조회)
        - [ ] 4.7.T2 `pytest -q tests/api/test_channels.py tests/api/test_attempts.py` + `pytest -q --cov=app` (커버리지 70%+ 확인) 실행 및 검증
