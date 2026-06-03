# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 1

> PRD: `.claude/tasks/prd.md` (§5 모노레포 구조, §10 배포, §11 MVP Push 1)
> Push 범위: 모노레포 인프라 — pnpm workspace, FastAPI 스캐폴딩, Alembic, FSD 디렉토리 + eslint-plugin-boundaries, Next.js + Tailwind + shadcn, Docker Compose (server 외부 노출 차단), pytest/vitest + MSW 셋업, 루트 `pnpm test` 통합
> 상태: ✅ 완료

---

### 관련 파일

- `pnpm-workspace.yaml` - workspace 정의 (`apps/web`, `packages/*`)
- `package.json` - 루트 스크립트 (dev/test/gen:api/lint/build)
- `apps/server/pyproject.toml` - Python 의존성 (uv)
- `apps/server/src/app/main.py` - FastAPI 앱 + lifespan + `/healthz`
- `apps/server/src/app/config.py` - pydantic-settings
- `apps/server/src/app/db/session.py` - SQLite WAL 엔진/세션
- `apps/server/alembic/` - 마이그레이션 환경
- `apps/server/tests/conftest.py` - 공용 fixture (engine, session, client)
- `apps/web/` - Next.js 15 + FSD 6계층 (`src/{app,pages,widgets,features,entities,shared}`)
- `apps/web/eslint.config.js` - eslint-plugin-boundaries FSD 강제
- `apps/web/next.config.ts` - rewrites: `/api/*` → `http://server:8000/api/*`
- `apps/web/vitest.config.ts`, `apps/web/tests/setup.ts` - vitest + MSW 셋업
- `docker-compose.yml` - server `expose` 만 / web `ports: 3000`
- `apps/server/Dockerfile`, `apps/web/Dockerfile`

---

### 에이전트 실행 전략 (push-lead)

| 작업 | 담당 | 의존성 |
|---|---|---|
| 1.1 | push-lead 직접 (루트 설정) | — |
| 1.2 → 1.3 | `server-worker` | 1.1 |
| 1.4 → 1.5 → 1.6 | `web-worker` | 1.1 |
| 1.7 | `server-worker` (Dockerfile/compose) + `web-worker` (rewrites) 협업, push-lead 조율 | 1.2~1.6 전체 |

```
1.1 ──┬── [server-worker] 1.2 → 1.3 ──┬── 1.7 (배리어)
      └── [web-worker]    1.4 → 1.5 → 1.6 ──┘
```

- **병렬**: server 체인(1.2~1.3) ∥ web 체인(1.4~1.6) — 파일 영역 완전 분리
- 각 커밋의 T2 는 커밋 직전 `test-runner` 호출로 검증, Push 완료 시 test-runner 가 전체 스위트 최종 게이트
- 참조 스킬: `fastapi-patterns`, `python-testing` (server) / `fsd-architecture`, `web-testing` (web) / `oss-selection` (공통)

---

## 작업

