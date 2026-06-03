# 결과보고서: tasks-prd-push1

> 완료일: 2026-06-03
> 범위: 모노레포 인프라 — pnpm workspace, FastAPI 스캐폴딩, Alembic, FSD + eslint-plugin-boundaries, Next.js 15 + Tailwind v4 + shadcn, Docker Compose(server 외부 노출 차단), pytest/vitest + MSW, 루트 `pnpm test`
> 브랜치: `push1-monorepo-infra` (push 안 함)

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 1.1 pnpm workspace 초기화 | root | ✅ | e6f0599 |
| 1.2 FastAPI 스캐폴딩 + /healthz + pytest | server | ✅ | 4ffaa36 |
| 1.3 SQLModel WAL 엔진/세션 + Alembic | server | ✅ | 11bdd56 |
| 1.4 Next.js 15 + Tailwind v4 + shadcn + FSD 골격 | web | ✅ | 975833f |
| 1.5 eslint-plugin-boundaries FSD 규칙 강제 | web | ✅ | 5f8dc83 |
| 1.6 vitest + RTL + MSW 테스트 인프라 | web | ✅ | 94276d9 |
| 1.7 Docker Compose 외부 차단 + rewrites + 루트 pnpm test | infra | ✅ | 26ef4ed |

## 테스트 결과

- pytest (서버): **8 passed**, 커버리지 **85%** (목표 70% 초과)
- vitest (웹): **7 passed** (3 files — Providers smoke / MSW setup / next rewrites)
- `pnpm test` (= test:server && test:web): 통과
- `pnpm lint`: 통과 / FSD 위반 fixture: `boundaries/element-types` 에러로 정상 거부
- `pnpm --filter web build` + `tsc --noEmit`: 통과
- `node scripts/verify-workspace.mjs`, `node scripts/verify-compose.mjs`: 통과

## 변경 파일

### Root
- `pnpm-workspace.yaml`, `package.json`, `pnpm-lock.yaml`, `.gitignore`, `.env.example`
- `docker-compose.yml`, `README.md`
- `scripts/verify-workspace.mjs`, `scripts/verify-compose.mjs`

### Server (`apps/server/`)
- `pyproject.toml`, `uv.lock`, `Dockerfile`, `alembic.ini`
- `src/app/{__init__,config,main}.py`, `src/app/db/{__init__,models,session}.py`
- `alembic/env.py`, `alembic/script.py.mako`, `alembic/versions/*_initial.py`
- `tests/conftest.py`, `tests/api/test_healthz.py`, `tests/unit/test_config.py`, `tests/unit/db/test_session.py`

### Web (`apps/web/`)
- `package.json`, `tsconfig.json`, `next.config.ts`, `postcss.config.mjs`, `next-env.d.ts`
- `eslint.config.js`, `vitest.config.ts`, `orval.config.ts`, `components.json`, `Dockerfile`
- `src/app/{layout,page}.tsx`, `src/app/providers/{Providers,index}.tsx`, `src/app/styles/globals.css`
- `src/{pages,widgets,features,entities,shared}/index.ts`, `src/shared/{lib/utils,ui/button}`
- `src/entities/__lint_fixture__/bad-import.ts` (FSD 위반 fixture)
- `tests/setup.ts`, `tests/setup.test.ts`, `tests/next-rewrites.test.ts`, `tests/mocks/{server,handlers}.ts`

## 발생 이슈와 해결

1. **환경 도구 부재**: `uv`/`pip`/`docker` 미설치. → `uv` standalone 설치 스크립트로 설치(`~/.local/bin`),
   모든 Python 작업을 `uv run` 으로 수행. Docker 데몬은 부재 → 1.7 라이브 프로브 보류(아래 5번).
2. **conftest import 충돌**: `import app.db.models` 가 `from app.main import app` 의 `app` 을 모듈로 덮어써
   ASGITransport 가 'module object is not callable' 발생. → `import app.db.models as _models` 별칭으로 해결.
3. **Next.js App Router 위치 충돌**: `src/` 디렉토리 존재 시 Next 가 `src/app` 을 라우터 루트로 사용 →
   루트 `app/` 라우터가 무시되어 타입 검증 실패. → 라우터 `layout/page` 를 `src/app` 으로 이동하여
   FSD app 레이어(providers/styles)와 공존. `pageExtensions=[tsx,jsx]` 로 `src/pages/index.ts` 가
   라우트로 오인되지 않게 함. (PRD §5 "src/app 으로 두고 충돌 회피" 의도 충족)
4. **boundaries 룰 미발동**: 레이어 import 타입 해석을 위해 import resolver 필요.
   → `eslint-import-resolver-typescript` + `import/resolver` 설정 추가, element pattern 을
   `src/<layer>` (folder mode) 로 조정하여 레이어 배럴/슬라이스 모두 분류되게 함. fixture 가
   정상적으로 에러 발생 확인.
5. **Docker 데몬 부재 (1.7.T2 일부 보류)**: `docker compose up` 후 `curl localhost:8000` 실패 /
   `curl localhost:3000/api/healthz` 성공 라이브 프로브는 실행 불가. → `scripts/verify-compose.mjs` 로
   `server ports 미선언`/`expose:8000`/`web 3000:3000`/`depends_on service_healthy` 불변식을 정적 검증,
   `next-rewrites.test.ts` 로 프록시 매핑을 단위 검증하여 외부 차단 보증. Docker 가용 환경에서 라이브 프로브 권장.

## 새로 만든 스킬

- 없음. (반복 패턴 미발생 — 단발성 인프라 셋업)

## 미완료 항목

- 없음. 1.0~1.7 및 모든 T1/T2 완료.
- 후속: 1.7.T2 의 Docker 라이브 curl 프로브는 Docker 데몬 가용 시 1회 수동 확인 권장(차단/프록시 동작).
