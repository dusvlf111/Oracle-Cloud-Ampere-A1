# 결과보고서: tasks-prd-push6

> 완료일: 2026-06-03
> 브랜치: `push6-worker-dashboard` (push5-web-ui HEAD 에서 분기)
> 범위: 다중 계정 동시 폴링 워커(supervisor + per-config task + per-credential semaphore) + 성공/에러 다중 채널 알림 + 대시보드 + 부트스트랩 문서 — **MVP(Push 1~6) 전체 완료**

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 6.1 config_task 폴링 루프 + 세마포어 | server | ✅ | e84295c |
| 6.2 에러 처리 + 다중 채널 알림 연동 | server | ✅ | 50c5ec9 |
| 6.3 poller supervisor + lifespan 통합 | server | ✅ | 63af312 |
| 6.4 web 시도 이력 엔티티 (배지 + react-table) | web | ✅ | 99771cb |
| 6.5 web 대시보드 페이지 + header/sidebar 위젯 | web | ✅ | 15470a9 |
| 6.6 부트스트랩 문서 + 최종 검증 | push-lead | ✅ | (본 커밋) |

> 실행 전략: Task 서브에이전트 도구 미사용 환경이라 단일 에이전트로 순차 직접 구현
> (server 체인 6.1→6.2→6.3, web 체인 6.4→6.5, 배리어 6.6). 6.1·6.2 는 동일 모듈/
> 테스트 파일(`config_task.py` / `test_config_task.py`)로 함께 구현됨.

## 변경 파일

### Server
- `apps/server/src/app/workers/concurrency.py` (신규) — 전역 + per-credential 세마포어, 순서 고정 `oci_slots`
- `apps/server/src/app/workers/config_task.py` (신규) — `poll_once`/`run_config_task` 폴링 루프
- `apps/server/src/app/workers/poller.py` (신규) — `PollerSupervisor` (spawn/cancel/restart) + `poller_supervisor` 루프
- `apps/server/src/app/services/oci_client.py` — `build_launch_details`/`launch_instance_sync` 추가
- `apps/server/src/app/main.py` — lifespan 에서 poller_supervisor + log_pruner 기동, graceful shutdown
- `apps/server/tests/unit/workers/test_config_task.py` (신규, 8 tests)
- `apps/server/tests/integration/test_poller_supervisor.py` (신규, 6 tests) + `tests/integration/__init__.py`

### Web
- `apps/web/src/entities/attempt/` (신규) — `AttemptStatusBadge`, `AttemptsTable`(@tanstack/react-table), api/model + 테스트 2종(8 tests)
- `apps/web/src/widgets/sidebar/` (신규) — `Sidebar` 네비게이션 + 테스트
- `apps/web/src/widgets/header/` (신규) — `Header` + LogoutButton + 테스트
- `apps/web/src/pages/dashboard/` (신규) — `DashboardPage` (카운트 카드/성공 카드/시도 테이블) + 테스트
- `apps/web/app/(protected)/layout.tsx` — sidebar+header chrome
- `apps/web/app/(protected)/page.tsx` — → DashboardPage
- `apps/web/package.json` / `pnpm-lock.yaml` — `@tanstack/react-table` 추가

### Docs
- `README.md` — 부트스트랩 절차(cli hash→APP_SECRET→compose up), 외부 차단 curl 검증, 정적 검증 안내, OSS 표 `@tanstack/react-table` 추가
- `.env.example` — PRD §10 과 일치(기존 완비, 변경 없음)

## 테스트 결과

- **서버 (pytest)**: 155 passed, 커버리지 **93%**
  - services: notifier 96~100%, oci_client 94%, crypto 88%, auth 100%
  - workers: concurrency 100%, poller 94%, config_task 85%, log_pruner 84% → 모두 80%+
- **웹 (vitest)**: 84 passed (29 files), 커버리지 **All files 91.5%**
  - entities/attempt ui 100%, widgets/sidebar 100%, widgets/header 100%, pages/dashboard 98.5%
  - features 대부분 90%+ (기존 자산 포함)
