# 결과보고서: tasks-prd-push3

> 완료일: 2026-06-03
> 브랜치: `push3-logging` (push2-auth 에서 분기)
> 범위: 커스텀 로깅 인프라 (`JsonFormatter`, `DbLogHandler`, `LogBus`, `log_pruner`) + 로그 조회/SSE API + `/logs` 페이지 (FSD: `pages/logs` + `widgets/log-stream` + `features/log-filter`)
> 실행 방식: 서브에이전트 Task 도구 미사용 환경 → 단일 에이전트 순차 직접 구현 (도메인 분리·커밋 단위·T1/T2 규칙 준수)

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 3.1 LogEntry 모델 + Alembic 마이그레이션 | server | ✅ | d117acb |
| 3.2 JsonFormatter + DbLogHandler + 부트스트랩 | server | ✅ | 24bcf29 |
| 3.3 LogBus + LogBusHandler + 3핸들러 부착 | server | ✅ | de87e72 |
| 3.4 GET/DELETE /api/logs (커서 페이지네이션) | server | ✅ | 4eb5d00 |
| 3.5 SSE 스트림 + log_pruner 보존 워커 | server | ✅ | dee9678 |
| 3.6 entities/log + features/log-filter | web | ✅ | 051d0db |
| 3.7 widgets/log-stream + pages/logs + /logs 라우트 | web | ✅ | 0b4a69e |

## 변경 파일

### Server
- `apps/server/src/app/db/models.py` — `LogEntry` 테이블 추가 (timestamp/level/logger/config_id 인덱스)
- `apps/server/alembic/versions/e4c7ad0c4321_log_entry.py` — 마이그레이션 (autogenerate, up/down 검증)
- `apps/server/src/app/logging_config.py` — `JsonFormatter`, `DbLogHandler`, `NoRecursionFilter`, `configure_logging`
- `apps/server/src/app/log_bus.py` — `LogBus`(asyncio.Queue pub/sub, maxsize 500), `LogBusHandler`, `attach_log_bus`, `record_to_dict`
- `apps/server/src/app/api/logs.py` — `GET /api/logs`(필터+base64 커서), `GET /api/logs/stream`(SSE), `DELETE /api/logs?before=`
- `apps/server/src/app/workers/log_pruner.py` — `prune_once`/`run_log_pruner` (7일·10,000행 cutoff, AppSetting 오버라이드)
- `apps/server/src/app/main.py` — lifespan 에서 3핸들러 부트스트랩 + LogBus loop 바인딩 + log_pruner 백그라운드 태스크 + 라우터 등록
- 테스트: `tests/unit/db/test_log_entry.py`, `tests/unit/test_logging.py`, `tests/unit/test_logging_bootstrap.py`, `tests/unit/test_log_bus.py`, `tests/api/test_logs.py`, `tests/api/test_logs_stream.py`, `tests/unit/workers/test_log_pruner.py`
- `tests/conftest.py` — `db_app`/`authed_db_client` 픽스처(get_session 오버라이드 → 인메모리 DB)
- `pyproject.toml`/`uv.lock` — `sse-starlette>=2.1` 추가

### Web
- `apps/web/src/entities/log/` — `model/types.ts`(LogEntry/LogPage/LogLevel), `lib/format.ts`(레벨 배지 색·로컬 타임존), `ui/LogRow.tsx`(컨텍스트 칩·traceback 펼침)
- `apps/web/src/features/log-filter/` — `model/filter.ts`(LogFilter·filterToQuery), `ui/LogFilterBar.tsx`(레벨 멀티 토글·logger·config_id·기간·검색·Reset)
- `apps/web/src/widgets/log-stream/` — `model/useLogStream.ts`(EventSource 구독·일시정지 해제·maxRows 트림·query URL), `ui/LogStream.tsx`(가상 스크롤 임계 500행·자동 스크롤·위로 스크롤 시 자동 일시정지·pause 토글)
- `apps/web/src/pages/logs/` — `model/api.ts`(fetchLogs/deleteLogsBefore), `ui/LogsPage.tsx`(과거+실시간 결합·필터 재조회·삭제 확인 모달)
- `apps/web/app/(protected)/logs/page.tsx` — 라우트
- 테스트: `entities/log/ui/LogRow.test.tsx`, `features/log-filter/ui/LogFilterBar.test.tsx`, `widgets/log-stream/model/useLogStream.test.tsx`, `widgets/log-stream/ui/LogStream.test.tsx`, `pages/logs/ui/LogsPage.test.tsx`
- `package.json`/`pnpm-lock.yaml` — `@tanstack/react-virtual` 추가

