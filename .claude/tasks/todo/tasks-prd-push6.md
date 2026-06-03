# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 6

> PRD: `.claude/tasks/prd.md` (§7.3 워커, §7.4 대시보드, §7.5.3 발송 시점, §9.2 동시성, §11 MVP Push 5)
> Push 범위: 다중 계정 동시 폴링 워커 (supervisor + per-config task + per-credential semaphore) + 성공/에러 시 다중 채널 알림 + 대시보드 + 부트스트랩 문서
> 상태: 🔲 진행 중

---

### 관련 파일

- `apps/server/src/app/workers/config_task.py` - config 1개당 폴링 루프
- `apps/server/src/app/workers/poller.py` - supervisor (task spawn/cancel/재시작)
- `apps/server/src/app/main.py` - lifespan 에서 supervisor 기동/graceful shutdown
- `apps/server/tests/unit/workers/test_config_task.py` - 단위 테스트
- `apps/server/tests/integration/test_poller_supervisor.py` - 통합 테스트
- `apps/web/src/entities/attempt/` - 시도 이력 엔티티
- `apps/web/src/widgets/{header,sidebar}/`, `apps/web/src/pages/dashboard/` - 대시보드
- `README.md`, `.env.example` - 부트스트랩 절차

---

### 에이전트 실행 전략 (push-lead)

| 작업 | 담당 | 의존성 |
|---|---|---|
| 6.1 → 6.2 → 6.3 | `server-worker` | 순차 (폴링 루프 → 에러/알림 → supervisor 통합) |
| 6.4 → 6.5 | `web-worker` | Push 5 의 Orval 클라이언트 (attempts 훅) — server 체인과 병렬 |
| 6.6 | push-lead 직접 (문서) + `test-runner` (최종 게이트) | 6.1~6.5 전체 |

```
[server-worker] 6.1 → 6.2 → 6.3 ──┬→ 6.6 (배리어: 문서 + 최종 검증)
[web-worker]    6.4 → 6.5 ────────┘
```

- **병렬**: server 워커 체인(6.1~6.3) ∥ web 대시보드 체인(6.4~6.5)
- 6.3.T1 통합 테스트는 `test-runner` 가 아닌 `server-worker` 가 작성 (도메인 지식 필요), test-runner 는 실행/분석 담당
- 6.6.T2 가 MVP 전체 성공 기준 (PRD §13) 최종 게이트 — 실패 시 test-runner 가 수정 가능하면 직접 수정, 설계 문제는 T3 등록
- 참조 스킬: `fastapi-patterns`, `python-testing`, `oci-sdk`, `notification-channels` / `fsd-architecture`, `web-testing`

---

## 작업

- [ ] 6.0 폴링 워커 + 대시보드 (Push 6)
    - [x] 6.1 config_task 폴링 루프 — `workers/config_task.py` (자체 `retry_interval_sec` sleep + 전역 최소 200ms 가드, `credential_semaphores[credential_id]` (기본 max=1, env `OCI_PER_CREDENTIAL_MAX`) + 전역 `Semaphore(OCI_MAX_CONCURRENT)`, `asyncio.to_thread` launch_instance, 성공 → `Attempt(success)` + `enabled=False` + 자가 종료, `OutOfCapacity` → `Attempt(out_of_capacity)` 기록만, task 단위 세션 분리, 로그 컨텍스트 `extra=` 동봉)
        - [x] 6.1.T1 pytest 테스트 작성 — `tests/unit/workers/test_config_task.py` (OCI mock: 성공 시 Attempt+비활성화+종료, 용량 부족 시 기록 후 재시도 sleep, 같은 credential 2-task 직렬화 / 다른 credential 병렬 실행 검증)
        - [x] 6.1.T2 `pytest -q tests/unit/workers/test_config_task.py` 실행 및 검증
    - [x] 6.2 에러 처리 + 알림 연동 — 429 → tenacity 지수 백오프 + `rate_limited` 기록 + sleep 연장, 인증/권한 오류 → `auth_error` + `enabled=False` + 인증 오류 알림 (priority 4) + 종료, 성공 시 연결된 모든 채널 `asyncio.gather(..., return_exceptions=True)` 병렬 발송 (priority 5), `OutOfCapacity` 는 무알림 (PRD §7.5.3)
        - [x] 6.2.T1 pytest 테스트 작성 — 429 백오프 동작, auth_error 시 비활성화+알림 mock 호출 검증, 성공 시 다중 채널 병렬 발송 (1개 채널 실패해도 나머지 발송), out_of_capacity 무알림
        - [x] 6.2.T2 `pytest -q tests/unit/workers/` 실행 및 검증
    - [x] 6.3 poller supervisor + lifespan — `workers/poller.py` (10초 주기 `enabled=True` 목록 vs 실행 중 task diff → spawn/cancel, config 수정 감지 시 재시작), `main.py` lifespan 에서 `asyncio.create_task(poller_supervisor())` + log_pruner 기동, shutdown 시 전체 graceful cancel (`asyncio.wait` + `CancelledError` 전파)
        - [x] 6.3.T1 pytest 테스트 작성 — `tests/integration/test_poller_supervisor.py` (toggle on → task spawn, toggle off → cancel, config 수정 → 재시작, shutdown graceful 종료, 다중 계정 + 다중 config 동시 폴링 시나리오)
        - [x] 6.3.T2 `pytest -q tests/integration/test_poller_supervisor.py` 실행 및 검증
    - [x] 6.4 web: 시도 이력 — `entities/attempt` (상태 배지: success/out_of_capacity/rate_limited/auth_error/other_error, duration 표시), 최근 50개 시도 테이블 (`@tanstack/react-table`, 설정별/상태별 필터, `refetchInterval` 5초)
        - [x] 6.4.T1 vitest 테스트 작성 — 상태별 배지 렌더, 테이블 필터 동작 (MSW: config_id/status 쿼리 검증)
        - [x] 6.4.T2 `pnpm --filter web vitest run src/entities/attempt` 실행 및 검증
    - [x] 6.5 web: 대시보드 페이지 — `pages/dashboard` (활성/비활성 설정 카운트 카드, 시도 이력 테이블 위젯, 성공 인스턴스 정보 카드: OCID/생성 시각), `widgets/{header,sidebar}` 네비게이션 (로그아웃 포함), `app/(protected)/page.tsx`
        - [x] 6.5.T1 vitest 테스트 작성 — 대시보드 통합 테스트 (MSW: 카운트 집계 표시, 성공 인스턴스 카드 렌더), 사이드바 네비게이션 링크
        - [x] 6.5.T2 `pnpm --filter web test` 실행 및 검증
    - [ ] 6.6 부트스트랩 문서 + 최종 검증 — `README.md` (cli hash → APP_SECRET 생성 → `docker compose up -d` 절차, OSS Dependencies 섹션), `.env.example` 최종 정리, PRD §13 성공 기준 점검 (외부 차단 curl 검증 포함)
        - [ ] 6.6.T1 전체 테스트 스위트 보강 — 누락 커버리지 확인 (서버 70%+ / services·workers 80%+, 웹 50%+ / features·entities 70%+)
        - [ ] 6.6.T2 루트 `pnpm test` 전체 통과 + `docker compose up -d` 후 `curl localhost:8000/healthz` 실패·`curl localhost:3000/api/healthz` 성공 검증