- 루트 `pnpm test` (server + web) 전체 통과
- `pnpm lint` (eslint-plugin-boundaries / FSD 레이어 규칙) 통과
- 정적 검증: `node scripts/verify-compose.mjs` OK (server 호스트 미노출 + expose:8000, web :3000), `verify-workspace.mjs` OK

## PRD §13 성공 기준 점검표

| 기준 | 상태 | 비고 |
|---|---|---|
| `docker compose up -d` 한 줄 기동 | ⚠️ 정적 | docker 미설치 — compose 구성 정적 검증으로 대체 |
| Next.js 에서 자격증명/설정 등록 | ✅ | Push 4~5 페이지 + 본 Push 대시보드 |
| Swagger 직접 호출 | ✅ | FastAPI 자동 docs (기존) |
| `pnpm gen:api` Orval 재생성 | ✅ | attempts 훅 포함, 엔티티 재노출 |
| 워커 OCI 호출 + 시도 이력 누적 | ✅ | config_task → Attempt 기록 (OCI mock 테스트) |
| 다중 계정/config 동시 폴링, 동일 계정 직렬·계정 간 병렬 | ✅ | 세마포어 테스트(같은 cred max_active=1, 다른 cred=2) + supervisor 다중 시나리오 |
| 가용성 확보 시 자동 생성 + 연결된 모든 채널 알림 | ✅ | 성공 시 fan_out 전 채널 병렬, 1채널 실패 격리 테스트 |
| ntfy `{server}/{topic}` Title/Priority/Tags 발송 | ✅ | ntfy 모듈(기존) + kind→priority(success5/warning4) 매핑 |
| `/logs` 실시간+과거 + 필터/검색 | ✅ | Push 3 자산 (변경 없음) |
| 미인증 시 `/login` 리다이렉트, 5회 실패 rate limit | ✅ | Push 2 자산 (middleware + slowapi) |
| 컨테이너 재시작 후 보존 | ✅ | SQLite 볼륨 마운트 (compose 구성) |
| 외부 차단: `curl :8000/healthz` 실패 / `:3000/api/healthz` 성공 | ⚠️ 정적 | docker 미설치 — verify-compose.mjs 로 ports/expose 정적 검증 |
| FSD 규칙: `pnpm lint` 레이어 위반 감지 | ✅ | lint 통과 + `lint:fsd-fixture` 위반 감지 유지 |
| `pnpm test` 서버 70%+ / 웹 50%+ | ✅ | 서버 93% / 웹 91.5% |

## 새로 만든 스킬

- 없음 (반복 패턴이 기존 스킬 `oci-sdk`/`notification-channels`/`fastapi-patterns`/`python-testing`/`fsd-architecture`/`web-testing` 범위 내에서 처리됨)

## 이슈 및 특이사항

- **docker 미설치**: 라이브 `docker compose up` / curl 외부 차단 검증 불가 → `scripts/verify-compose.mjs` 정적 검증으로 대체(지시사항 명시 사항). README 에도 동일 기재.
- **6.1/6.2 통합 구현**: 폴링 루프와 에러/알림 처리는 단일 모듈에서 응집도가 높아 한 파일로 구현하고 테스트도 한 파일에 동봉. 두 작업 모두 T1/T2 충족.
- **OCI 호출 전면 모킹**: `launch_instance_sync` 를 monkeypatch 하여 실 OCI 호출 없음. ServiceError(status/code) 로 out_of_capacity/429/auth 분기 검증.
- **동시성 검증**: per-credential 세마포어가 같은 credential 의 두 config launch 를 직렬화(`max_active==1`), 다른 credential 은 병렬(`max_active==2`) — `time.sleep` 블로킹 + `to_thread` 로 실제 동시 실행 측정.
- **graceful shutdown**: supervisor 취소 시 자식 config task `CancelledError` 전파 + await 확인 (`test_supervisor_loop_cancellation_propagates`).
- **OSS 신규 도입**: `@tanstack/react-table` (MIT, headless, OSS 매트릭스 기재 항목) — 오프라인 pnpm 캐시로 설치 성공, README OSS 표 갱신.
- `git push` 미수행(금지 준수). 워킹트리 todo 수정분 stash 미수행.

## 미완료 항목

- 없음. 6.1~6.6 모든 하위 작업 [x] 완료.
