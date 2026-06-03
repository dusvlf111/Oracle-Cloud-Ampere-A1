# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 3

> PRD: `.claude/tasks/prd.md` (§7.6 로그 뷰어, §9.3 로깅, §11 MVP Push 3)
> Push 범위: 커스텀 로깅 인프라 (`JsonFormatter`, `DbLogHandler`, `LogBus`, `log_pruner`) + 로그 조회/SSE API + `/logs` 페이지 (FSD: `pages/logs` + `widgets/log-stream` + `features/log-filter`)
> 상태: ✅ 완료

---

### 관련 파일

- `apps/server/src/app/db/models.py` - `LogEntry` 모델
- `apps/server/src/app/logging_config.py` - `JsonFormatter`, `DbLogHandler`, 부트스트랩
- `apps/server/src/app/log_bus.py` - 인메모리 pub/sub (`asyncio.Queue` per subscriber)
- `apps/server/src/app/api/logs.py` - 조회/삭제/SSE 라우터
- `apps/server/src/app/workers/log_pruner.py` - 보존 정책 정리 워커
- `apps/server/tests/unit/test_logging.py`, `tests/api/test_logs.py` - 서버 테스트
- `apps/web/src/entities/log/` - 로그 엔티티 (행 렌더, 레벨 배지)
- `apps/web/src/features/log-filter/` - 레벨/logger/config/기간/검색 필터
- `apps/web/src/widgets/log-stream/` - SSE 구독 + 가상 스크롤 (`@tanstack/react-virtual`)
- `apps/web/src/pages/logs/`, `apps/web/app/(protected)/logs/page.tsx`

---

### 에이전트 실행 전략 (push-lead)

| 작업 | 담당 | 의존성 |
|---|---|---|
| 3.1 → 3.2 → 3.3 → 3.4 → 3.5 | `server-worker` | 순차 (모델 → 핸들러 → 버스 → API → SSE/pruner) |
| 3.6 → 3.7 | `web-worker` | — (MSW + EventSource mock 기반, API 계약은 PRD §8 `LogPage`/SSE 스키마 고정) |

```
[server-worker] 3.1 → 3.2 → 3.3 → 3.4 → 3.5
[web-worker]    3.6 → 3.7                    (server 체인과 병렬)
```

- **병렬**: server 체인(3.1~3.5) ∥ web 체인(3.6~3.7) — 파일 영역 분리, 계약은 PRD §8 기준
- 3.7 완료 후 push-lead 가 실서버 연동 smoke 확인 (SSE rewrite 경유 스트리밍), `test-runner` 최종 게이트
- 참조 스킬: `fastapi-patterns`, `python-testing` / `fsd-architecture`, `web-testing`

---

## 작업

- [x] 3.0 로깅 인프라 + 로그 뷰어 (Push 3)
    - [x] 3.1 `LogEntry` 모델 + Alembic 마이그레이션 — timestamp/level/logger 인덱스, `config_id`/`attempt_id`/`credential_id`/`extra`/`exc_info` 컨텍스트 컬럼 (PRD §6)
        - [x] 3.1.T1 pytest 테스트 작성 — `tests/unit/db/test_log_entry.py` (생성/인덱스 컬럼 조회), 마이그레이션 up/down 검증
        - [x] 3.1.T2 `pytest -q tests/unit/db/` + `alembic upgrade head` 실행 및 검증
    - [x] 3.2 `JsonFormatter` + `DbLogHandler` + 로깅 부트스트랩 — `logging_config.py` (stdout JSON 핸들러, DB 동기 INSERT 핸들러, `record.__dict__` 에서 컨텍스트 키 추출, 재귀 방지 필터, `emit()` 예외 격리 `handleError`, 라이브러리 로거 WARNING, env `LOG_LEVEL`/`LOG_LEVEL_DB`)
        - [x] 3.2.T1 pytest 테스트 작성 — `tests/unit/test_logging.py` (JSON 출력 스키마, `extra` 컨텍스트 → LogEntry 컬럼 매핑, ERROR 시 exc_info 저장, DB 장애 시 앱 영향 없음, sqlalchemy 로그 재귀 차단)
        - [x] 3.2.T2 `pytest -q tests/unit/test_logging.py` 실행 및 검증
    - [x] 3.3 `LogBus` + `LogBusHandler` — `log_bus.py` (subscribe 컨텍스트매니저, `put_nowait` + QueueFull 드롭, maxsize 500), 핸들러가 `publish()` 호출, 루트 로거에 3핸들러 부착
        - [x] 3.3.T1 pytest 테스트 작성 — `tests/unit/test_log_bus.py` (구독자 수신, 다중 구독자, 가득 찬 큐 드롭, 구독 해제 후 미수신)
        - [x] 3.3.T2 `pytest -q tests/unit/test_log_bus.py` 실행 및 검증
    - [x] 3.4 로그 조회/삭제 API — `GET /api/logs` (levels 멀티/logger prefix/config_id/since/until/q LIKE/limit + base64 cursor 페이지네이션 → `LogPage{items, next_cursor, has_more}`), `DELETE /api/logs?before=<iso>` 204 (PRD §8)
        - [x] 3.4.T1 pytest 테스트 작성 — `tests/api/test_logs.py` (필터 조합, 커서 연속 조회, 검색, 삭제 후 미조회, 미인증 401)
        - [x] 3.4.T2 `pytest -q tests/api/test_logs.py` 실행 및 검증
    - [x] 3.5 SSE 스트림 + log_pruner — `GET /api/logs/stream` (sse-starlette, LogBus 구독, 필터 쿼리, 15초 `ping` heartbeat), `workers/log_pruner.py` (5분 주기, 7일/10,000행 cutoff DELETE, `AppSetting` 정책 값)
        - [x] 3.5.T1 pytest 테스트 작성 — `tests/api/test_logs_stream.py` (publish → SSE 이벤트 수신, 필터 미일치 미수신), `tests/unit/workers/test_log_pruner.py` (기간/행수 초과 삭제)
        - [x] 3.5.T2 `pytest -q tests/api/test_logs_stream.py tests/unit/workers/test_log_pruner.py` 실행 및 검증
    - [x] 3.6 web: 로그 엔티티 + 필터 — `entities/log` (행 컴포넌트: 로컬 타임존 타임스탬프, 레벨 색 배지, 컨텍스트/traceback 펼침), `features/log-filter` (레벨 멀티 선택, logger prefix, config_id, 기간, 검색어 → 쿼리 파라미터 상태)
        - [x] 3.6.T1 vitest 테스트 작성 — `entities/log/ui/LogRow.test.tsx` (레벨별 배지, traceback 펼침), `features/log-filter` 테스트 (user-event 로 필터 변경 → 콜백 파라미터)
        - [x] 3.6.T2 `pnpm --filter web vitest run src/entities/log src/features/log-filter` 실행 및 검증
    - [x] 3.7 web: 로그 스트림 위젯 + 페이지 — `widgets/log-stream` (EventSource 구독, 실시간↔일시정지 토글, 자동 스크롤 + 위로 스크롤 시 자동 일시정지, 500행 초과 가상 스크롤), `pages/logs` (과거 조회 + 실시간 결합, 삭제 확인 모달) + `app/(protected)/logs/page.tsx`
        - [x] 3.7.T1 vitest 테스트 작성 — `widgets/log-stream` (EventSource mock: 수신→행 추가, 일시정지 시 구독 해제), `pages/logs` 통합 테스트 (MSW: 과거 로그 로드 + 필터 적용 + 삭제 흐름)
        - [x] 3.7.T2 `pnpm --filter web test` 실행 및 검증