## 테스트 결과

- **pytest**: 65 passed (커버리지 91%) — `uv run pytest`
- **vitest**: 38 passed (기존 15 + 신규 23) — `pnpm --filter web test`
- **lint**: web ESLint(FSD boundaries 포함) 통과
- 모든 외부 의존 모킹: SSE 제너레이터는 `log_bus` 직접 주입으로, EventSource 는 web 측 주입 가능한 mock 으로, DB 는 인메모리 sqlite 로 격리.

## OSS 도입 (oss-selection 체크 통과)

- **sse-starlette** (BSD-3): FastAPI SSE 표준 구현. PRD §9.3.7 에서 명시 지정. 수동 `text/event-stream` 핸들링 대비 heartbeat/disconnect 처리 안정성 확보. → README OSS 표 갱신.
- **@tanstack/react-virtual** (MIT): 로그 500행 초과 시 DOM 노드 가상화. 이미 도입된 @tanstack 생태계와 정합. PRD §7.6 명시. → README OSS 표 갱신.

## 이슈 및 해결 (T3)

- **3.5 SSE 테스트 행(hang)**: ASGITransport + `EventSourceResponse` 조합이 연결을 무한 유지해 httpx 스트리밍 읽기가 `wait_for` 취소 시에도 teardown 에서 데드락. → SSE 제너레이터를 라우트에서 `sse_event_stream(is_disconnected, levels, logger, config_id, heartbeat)` 로 분리하여 `log_bus.publish` 로 직접 구동하는 결정적 단위 테스트로 전환(수신/필터/heartbeat/disconnect 4케이스). 라우트는 이 제너레이터를 EventSourceResponse 로 감싸기만 함. 인증 가드(401)는 스트리밍 시작 전 반환되므로 HTTP 레벨로 검증.
- **3.2 `formatException` AttributeError**: `logging.Handler` 에는 `formatException` 이 없음(Formatter 메서드). → `DbLogHandler._exc_formatter = logging.Formatter()` 클래스 속성으로 traceback 포맷.
- **재귀 방지**: `NoRecursionFilter` 가 `sqlalchemy`/`aiosqlite`/`app.db`/`alembic` prefix 로거를 DB·Bus 핸들러에서 차단 → 로깅 INSERT 가 또 다른 로깅 INSERT 를 트리거하지 않음.
- **부트스트랩 테스트 격리**: lifespan 전체 부팅은 글로벌 root 로거/엔진을 오염시켜 다른 테스트에 영향 → `_restore_root_handlers` 픽스처로 핸들러 스냅샷/복원, 인메모리 엔진으로 `configure_logging`+`attach_log_bus` 직접 검증.

## 미완료/주의 항목

- **선재 typecheck 오류**(push3 범위 외): `apps/web/tests/next-rewrites.test.ts` 의 `rules` possibly undefined 2건은 push2-auth 시점부터 존재(동일 코드). push3 신규 코드는 `tsc` 클린. 회귀 아님이라 본 Push 범위에서 미수정 — 별도 정리 권장.
- git push 는 지시대로 미실행. 브랜치 `push3-logging` 에 7개 커밋 적재 상태.
- 작업 시작 시 워킹트리에 있던 push4/5/6 todo 수정분은 `git stash`(stash@{0} "wip-task-files") 로 분리 보관 — push3 커밋에 미포함.