- [x] 1.0 모노레포 인프라 구축 (Push 1)
    - [x] 1.1 pnpm workspace 초기화 — `pnpm-workspace.yaml`, 루트 `package.json` 스크립트 (PRD §5), `.gitignore`, `.env.example` (PRD §10)
        - [x] 1.1.T1 검증 스크립트 작성 — workspace 구성 파일 존재/스키마 확인 (이후 1.6에서 vitest 로 통합)
        - [x] 1.1.T2 `pnpm install` 성공 + `pnpm -r ls` 로 workspace 인식 검증
    - [x] 1.2 FastAPI 서버 스캐폴딩 — `apps/server/pyproject.toml` (uv, fastapi/uvicorn/pydantic-settings), `src/app/{__init__,main,config}.py`, `/healthz` 엔드포인트, pytest/pytest-asyncio (`asyncio_mode=auto`)/pytest-cov/pytest-httpx/polyfactory 셋업 + `tests/conftest.py` 기본 fixture
        - [x] 1.2.T1 pytest 테스트 작성 — `tests/api/test_healthz.py` (`GET /healthz` → `{status:"ok"}`, 인증 불필요), `tests/unit/test_config.py` (env 로딩)
        - [x] 1.2.T2 `cd apps/server && pytest -q` 실행 및 검증
    - [x] 1.3 SQLModel 엔진/세션 + Alembic 셋업 — `db/session.py` (SQLite, `PRAGMA journal_mode=WAL`), `alembic.ini`, `alembic/env.py` (SQLModel metadata 연동), 빈 초기 revision
        - [x] 1.3.T1 pytest 테스트 작성 — `tests/unit/db/test_session.py` (in-memory 엔진 생성, WAL pragma 적용 확인), conftest 에 `engine`/`session` fixture 추가
        - [x] 1.3.T2 `pytest -q tests/unit/db/` + `alembic upgrade head` (임시 DB) 실행 및 검증
    - [x] 1.4 Next.js 15 스캐폴딩 — App Router, React 19, TypeScript, Tailwind CSS v4, shadcn/ui 초기화, FSD 디렉토리 골격 `src/{app,pages,widgets,features,entities,shared}` + slice 별 `index.ts`, `tsconfig.json` paths (`@/app` ~ `@/shared`), `app/layout.tsx` + Providers (`src/app/providers` — QueryClientProvider)
        - [x] 1.4.T1 (1.6 vitest 셋업 후 소급 실행) 루트 레이아웃 렌더 smoke 테스트 작성 — `src/app/providers/Providers.test.tsx`
        - [x] 1.4.T2 `pnpm --filter web build` + `pnpm --filter web tsc --noEmit` 실행 및 검증
    - [x] 1.5 FSD 레이어 규칙 강제 — `eslint.config.js` 에 `eslint-plugin-boundaries` 설정 (PRD §5 규칙: 상위→하위만 허용, 같은 레이어 slice 간 직접 import 금지)
        - [x] 1.5.T1 위반 케이스 fixture 작성 — `entities` → `features` import 샘플 파일로 룰 동작 검증 (검증 후 샘플 제거 or `tests/lint-fixtures/`)
        - [x] 1.5.T2 `pnpm --filter web lint` 실행 — 위반 시 에러 발생, 정상 코드 통과 검증
    - [x] 1.6 웹 테스트 인프라 — `vitest.config.ts` (jsdom), `@testing-library/react`, `@testing-library/user-event`, MSW (`tests/setup.ts`: `onUnhandledRequest: 'error'`), `tests/mocks/{server,handlers}.ts`
        - [x] 1.6.T1 vitest 테스트 작성 — MSW 핸들러 동작 smoke 테스트 (`tests/setup.test.ts`: 등록된 핸들러 응답 + 미등록 호출 실패 확인), 1.4.T1 소급 작성
        - [x] 1.6.T2 `pnpm --filter web test` 실행 및 검증
    - [x] 1.7 Docker Compose + 외부 노출 차단 — `docker-compose.yml` (server: `expose` 만/`ports` 미선언, healthcheck; web: `ports: 3000`, `depends_on: service_healthy`), `apps/server/Dockerfile`, `apps/web/Dockerfile` (multi-stage + pnpm), `next.config.ts` rewrites (`INTERNAL_API_URL`), 루트 `pnpm test` = `test:server && test:web`
        - [x] 1.7.T1 vitest 테스트 작성 — `next.config.ts` rewrites 설정 단위 테스트 (`/api/:path*` → internal URL 매핑)
        - [x] 1.7.T2 `docker compose config` 검증 (server ports 미선언 확인) + `docker compose up -d` 후 `curl localhost:8000/healthz` 실패 / `curl localhost:3000/api/healthz` 성공 + 루트 `pnpm test` 통과
            - 참고: 본 실행 환경에 Docker 데몬 없음 → `docker compose up` 라이브 curl 프로브는 보류. 대신 `scripts/verify-compose.mjs` 로 server `ports` 미선언 / `expose:8000` / web `3000:3000` / `depends_on: service_healthy` 불변식을 정적 검증(통과), rewrites 단위 테스트(1.7.T1)로 프록시 매핑 보증. 루트 `pnpm test` 통과(서버 8 / 웹 7).
