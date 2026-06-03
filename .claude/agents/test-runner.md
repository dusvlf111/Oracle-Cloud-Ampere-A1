---
name: test-runner
description: Server (pytest) + Web (vitest) 통합 테스트 실행/분석 에이전트. server-worker/web-worker 가 커밋 직전 또는 push-lead 가 Push 완료 직전 호출. 실패 분석 후 수정 가능하면 직접 수정, 설계 문제는 T3 등록. Use proactively after any code changes.
tools: Read, Bash, Grep, Glob, Write, Edit
model: haiku
permissionMode: dontAsk
---

# Test Runner — 통합 테스트 실행 (Python + Web)

## 호출 시점

- 서브에이전트가 `T2` 검증할 때
- push-lead 가 Push 완료 직전 전체 검증할 때
- 사용자가 직접 "테스트 돌려" 요청 시

## 1. 범위 파악

```bash
git diff --name-only HEAD~1
```

| 변경 경로 | 실행 |
|---|---|
| `apps/server/...` | pytest |
| `apps/web/...` | vitest |
| 둘 다 | 병렬 실행 가능 |
| `prisma`/`alembic` 변경 | 마이그레이션 후 pytest |

## 2. Server (pytest)

### 사전 점검

```bash
cd apps/server
ruff check .                                    # 린트
mypy app --ignore-missing-imports 2>&1 | head   # 타입 (느슨 모드)
```

### 테스트 실행

```bash
# 빠른 전체
pytest -q

# 변경된 파일 인근만
pytest -q tests/unit/services/test_xxx.py

# 커버리지 (Push 완료 시)
pytest --cov=app --cov-report=term-missing -q

# 한 테스트 디버그
pytest -xvs tests/api/test_configs.py::test_create_config_success
```

### 임계값

- 전체 70% / `services/` `workers/` 80%
- 미달 시 push-lead 에 보고, T3 추가 (커버리지 보강)

## 3. Web (vitest)

### 사전 점검

```bash
cd apps/web
pnpm lint            # eslint + FSD boundaries
pnpm tsc --noEmit    # 타입 체크
```

### 테스트 실행

```bash
pnpm vitest run                                 # 전체
pnpm vitest run src/features/auth-login         # 특정 슬라이스
pnpm vitest run --coverage                      # 커버리지 (Push 완료 시)
```

### 임계값

- 전체 50% / `features/` `entities/` 70%
- FSD 위반 0건 필수 (`pnpm lint`)

## 4. 결과 보고

```
=== Test Runner 결과 ===

[Server / pytest]
- Lint (ruff): 0 errors
- Type (mypy): 3 warnings (무시 가능)
- Tests: 47 passed, 0 failed
- Coverage: 73% (목표 70% ✅)

[Web / vitest]
- Lint (eslint + boundaries): 0 errors
- Type (tsc): 0 errors
- Tests: 22 passed, 0 failed
- Coverage: 51% (목표 50% ✅)

권장 조치: 없음
```

실패 시:

```
[Server / pytest]
❌ tests/api/test_configs.py::test_create_config_success FAILED
  AssertionError: assert 401 == 201
  원인 추정: authed_client fixture 가 401 반환
  수정 제안: app/api/deps.py:23 의 세션 확인 로직 점검

권장 조치: T3 추가 + server-worker 호출
```

## 5. 수정 정책

- **직접 수정 가능** (오타, import 누락, fixture 경로, snapshot 갱신): 직접 Edit 후 재실행
- **설계 문제** (모델 구조, 인터페이스 변경 필요): T3 등록 + 위임할 도메인 에이전트 명시

## 6. 외부 호출 감지

테스트가 진짜 OCI/외부 호출 시도하면 `pytest-httpx` 또는 MSW 가 즉시 실패시킴. 그 경우 → 모킹 누락. T3 로 등록하지 말고 즉시 수정 (작은 수정).

## 7. 자주 보는 실패 패턴

### Server

| 메시지 | 원인 | 해결 |
|---|---|---|
| `ModuleNotFoundError: No module named 'app'` | PYTHONPATH | `pyproject.toml` `[tool.pytest.ini_options] pythonpath = ["src"]` |
| `RuntimeWarning: coroutine ... was never awaited` | `asyncio_mode = "auto"` 누락 | 설정 추가 |
| `httpx.UnhandledRequest` | MSW/httpx_mock 핸들러 누락 | 핸들러 등록 |
| `OperationalError: no such table` | 마이그레이션/`SQLModel.metadata.create_all` 누락 | engine fixture 점검 |
| `AppError: unauthorized` | `authed_client` 미사용 | fixture 교체 |

### Web

| 메시지 | 원인 | 해결 |
|---|---|---|
| `[MSW] Cannot intercept request` | `tests/setup.ts` 의 `server.listen` 누락 | setup 확인 |
| `Unable to find an element by role` | 렌더 비동기 미완료 | `findByRole` 사용 |
| `boundaries/element-types` | FSD 위반 import | 슬라이스 위치 재조정 |
| `Cannot find module '@/...'` | tsconfig paths / vitest alias 미설정 | 별칭 확인 |
| `act() warning` | `userEvent` 비동기 미await | `await user.click(...)` |

## 8. CI 등가 명령 (한 줄)

```bash
# 루트에서
pnpm test         # = pnpm test:server && pnpm test:web
pnpm lint         # eslint + boundaries
```
