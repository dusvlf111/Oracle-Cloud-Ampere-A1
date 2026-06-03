# 결과보고서: tasks-prd-push4

> 완료일: 2026-06-03
> 브랜치: `push4-domain-api` (HEAD: `push3-logging` 에서 분기)
> 범위: 서버 도메인 API — 모델 6종 + 마이그레이션, AES-256-GCM 암호화, OCI 클라이언트 서비스, 자격증명/설정/채널/시도 API, notifier 4종(Discord/Slack/Telegram/ntfy) + 테스트 발송
> 실행 형태: 서브에이전트 Task 도구 미사용 → 단일 에이전트 순차 직접 구현 (레인 A 4.1→4.5 → 레인 B 4.6 → 합류 4.7), 커밋 단위/T1·T2 규칙 준수

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 4.1 도메인 모델 6종 + m2m + Alembic | server | ✅ | 5e3764c |
| 4.2 crypto 서비스 (AES-256-GCM + 마스킹) | server | ✅ | afaecb5 |
| 4.3 OCI 클라이언트 서비스 (verify + 예외 분류) | server | ✅ | a34a068 |
| 4.4 credentials API (multipart 업로드 + verify) | server | ✅ | 9d3b98b |
| 4.5 configs API (CRUD + toggle + channel m2m) | server | ✅ | 78de664 |
| 4.6 notifier 4채널 + 디스패치/재시도/팬아웃 | server | ✅ | a683c05 |
| 4.7 channels CRUD(+test) + attempts 조회 API | server | ✅ | 760fb57 |

## 변경 파일

### Server — 신규
- `apps/server/src/app/db/models.py` (전면 작성: OciCredential/InstanceConfig/NotificationChannel/ConfigChannelLink/Attempt/AppSetting/LogEntry)
- `apps/server/alembic/versions/1b9a876eab13_domain_models.py`
- `apps/server/src/app/services/crypto.py`
- `apps/server/src/app/services/oci_client.py`
- `apps/server/src/app/services/notifier/{__init__,types,discord,slack,telegram,ntfy}.py`
- `apps/server/src/app/schemas/{__init__,credential,config,channel}.py`
- `apps/server/src/app/api/{credentials,configs,channels,attempts}.py`

### Server — 수정
- `apps/server/src/app/main.py` (라우터 4종 등록)
- `apps/server/src/app/config.py` (`keys_dir` 설정 추가)
- `apps/server/pyproject.toml` (runtime deps: oci/cryptography/tenacity/httpx/python-multipart)
- `apps/server/tests/conftest.py` (`oci_mock` fixture 추가)

### Tests — 신규
- `tests/unit/db/test_models.py`
- `tests/unit/services/test_crypto.py`
- `tests/unit/services/test_oci_client.py`
- `tests/unit/services/test_notifier_{discord,slack,telegram,ntfy,dispatch}.py`
- `tests/api/test_{credentials,configs,channels,attempts}.py`

### 기타
- `README.md` — OSS Dependencies 표에 cryptography/tenacity/python-multipart/oci 추가

## 테스트 결과

- pytest: **141 passed** (push3 시점 65개 → +76개)
- 커버리지: **94%** (`--cov=app`, 게이트 70%+ 충족; services/notifier·oci_client·crypto 모두 88~100%)
- 외부 IO 전부 모킹: OCI SDK는 `oci_mock` fixture, 알림 발송은 pytest-httpx — 실 OCI/네트워크 호출 0건

## OCI/네트워크 모킹 준수

- `tests/conftest.py::oci_mock` 가 `oci.identity.IdentityClient` 패치 → verify 성공/실패/분류 모두 mock
- notifier·channel test-send 테스트는 `httpx_mock` 으로 가로채기 (`onUnhandledRequest` 미통과 호출은 테스트 실패)

## 이슈 및 해결

1. **SQLModel 관계 초기화 실패** — `from __future__ import annotations` + `Relationship(list["X"])` 조합에서 SQLAlchemy 가 generic 인자를 해석하지 못해 매퍼 초기화 실패. models.py 에서 future-annotations import 를 제거해 해결 (런타임 평가 가능하도록). 다른 모듈은 그대로 유지.
2. **ntfy 비-ASCII Title 헤더 (T3 자동 해결)** — `Title: 성공` 같은 한글 헤더가 httpx 의 ascii 헤더 인코딩에서 `UnicodeEncodeError`. ntfy 가 UTF-8 헤더를 디코드하므로 `_header_value()` 헬퍼로 비-ASCII 값만 UTF-8 bytes 로 전송하도록 수정 (테스트로 round-trip 검증). 실제 발송 가능성을 살린 버그 수정.

## 미완료 항목

- 없음. 4.1~4.7 전부 [x], 4.0 완료.
- (범위 외, Push 5) 워커 supervisor/config_task 가 notifier `fan_out`·oci_client `launch` 을 호출하는 통합은 Push 5 담당. 메타 조회 헬퍼 API(`/api/meta/*`)도 PRD §11 상 Push 4 범위 밖.

## 비고

- `git push` 미수행 (지시 준수). 워킹트리의 `tasks-prd-push5/6.md` 수정분은 stash 없이 그대로 보존, 커밋에 미포함.
- task 파일은 `.claude/tasks/done/` 로 이동 완료.
