# PRD: Oracle Cloud Ampere A1 자동 신청 시스템

> 상태: 초안 v0.6
> 작성일: 2026-06-03
> 변경: OSS 적극 활용 정책 / 도메인 분리형 에이전트 팀 / API JSON·에러 표준 / 스킬 카탈로그

---

## 1. 개요

Oracle Cloud Free Tier의 **Ampere A1 (ARM)** 인스턴스는 가용성이 부족해 수동으로 신청해도 `Out of host capacity` 오류로 실패하기 일쑤다. 본 시스템은 사용자가 웹 UI로 신청 조건을 설정해 두면, 백그라운드 워커가 가용성이 확보될 때까지 자동으로 재시도해 인스턴스를 생성하는 것을 목표로 한다.

---

## 2. 목표 (Goals)

- 사용자가 OCI 자격증명/인스턴스 사양을 웹 UI에서 입력·수정
- **여러 OCI 계정과 여러 InstanceConfig를 동시(병렬)로 폴링** — 한 계정 안에서는 rate limit 보호, 계정 간에는 완전 독립
- FastAPI 서버 내 백그라운드 워커가 OCI `LaunchInstance` API를 주기적으로 호출하여 가용성 확보 시 자동 생성
- 성공/실패/재시도 이력을 DB에 기록하고 UI에서 조회
- 서버/워커의 로그를 웹에서 실시간 + 과거 이력 조회 (필터링/검색 가능)
- 인스턴스 생성/장애 시 **다중 알림 채널** 발송 — Discord / Telegram / Slack / **ntfy** (self-hosted 포함, 예: `ntfy.supabin.com`)
- 알림 채널 CRUD + 채널 ↔ Config many-to-many (한 config 가 여러 채널로 발송 가능)
- **단일 관리자(혼자 사용) 로그인** — 회원가입 없음, env 로 정해진 1쌍의 계정만 허용
- **API 서버는 외부에 노출하지 않음** — Docker 내부 네트워크에서만 접근, Next.js 가 `/api/*` 를 리버스 프록시. CORS 는 보조 방어선
- 단일 명령 (`docker compose up`) 으로 전체 스택 기동
- 모노레포 — Python 서버와 Next.js 웹이 pnpm workspace 내에 공존, Orval 로 타입 클라이언트 자동 생성
- **Next.js 는 FSD (Feature-Sliced Design) 아키텍처** — 레이어 규칙 ESLint 로 강제, slice 별 공개 API
- **모든 commit 단위 작업은 테스트 코드 동봉 필수** — 서버 `pytest`, 웹 `vitest + RTL + MSW`
- **OSS 적극 활용** — 자체 구현보다 검증된 OSS 우선 (라이선스 GPL/AGPL 포함 모두 허용 — self-host, 재배포 없음)
- **도메인 분리형 에이전트 팀** — `push-lead` 오케스트레이터 + `server-worker`(Python/FastAPI) + `web-worker`(Next.js/FSD) + `test-runner`

## 3. 비목표 (Non-goals)

- 다중 클라우드(AWS/GCP) 지원
- Always Free 범위를 넘는 유료 인스턴스
- 인스턴스 생성 후 프로비저닝(앱 배포 등) — 본 시스템은 **생성까지만** 책임
- **다중 사용자 / 회원가입 / RBAC / OAuth** — env 로 박힌 단일 관리자만 로그인. 회원가입 엔드포인트/UI 자체를 두지 않음
- 비밀번호 재설정 플로우 (env 변경 + 재배포로 처리)
- 인스턴스 모니터링/메트릭 수집

---

## 4. 기술 스택

| 영역 | 기술 |
|---|---|
| API 서버 | **FastAPI** 0.115+, Uvicorn (ASGI), Python 3.12 |
| ORM | **SQLModel** (SQLAlchemy 2.0 + Pydantic 통합) |
| DB 마이그레이션 | **Alembic** |
| OCI 호출 | `oci` SDK (sync) → `asyncio.to_thread` 로 비동기화 |
| 재시도/백오프 | `tenacity` |
| 알림 HTTP | `httpx` (async) — Discord/Slack/Telegram/**ntfy** 모두 HTTP POST 로 통일 |
| ntfy | self-hosted 서버 지원 (예: `https://ntfy.supabin.com`), 별도 SDK 없음 |
| 인증 | FastAPI `SessionMiddleware` (itsdangerous 기반) + `argon2-cffi` (비밀번호 해시 비교) + `slowapi` (로그인 rate limit) |
| 로깅 | Python 표준 `logging` + 커스텀 `JsonFormatter` + DB `Handler` + 인메모리 `asyncio.Queue` |
| SSE | `sse-starlette` |
| 암호화 | `cryptography` (AES-256-GCM) |
| 웹 프런트 | **Next.js 15** (App Router), React 19, TypeScript |
| 웹 아키텍처 | **FSD (Feature-Sliced Design)** — `app/pages/widgets/features/entities/shared` 6계층 |
| FSD 강제 | `eslint-plugin-boundaries` (레이어 import 규칙), slice 별 `index.ts` 공개 API |
| API 클라이언트 | **Orval** (OpenAPI → TS client + React Query 훅) — `shared/api/` 에 생성 |
| 데이터 페칭 | TanStack Query v5 |
| 스타일 | Tailwind CSS v4 |
| 서버 테스트 | `pytest`, `pytest-asyncio`, `httpx` (TestClient), `pytest-cov`, `polyfactory` (팩토리) |
| 웹 테스트 | `vitest`, `@testing-library/react`, `@testing-library/user-event`, `msw` (API 모킹), `jsdom` |
| E2E (선택) | Playwright (v0.2 이후) |
| DB | SQLite (WAL 모드, 단일 파일) |
| 패키지 매니저 (JS) | **pnpm** + workspace |
| 패키지 매니저 (Python) | `uv` (또는 pip + requirements.txt) |
| 컨테이너 | Docker, Docker Compose v2 |
| 베이스 이미지 | `python:3.12-slim-bookworm` (서버), `node:20-bookworm-slim` (웹), ARM64 호환 |

### OSS 활용 정책

- **모든 OSS 라이선스 허용** (MIT/Apache/BSD/MPL/LGPL/GPL/AGPL 등) — 본 시스템은 self-host 전용이며 재배포하지 않음
- **자체 구현보다 검증된 OSS 우선** — "직접 짜기 전에 적절한 OSS 가 있는지 먼저 확인"이 기본 동작
- **선택 기준** (우선순위 순):
  1. 활성 유지보수 (최근 6개월 내 커밋)
  2. 다운로드/스타 수 (Python: 월 100k+ 다운로드, npm: 주 50k+ 또는 GitHub 5k★+)
  3. 라이브러리 보안 이력 (CVE/Snyk 검색)
  4. ARM64 (aarch64) 호환 (네이티브 의존성이 있는 경우)
- 채택한 OSS 와 버전·라이선스는 `README.md` 의 "OSS Dependencies" 섹션에 기록
- 도입 판단 가이드는 `.claude/skills/oss-selection/SKILL.md` 참조

### 핵심 OSS 매트릭스

| 영역 | 채택 | 대안 | 이유 |
|---|---|---|---|
| ASGI 서버 | `uvicorn` | hypercorn | FastAPI 표준 |
| ORM | `sqlmodel` | SQLAlchemy 2.0 + Pydantic | FastAPI/Pydantic 통합 |
| 마이그레이션 | `alembic` | aerich | SQLAlchemy 기반 (sqlmodel 호환) |
| HTTP 클라이언트 | `httpx` | aiohttp | sync/async 통합, FastAPI 친화 |
| 재시도 | `tenacity` | backoff | 데코레이터 + 컨텍스트, 풍부한 정책 |
| 비밀번호 해시 | `argon2-cffi` | passlib (deprecated bcrypt) | OWASP 권장, 활성 유지보수 |
| 암호화 | `cryptography` | nacl | 산업 표준, AES-GCM 내장 |
| 세션 미들웨어 | `starlette.SessionMiddleware` + `itsdangerous` | starsessions | FastAPI 내장 |
| Rate limit | `slowapi` | fastapi-limiter (Redis 필요) | 메모리 backend, SQLite 환경 적합 |
| SSE | `sse-starlette` | (직접 구현) | 끊김/재연결/heartbeat 처리 |
| 설정 | `pydantic-settings` | dynaconf | Pydantic 타입 안전 |
| 로깅 | `logging` stdlib + 커스텀 | structlog | 표준성, 의존성 최소 |
| 테스트 — 서버 | `pytest`, `pytest-asyncio`, `pytest-cov`, `pytest-httpx`, `polyfactory` | unittest | 생태계, fixture |
| OCI | `oci` (공식 SDK) | (REST 직접) | 공식 보장 |
| CLI 헬퍼 | `typer` | argparse | FastAPI 저자, Pydantic 통합 |
| 패키지 관리자 (Py) | `uv` | poetry, pip+requirements | 속도 (10x+), lockfile |
| Webhook 전송 | (httpx) | dhooks (Discord) | 채널 4종 통일 |
| **UI 컴포넌트** | `shadcn/ui` | mantine, chakra | 복사 가능, Tailwind 친화 |
| **폼** | `react-hook-form` + `zod` + `@hookform/resolvers` | formik, react-final-form | DX, 타입 안전 |
| **상태/데이터** | `@tanstack/react-query` | swr, redux-toolkit-query | Orval 통합 |
| **테이블/가상화** | `@tanstack/react-table`, `@tanstack/react-virtual` | ag-grid | 가벼움, headless |
| **차트** | `recharts` | victory, visx | shadcn 친화 |
| **날짜** | `date-fns` | dayjs, luxon | tree-shakable |
| **아이콘** | `lucide-react` | heroicons | shadcn 기본 |
| **알림 UI** | `sonner` | react-hot-toast | shadcn 권장 |
| **다이얼로그/팝오버** | `@radix-ui` (shadcn 내장) | headlessui | 접근성 |
| **테스트 — 웹** | `vitest`, `@testing-library/react`, `@testing-library/user-event`, `msw`, `jsdom` | jest | Vite 호환, 빠름 |
| **타입 검증 (런타임)** | `zod` | yup, valibot | 표준화, react-hook-form 통합 |
| **FSD 규칙** | `eslint-plugin-boundaries` | steiger | ESLint 통합 |
| **차단 알림 (ntfy)** | `httpx` (POST) | (전용 SDK 없음) | 단순 HTTP |

신규/대체 도입은 `oss-selection` 스킬 체크리스트 통과 후 PR description 에 근거 명시.

### 핵심 아키텍처 결정

- **서버 + 워커 = 단일 프로세스**: FastAPI `lifespan` 컨텍스트에서 `asyncio.create_task` 로 폴링 루프 시작. 별도 컨테이너 분리 안 함 (단순화 우선, 확장 시 분리 가능).
- **다중 계정 병렬 폴링**: config 별 독립 `asyncio.Task` + 계정별 `asyncio.Semaphore` (기본 동시 호출 1) → 같은 OCI 테넌시는 직렬, 다른 테넌시는 병렬
- **타입 동기화 흐름**: FastAPI (SQLModel) → `/openapi.json` → Orval → `apps/web/lib/api/*` (자동 생성) → React Query 훅
- **Orval 실행 시점**: dev에서 수동 `pnpm gen:api`, CI/Docker 빌드 시 자동 (서버 dev 실행 후 fetch)
- **알림 채널 분리**: 채널 ↔ Config many-to-many — 한 config 가 여러 채널로 발송, 한 채널을 여러 config 가 재사용
- **외부 노출 차단 전략**: docker-compose 에서 server 의 `ports` 미선언, `expose` 만. 호스트에서 `8000` 접근 불가. Next.js (`next.config.ts` `rewrites()`) 가 브라우저의 `/api/*` 요청을 내부 네트워크 `http://server:8000/api/*` 로 프록시. CORS 는 보조 (allow-list)
- **FSD 레이어 규칙**: 상위 레이어는 하위 사용 가능 / 하위는 상위 사용 불가 / 같은 레이어 slice 간 직접 import 금지 (shared 경유). Next.js `app/` (라우트) 는 얇은 진입점만, FSD `app/` 레이어는 `src/app/` 로 두고 충돌 회피

---

## 5. 모노레포 구조

```
Oracle-Cloud-Ampere-A1/
├── apps/
│   ├── server/                    # FastAPI + 워커 (Python)
│   │   ├── src/
│   │   │   └── app/
│   │   │       ├── __init__.py
│   │   │       ├── main.py            # FastAPI 앱, lifespan
│   │   │       ├── config.py          # pydantic-settings
│   │   │       ├── logging_config.py  # JsonFormatter, DbLogHandler, 부트스트랩
│   │   │       ├── log_bus.py         # 인메모리 pub/sub (asyncio.Queue per subscriber)
│   │   │       ├── db/
│   │   │       │   ├── session.py     # 엔진/세션
│   │   │       │   └── models.py      # SQLModel (LogEntry 포함)
│   │   │       ├── api/
│   │   │       │   ├── auth.py        # 로그인/로그아웃/me (단일 관리자)
│   │   │       │   ├── credentials.py
│   │   │       │   ├── configs.py
│   │   │       │   ├── channels.py    # 알림 채널 CRUD + 테스트 발송
│   │   │       │   ├── attempts.py
│   │   │       │   ├── logs.py        # 로그 조회 + SSE 스트림
│   │   │       │   └── deps.py        # current_user 의존성, rate limit
│   │   │       ├── schemas/           # 요청/응답 Pydantic 모델
│   │   │       ├── services/
│   │   │       │   ├── oci_client.py
│   │   │       │   ├── crypto.py
│   │   │       │   ├── auth.py        # argon2 해싱/검증, 세션
│   │   │       │   └── notifier/
│   │   │       │       ├── __init__.py    # send(channel, payload) 디스패치
│   │   │       │       ├── discord.py
│   │   │       │       ├── slack.py
│   │   │       │       ├── telegram.py
│   │   │       │       └── ntfy.py        # 커스텀 ntfy 서버 지원
│   │   │       └── workers/
│   │   │           ├── poller.py      # 메인 supervisor (config 별 task 관리)
│   │   │           ├── config_task.py # config 한 개당 비동기 루프
│   │   │           └── log_pruner.py  # 오래된 LogEntry 주기적 삭제
│   │   ├── alembic/
│   │   │   ├── env.py
│   │   │   └── versions/
│   │   ├── tests/                 # pytest 트리 (모듈 구조 미러)
│   │   │   ├── conftest.py        # 공용 fixture: db, client, oci mock
│   │   │   ├── unit/
│   │   │   │   ├── services/test_crypto.py
│   │   │   │   ├── services/test_notifier_ntfy.py
│   │   │   │   └── workers/test_config_task.py
│   │   │   ├── api/
│   │   │   │   ├── test_auth.py
│   │   │   │   ├── test_configs.py
│   │   │   │   └── test_channels.py
│   │   │   └── integration/
│   │   │       └── test_poller_supervisor.py
│   │   ├── pyproject.toml
│   │   ├── alembic.ini
│   │   └── Dockerfile
│   └── web/                       # Next.js 웹 — FSD (Feature-Sliced Design)
│       ├── app/                   # Next.js App Router (라우트 = 얇은 진입점만)
│       │   ├── login/page.tsx         # → src/pages/login
│       │   ├── (protected)/
│       │   │   ├── layout.tsx         # 미인증 가드 (서버 컴포넌트)
│       │   │   ├── page.tsx           # → src/pages/dashboard
│       │   │   ├── configs/page.tsx   # → src/pages/configs
│       │   │   ├── credentials/page.tsx
│       │   │   ├── channels/page.tsx
│       │   │   └── logs/page.tsx
│       │   ├── layout.tsx             # root layout + Providers
│       │   └── middleware.ts          # 세션 쿠키 부재 시 /login 리다이렉트
│       ├── src/                   # FSD 레이어
│       │   ├── app/                   # FSD app 레이어 (전역 설정)
│       │   │   ├── providers/         # QueryClientProvider, ThemeProvider
│       │   │   └── styles/globals.css
│       │   ├── pages/                 # 페이지 조합 (entities/features/widgets 사용)
│       │   │   ├── login/{ui,index.ts}
│       │   │   ├── dashboard/{ui,index.ts}
│       │   │   ├── configs/
│       │   │   ├── credentials/
│       │   │   ├── channels/
│       │   │   └── logs/
│       │   ├── widgets/               # 큰 UI 블록 (header, sidebar, log-viewer)
│       │   │   ├── header/
│       │   │   ├── sidebar/
│       │   │   └── log-stream/        # SSE 구독 + 가상 스크롤
│       │   ├── features/              # 사용자 액션 단위
│       │   │   ├── auth-login/
│       │   │   ├── auth-logout/
│       │   │   ├── config-create/
│       │   │   ├── config-toggle/
│       │   │   ├── credential-verify/
│       │   │   ├── channel-test/
│       │   │   └── log-filter/
│       │   ├── entities/              # 도메인 엔티티 (조회/표시 단위)
│       │   │   ├── config/{ui,model,api}
│       │   │   ├── credential/
│       │   │   ├── channel/
│       │   │   ├── attempt/
│       │   │   └── log/
│       │   └── shared/                # 도메인 무관 공용
│       │       ├── api/               # ★ Orval 자동 생성 (gitignored)
│       │       │   ├── auth/
│       │       │   ├── credentials/
│       │       │   ├── configs/
│       │       │   ├── channels/
│       │       │   ├── attempts/
│       │       │   ├── logs/
│       │       │   └── schemas/
│       │       ├── ui/                # shadcn/ui 래퍼, 버튼/입력 등
│       │       ├── lib/               # 유틸 (date, format, ...)
│       │       ├── config/            # 상수, env 접근
│       │       └── http/              # axios/fetch 인스턴스 (Orval mutator)
│       ├── tests/                     # 통합/시나리오 테스트 (단위는 slice 옆에 `*.test.tsx`)
│       │   ├── setup.ts               # vitest 셋업 (MSW 시작)
│       │   └── mocks/                 # MSW 핸들러
│       ├── orval.config.ts
│       ├── next.config.ts             # rewrites: /api/* → http://server:8000/api/*
│       ├── vitest.config.ts
│       ├── eslint.config.js           # eslint-plugin-boundaries (FSD 강제)
│       ├── package.json
│       ├── tsconfig.json              # paths: @/app, @/pages, @/widgets, @/features, @/entities, @/shared
│       └── Dockerfile
├── packages/                      # 공유 (현 시점 비어있음, 필요시 추가)
├── data/                          # 볼륨: SQLite DB, OCI private key
├── docker-compose.yml
├── pnpm-workspace.yaml            # apps/web, packages/* 등록
├── package.json                   # 루트 (스크립트만)
├── .env.example
├── .gitignore
├── README.md
└── prd.md
```

### pnpm workspace 설정

```yaml
# pnpm-workspace.yaml
packages:
  - "apps/web"
  - "packages/*"
```

`apps/server` 는 Python 이라 pnpm 영역 밖. 루트 `package.json` 스크립트로 통합 제어:

```json
{
  "scripts": {
    "dev:web": "pnpm --filter web dev",
    "dev:server": "cd apps/server && uvicorn app.main:app --reload --port 8000",
    "gen:api": "pnpm --filter web gen:api",
    "test:web": "pnpm --filter web test",
    "test:server": "cd apps/server && pytest -q --cov=app --cov-report=term-missing",
    "test": "pnpm test:server && pnpm test:web",
    "lint": "pnpm --filter web lint",
    "build": "pnpm --filter web build"
  }
}
```

### FSD 규칙 (웹)

#### 계층 (위 → 아래)
1. **`app`** — Providers, global styles, app-level setup
2. **`pages`** — 페이지 단위 조합 (Next.js `app/` 라우트가 import)
3. **`widgets`** — 큰 UI 블록 (sidebar/header/log-stream)
4. **`features`** — 사용자 액션 단위 (로그인, 설정 생성, 채널 테스트)
5. **`entities`** — 도메인 엔티티 (config/credential/channel/attempt/log)
6. **`shared`** — 도메인 무관 공용 (UI kit, API client, utils, config, http)

#### import 규칙 (`eslint-plugin-boundaries`)
- 상위 레이어는 하위 import 가능
- 하위 레이어는 상위 import **금지**
- 같은 레이어 다른 slice 직접 import **금지** — `shared` 또는 명시적 의존성으로만
- 각 slice 는 `index.ts` 로 공개 API 명시, 외부에서는 그것만 import

```js
// eslint.config.js (요지)
plugins: { boundaries },
settings: {
  'boundaries/elements': [
    { type: 'app',      pattern: 'src/app/*' },
    { type: 'pages',    pattern: 'src/pages/*' },
    { type: 'widgets',  pattern: 'src/widgets/*' },
    { type: 'features', pattern: 'src/features/*' },
    { type: 'entities', pattern: 'src/entities/*' },
    { type: 'shared',   pattern: 'src/shared/*' },
  ],
},
rules: {
  'boundaries/element-types': ['error', {
    default: 'disallow',
    rules: [
      { from: 'app',      allow: ['pages','widgets','features','entities','shared'] },
      { from: 'pages',    allow: ['widgets','features','entities','shared'] },
      { from: 'widgets',  allow: ['features','entities','shared'] },
      { from: 'features', allow: ['entities','shared'] },
      { from: 'entities', allow: ['shared'] },
      { from: 'shared',   allow: ['shared'] },
    ],
  }],
}
```

#### 라우트 ↔ FSD 매핑

Next.js `app/configs/page.tsx` 는 단순 진입점:
```tsx
import { ConfigsPage } from '@/pages/configs';
export default ConfigsPage;
```
복잡한 조합은 `src/pages/configs/ui/ConfigsPage.tsx` 에 위치.

### Next.js rewrites (서버 외부 노출 차단)

```ts
// apps/web/next.config.ts
const config = {
  async rewrites() {
    return [
      {
        source: '/api/:path*',
        destination: `${process.env.INTERNAL_API_URL ?? 'http://server:8000'}/api/:path*`,
      },
    ];
  },
};
```

- 브라우저는 항상 `http://localhost:3000/api/...` 만 호출 (same-origin)
- Next.js 서버가 내부 Docker 네트워크의 `server:8000` 으로 프록시
- 호스트에 `server` 컨테이너 포트 미노출 → 외부에서 직접 접근 불가
- SSE (`/api/logs/stream`) 도 rewrite 통해 정상 동작 (Next.js 가 chunked streaming 지원)

---

## 6. 데이터 모델 (SQLModel)

```python
# apps/server/src/app/db/models.py
from datetime import datetime
from typing import Optional
from sqlmodel import Field, Relationship, SQLModel


class OciCredential(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True, index=True)
    tenancy_ocid: str
    user_ocid: str
    fingerprint: str
    region: str                                # e.g. "ap-chuncheon-1"
    private_key_path: str                      # /data/keys/oci_api_key.pem
    passphrase_enc: str | None = None          # AES-encrypted
    created_at: datetime = Field(default_factory=datetime.utcnow)

    configs: list["InstanceConfig"] = Relationship(back_populates="credential")


class InstanceConfig(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str
    credential_id: int = Field(foreign_key="ocicredential.id")
    enabled: bool = True

    shape: str = "VM.Standard.A1.Flex"
    ocpus: int = 4
    memory_gb: int = 24
    boot_volume_gb: int = 50
    image_ocid: str
    subnet_ocid: str
    availability_domain: str
    ssh_public_key: str

    retry_interval_sec: int = 60
    max_attempts: int | None = None

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    credential: OciCredential = Relationship(back_populates="configs")
    attempts: list["Attempt"] = Relationship(back_populates="config")
    notification_channels: list["NotificationChannel"] = Relationship(
        back_populates="configs",
        link_model=lambda: ConfigChannelLink,
    )


class NotificationChannel(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    name: str = Field(unique=True)
    type: str = Field(index=True)              # "discord" | "slack" | "telegram" | "ntfy"
    enabled: bool = True
    config_enc: str                            # AES-256-GCM 암호화된 JSON (채널별 설정)
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    configs: list[InstanceConfig] = Relationship(
        back_populates="notification_channels",
        link_model=lambda: ConfigChannelLink,
    )


class ConfigChannelLink(SQLModel, table=True):
    config_id: int = Field(foreign_key="instanceconfig.id", primary_key=True)
    channel_id: int = Field(foreign_key="notificationchannel.id", primary_key=True)


class Attempt(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    config_id: int = Field(foreign_key="instanceconfig.id", index=True)
    attempted_at: datetime = Field(default_factory=datetime.utcnow, index=True)
    status: str                                # "success" | "out_of_capacity" | "rate_limited" | "auth_error" | "other_error"
    message: str | None = None
    instance_ocid: str | None = None
    duration_ms: int | None = None

    config: InstanceConfig = Relationship(back_populates="attempts")


class AppSetting(SQLModel, table=True):
    key: str = Field(primary_key=True)
    value: str


class LogEntry(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    timestamp: datetime = Field(default_factory=datetime.utcnow, index=True)
    level: str = Field(index=True)             # "DEBUG" | "INFO" | "WARNING" | "ERROR" | "CRITICAL"
    logger: str = Field(index=True)            # 예: "app.workers.poller", "app.services.oci_client"
    message: str
    config_id: int | None = Field(default=None, index=True)  # 컨텍스트 (있는 경우)
    attempt_id: int | None = None
    credential_id: int | None = None
    extra: str | None = None                   # 추가 컨텍스트 JSON 문자열
    exc_info: str | None = None                # traceback (ERROR 이상일 때)
```

SQLModel은 동일 클래스가 DB 테이블 + Pydantic 응답 스키마로 동작 → FastAPI 응답에 그대로 사용 가능. 단, 생성/수정 요청은 별도 `*Create`, `*Update` Pydantic 모델로 분리하여 read-only 필드 보호.

### NotificationChannel.config_enc 스키마 (타입별)

복호화 후 JSON 형태. API 응답에서는 sensitive 필드 (토큰/webhook URL) 마스킹.

```jsonc
// type = "discord"
{ "webhook_url": "https://discord.com/api/webhooks/..." }

// type = "slack"
{ "webhook_url": "https://hooks.slack.com/services/..." }

// type = "telegram"
{ "bot_token": "123456:ABC...", "chat_id": "-1001234567890" }

// type = "ntfy"
{
  "server_url": "https://ntfy.supabin.com",   // 또는 https://ntfy.sh
  "topic": "oci-arm-alerts",
  "token": "tk_xxx",                          // 선택: Bearer 토큰
  "priority": 4,                              // 1~5 (기본 3)
  "tags": ["rocket", "oracle"]                // 선택
}
```

Pydantic discriminated union 으로 타입 안전성 확보 (`Annotated[Union[...], Discriminator("type")]`).

---

## 7. 기능 요구사항

### 7.1 OCI 자격증명 관리
- 웹 UI 에서 OCI 자격증명 입력 (tenancy/user OCID, fingerprint, region, private key 업로드)
- private key 는 `/data/keys/{credential_id}.pem` 에 파일로 저장 (chmod 600)
- passphrase 는 AES-256-GCM 으로 암호화하여 DB 에 저장 (키는 `APP_SECRET` env)
- 자격증명 유효성 검증 엔드포인트 — OCI `ListAvailabilityDomains` 호출

### 7.2 인스턴스 설정
- 인스턴스 설정 CRUD + 활성화 토글
- 폼 필드: shape, OCPU, memory, boot volume, image OCID, subnet OCID, AD, SSH 공개키, 재시도 간격, 최대 시도 횟수, 알림 webhook
- 헬퍼 API: region 으로 사용 가능한 AD/이미지/서브넷 조회

### 7.3 워커 (FastAPI 내 백그라운드 task, 다중 계정 동시 처리)

#### 7.3.1 동시성 모델
- `lifespan` 진입 시 `asyncio.create_task(poller_supervisor())` 1개 기동
- **Supervisor 루프** (`workers/poller.py`):
  - 10초마다 DB 에서 `InstanceConfig.enabled = True` 목록 조회
  - 현재 실행 중인 config task 와 비교
    - 새로 활성화 → `asyncio.create_task(run_config_task(config))` spawn
    - 비활성화 또는 삭제 → 해당 task `.cancel()`
    - config 수정 (retry_interval, sshkey 등) → task 재시작
- **Config task** (`workers/config_task.py`):
  - 자기 config 의 `retry_interval_sec` 으로 자체 sleep
  - 매 시도 시 `credential_semaphores[credential_id]` 획득 (기본 max=1) → 같은 계정 직렬화, 다른 계정 병렬
  - `asyncio.to_thread(client.launch_instance, ...)` 로 OCI 동기 SDK 호출
  - 성공 → `Attempt(status="success", instance_ocid=...)` 저장, 모든 연결된 채널로 알림, `config.enabled = False` 후 task 자가 종료
  - `OutOfCapacity` → `Attempt(status="out_of_capacity")` 저장 (알림 없음 — 노이즈 방지)
  - `429 TooManyRequests` → `tenacity` 지수 백오프 + `rate_limited` 기록 + 다음 sleep 연장
  - 인증/권한 오류 → `auth_error` 기록 + `config.enabled = False` + **인증 오류 알림 발송** + task 종료
- **글로벌 가드**: 전역 `asyncio.Semaphore(max_concurrent=10)` 로 동시 OCI 호출 총량 상한
- **계정 단위 가드**: `credential_semaphores: dict[int, Semaphore]` (기본 max=1, env 로 조정 가능)
- shutdown 신호 시 모든 task graceful cancel (`asyncio.wait` + `CancelledError` 전파)

#### 7.3.2 로그 컨텍스트
모든 로그 호출에 `extra={"config_id": ..., "attempt_id": ..., "credential_id": ...}` 컨텍스트 동봉 → DB 의 `LogEntry` 컬럼으로 매핑.

(v0.2 개선: `contextvars` 로 config task 진입 시점에 묶어 자동 주입)

### 7.4 대시보드
- 활성/비활성 설정 카운트
- 최근 50개 시도 이력 테이블 (필터: 설정별/상태별)
- 실시간 업데이트 — TanStack Query `refetchInterval` 5초 (SSE 는 v0.2)
- 성공한 인스턴스 정보 카드 (OCID, 생성 시각)

### 7.5 알림 (다중 채널 + ntfy 지원)

#### 7.5.1 지원 채널
| 타입 | 발송 방식 | 비고 |
|---|---|---|
| `discord` | POST `webhook_url` (JSON `{content, embeds}`) | |
| `slack` | POST `webhook_url` (JSON Block Kit) | |
| `telegram` | POST `https://api.telegram.org/bot{token}/sendMessage` | `parse_mode=HTML` |
| `ntfy` | POST `{server_url}/{topic}` (text body) | 헤더: `Title`, `Priority`, `Tags`, `Authorization: Bearer {token}` (옵션) — **self-hosted 서버 (예: `ntfy.supabin.com`) 그대로 사용** |

#### 7.5.2 채널 관리
- 웹 `/channels` 페이지에서 CRUD
- 타입 선택 시 폼이 동적으로 바뀜 (Discord 면 webhook 1개, ntfy 면 server/topic/token/priority 등)
- **테스트 발송 버튼** — `POST /api/channels/{id}/test` → 채널로 "테스트 메시지" 보내고 결과(`ok: bool, error?: str`) 반환
- 토큰/webhook URL 은 저장 시 AES-256-GCM 암호화, API 응답에서는 마스킹 (`***` + 마지막 4자리)

#### 7.5.3 발송 시점
| 이벤트 | 발송 여부 | 우선순위 (ntfy) |
|---|---|---|
| 인스턴스 생성 성공 | 필수 | 5 (max) |
| 인증/권한 오류로 config 비활성화 | 필수 | 4 |
| `OutOfCapacity` (개별) | **발송 안 함** (노이즈 방지) | — |
| `rate_limited` 가 5분 이상 지속 | 옵션 (v0.2) | 3 |

#### 7.5.4 발송 흐름
- 알림 트리거 → `services.notifier.send(channel, payload)` 디스패치
- 각 채널 모듈 (`discord.py`, `slack.py`, `telegram.py`, `ntfy.py`) 가 자기 포맷 변환 + `httpx.AsyncClient.post(...)` 수행
- 타임아웃 5초, 실패 시 재시도 2회 (`tenacity`), 최종 실패는 ERROR 로그만 남기고 워커는 계속 진행
- config 가 여러 채널에 연결되어 있으면 `asyncio.gather(*[send(ch, payload) for ch in channels], return_exceptions=True)` 로 병렬 발송

#### 7.5.5 ntfy 발송 예시
```python
# services/notifier/ntfy.py
async def send(cfg: dict, payload: NotificationPayload) -> None:
    headers = {
        "Title": payload.title,
        "Priority": str(cfg.get("priority", 3)),
        "Tags": ",".join(cfg.get("tags", [])),
    }
    if token := cfg.get("token"):
        headers["Authorization"] = f"Bearer {token}"
    url = f"{cfg['server_url'].rstrip('/')}/{cfg['topic']}"
    async with httpx.AsyncClient(timeout=5.0) as client:
        r = await client.post(url, content=payload.body.encode("utf-8"), headers=headers)
        r.raise_for_status()
```

#### 7.5.6 메시지 포맷 통일
공통 `NotificationPayload`:
```
title:   "✅ OCI 인스턴스 생성 성공" / "⚠️ OCI 인증 오류"
body:    "Config: {config.name}\n계정: {credential.name}\n시각: {ts}\n인스턴스 OCID: {ocid}\n오류: {msg}"
tags:    ["success" | "error" | "warning"]
```
각 채널 모듈이 자기 채널 표현에 맞게 변환 (Discord embed / Slack block / ntfy header).

### 7.6 로그 뷰어 (웹)
- 별도 페이지 `/logs` 에서 실시간 + 과거 로그 조회
- 필터: 레벨 (DEBUG/INFO/WARNING/ERROR/CRITICAL 멀티 선택), logger 이름 (prefix 매칭), `config_id`, 기간
- 검색: 메시지 부분 문자열 (서버 측 `LIKE`)
- 표시: 타임스탬프 (사용자 로컬 타임존), 레벨 배지(색), logger, 메시지, 컨텍스트 (펼침)
- ERROR 이상은 traceback 펼침 표시
- 실시간 모드 ↔ 일시정지 토글 — 일시정지 시 SSE 구독 해제, 새로고침 시 재구독
- 자동 스크롤 (실시간 모드, 새 로그 들어오면 하단으로) — 사용자가 스크롤 위로 올리면 자동 일시정지
- 로그 삭제 (관리자 액션, 확인 모달) — `DELETE /api/logs?before=...`
- 한 화면 최대 500행 → 초과 시 가상 스크롤 (`@tanstack/react-virtual`)

### 7.7 인증 (단일 관리자)

#### 7.7.1 정책
- 회원가입 없음. 비밀번호 재설정 UI 없음 (env 변경 + 재배포로 처리)
- 로그인 가능한 계정은 env (`APP_USERNAME`, `APP_PASSWORD_HASH`) 에 박힌 **1쌍**뿐
- 비밀번호는 평문이 아닌 **Argon2id 해시**를 env 로 주입 (`APP_PASSWORD_HASH`)
- 부트스트랩 헬퍼 CLI: `python -m app.cli hash <password>` → 해시 출력 (env 에 복사)

#### 7.7.2 흐름
- `POST /api/auth/login {username, password}` → argon2 검증 → 세션 쿠키 발급 (`session=...`, HTTP-only, SameSite=Lax, Secure=true in prod)
- `POST /api/auth/logout` → 세션 무효화
- `GET /api/auth/me` → 로그인 상태 확인 (`{username}` 또는 401)
- 보호된 모든 엔드포인트는 `Depends(require_login)` — 미인증 시 401
- `/healthz` 와 `/api/auth/login` 만 공개

#### 7.7.3 무차별 대입 방어
- `POST /api/auth/login` 에 `slowapi` rate limit — **IP 당 5회/분**, 초과 시 429
- 연속 실패 10회 → 해당 IP 5분간 차단 (in-memory)
- 로그인 시도 (성공/실패 모두) WARNING 레벨로 로그 기록

#### 7.7.4 Next.js 측 가드
- `app/middleware.ts` 가 `session` 쿠키 부재 시 `/login` 으로 리다이렉트
- 단, `/login` 자체는 제외
- API 호출은 `credentials: 'include'` 로 쿠키 자동 전송 (CORS allow-credentials 설정 필요)

---

## 8. API 설계 (FastAPI)

모든 응답은 SQLModel 기반 자동 OpenAPI 스키마.

모든 엔드포인트는 `/healthz` 와 `/api/auth/login` 을 제외하고 **세션 쿠키 인증 필수** (`Depends(require_login)`).

| Method | Path | 설명 | 응답 |
|---|---|---|---|
| **POST** | `/api/auth/login` | 로그인 (rate limit 5/min/IP) | `{username}` + Set-Cookie |
| **POST** | `/api/auth/logout` | 로그아웃 | 204 |
| **GET** | `/api/auth/me` | 현재 세션 확인 | `{username}` or 401 |
| GET | `/api/credentials` | 목록 | `list[CredentialRead]` |
| POST | `/api/credentials` | 생성 (multipart: form + private key file) | `CredentialRead` |
| POST | `/api/credentials/{id}/verify` | OCI 호출로 유효성 검증 | `{ok: bool, error?: str}` |
| DELETE | `/api/credentials/{id}` | 삭제 | 204 |
| GET | `/api/configs` | 설정 목록 (channel_ids 포함) | `list[ConfigRead]` |
| POST | `/api/configs` | 생성 (channel_ids: list[int]) | `ConfigRead` |
| PUT | `/api/configs/{id}` | 수정 (channel_ids 갱신 포함) | `ConfigRead` |
| DELETE | `/api/configs/{id}` | 삭제 | 204 |
| POST | `/api/configs/{id}/toggle` | 활성화 토글 (supervisor 가 감지하여 task spawn/cancel) | `ConfigRead` |
| **GET** | `/api/channels` | 알림 채널 목록 (sensitive 마스킹) | `list[ChannelRead]` |
| **POST** | `/api/channels` | 생성 (type 별 폼) | `ChannelRead` |
| **PUT** | `/api/channels/{id}` | 수정 | `ChannelRead` |
| **DELETE** | `/api/channels/{id}` | 삭제 | 204 |
| **POST** | `/api/channels/{id}/test` | 테스트 발송 | `{ok: bool, error?: str}` |
| GET | `/api/attempts` | 시도 이력 (쿼리: config_id, status, limit) | `list[AttemptRead]` |
| GET | `/api/logs` | 로그 조회 (쿼리: levels, logger, config_id, since, until, q, limit, cursor) | `LogPage` |
| GET | `/api/logs/stream` | SSE — 신규 로그 푸시 (필터 쿼리 동일) | `text/event-stream` |
| DELETE | `/api/logs?before=<iso>` | 지정 시각 이전 로그 삭제 (관리자) | 204 |
| GET | `/api/meta/availability-domains?credential_id=` | OCI 조회 헬퍼 | `list[str]` |
| GET | `/api/meta/images?credential_id=&region=` | OCI 조회 헬퍼 | `list[ImageRead]` |
| GET | `/healthz` | 헬스체크 (공개) | `{status: "ok"}` |

### 표준 에러 응답

모든 4xx/5xx 응답은 다음 스키마.

```jsonc
// 400/401/403/404/409/422/429/500
{
  "error": {
    "code": "config_not_found",          // 도메인 코드 (snake_case)
    "message": "InstanceConfig id=42 not found",  // 사람이 읽는 영문
    "details": {                         // optional, 구조화 컨텍스트
      "config_id": 42
    },
    "request_id": "01HRY8..."            // 미들웨어가 부여한 ULID
  }
}
```

#### 도메인 에러 코드 (안정)

| code | HTTP | 의미 |
|---|---|---|
| `unauthorized` | 401 | 세션 없음/만료 |
| `forbidden` | 403 | 권한 부족 (현재 미사용, 예약) |
| `not_found` | 404 | 일반 미존재 |
| `credential_not_found` | 404 | OCI 자격증명 미존재 |
| `config_not_found` | 404 | InstanceConfig 미존재 |
| `channel_not_found` | 404 | NotificationChannel 미존재 |
| `validation_error` | 422 | Pydantic 검증 실패 (`details` 에 필드별 에러) |
| `rate_limited` | 429 | 로그인 시도 초과 등 |
| `oci_auth_error` | 502 | OCI 자격증명 무효 (verify 시) |
| `oci_request_failed` | 502 | OCI API 호출 실패 |
| `ntfy_send_failed` | 502 | ntfy 채널 발송 실패 |
| `internal_error` | 500 | 처리되지 않은 예외 (`request_id` 로 로그 추적) |

#### FastAPI 구현

```python
# app/api/deps.py
class AppError(Exception):
    def __init__(self, code: str, status_code: int, message: str, details: dict | None = None):
        self.code, self.status_code, self.message, self.details = code, status_code, message, details

@app.exception_handler(AppError)
async def app_error_handler(req, exc):
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message, "details": exc.details, "request_id": req.state.request_id}},
    )

# 호출 예
raise AppError("config_not_found", 404, f"InstanceConfig id={cfg_id} not found", {"config_id": cfg_id})
```

`request_id` 는 `RequestIdMiddleware` 가 ULID 부여 후 `request.state` 와 응답 헤더 `X-Request-Id` 에 설정. 모든 로그에 자동 포함.

### 요청/응답 JSON 예시

#### POST `/api/auth/login`
```jsonc
// req
{ "username": "admin", "password": "..." }
// 200
{ "username": "admin" }
// Set-Cookie: session=...; HttpOnly; SameSite=Lax
// 401
{ "error": { "code": "unauthorized", "message": "Invalid credentials", "details": null, "request_id": "..." } }
// 429
{ "error": { "code": "rate_limited", "message": "Too many login attempts", "details": { "retry_after_sec": 60 }, "request_id": "..." } }
```

#### POST `/api/credentials` (multipart)
```jsonc
// fields:  name, tenancy_ocid, user_ocid, fingerprint, region, passphrase?
// file:    private_key (PEM)

// 201
{
  "id": 1,
  "name": "main",
  "tenancy_ocid": "ocid1.tenancy.oc1..aaa***",   // 마스킹
  "user_ocid": "ocid1.user.oc1..aaa***",
  "fingerprint": "ab:cd:**:**:**",
  "region": "ap-chuncheon-1",
  "has_passphrase": true,
  "created_at": "2026-06-03T10:23:45Z"
}
```

#### POST `/api/configs`
```jsonc
// req
{
  "name": "ARM 4OCPU main",
  "credential_id": 1,
  "shape": "VM.Standard.A1.Flex",
  "ocpus": 4,
  "memory_gb": 24,
  "boot_volume_gb": 50,
  "image_ocid": "ocid1.image.oc1.ap-chuncheon-1.aaa...",
  "subnet_ocid": "ocid1.subnet.oc1.ap-chuncheon-1.aaa...",
  "availability_domain": "Uocm:AP-CHUNCHEON-1-AD-1",
  "ssh_public_key": "ssh-ed25519 AAAA... user@host",
  "retry_interval_sec": 60,
  "max_attempts": null,
  "channel_ids": [1, 2]
}
// 201
{
  "id": 5,
  "name": "ARM 4OCPU main",
  "enabled": true,
  /* ... */
  "channel_ids": [1, 2],
  "created_at": "2026-06-03T10:24:00Z",
  "updated_at": "2026-06-03T10:24:00Z"
}
```

#### POST `/api/channels` (ntfy 예시)
```jsonc
// req
{
  "name": "supabin ntfy",
  "type": "ntfy",
  "enabled": true,
  "config": {
    "server_url": "https://ntfy.supabin.com",
    "topic": "oci-arm-alerts",
    "token": "tk_xxx",
    "priority": 4,
    "tags": ["rocket"]
  }
}
// 201 (sensitive 마스킹)
{
  "id": 2,
  "name": "supabin ntfy",
  "type": "ntfy",
  "enabled": true,
  "config": {
    "server_url": "https://ntfy.supabin.com",
    "topic": "oci-arm-alerts",
    "token": "***xxx",         // 마스킹
    "priority": 4,
    "tags": ["rocket"]
  }
}
```

#### POST `/api/channels/{id}/test`
```jsonc
// req body 없음
// 200 (성공)
{ "ok": true }
// 200 (실패도 200, ok=false)
{ "ok": false, "error": "Connect timeout to https://ntfy.supabin.com" }
```

#### GET `/api/logs?levels=ERROR&levels=WARNING&q=auth&limit=50`
```jsonc
{
  "items": [
    {
      "id": 12834,
      "timestamp": "2026-06-03T10:30:11.234Z",
      "level": "ERROR",
      "logger": "app.workers.config_task",
      "message": "OCI 인증 오류로 config 자동 비활성화",
      "config_id": 5,
      "attempt_id": 142,
      "credential_id": 1,
      "extra": null,
      "exc_info": "Traceback ..."
    }
  ],
  "next_cursor": "MTI4MzM=",     // base64(last_id)
  "has_more": true
}
```

#### GET `/api/logs/stream` (SSE)
```
event: log
data: {"id":12835,"timestamp":"2026-06-03T10:30:12Z","level":"INFO","logger":"app.workers.config_task","message":"OCI launch_instance 시도","config_id":5}

event: ping
data: {}

event: log
data: { ... }
```
heartbeat `ping` 은 15초마다 (프록시 idle timeout 회피).

### Orval 흐름

```ts
// apps/web/orval.config.ts
export default {
  api: {
    input: process.env.OPENAPI_URL ?? 'http://localhost:8000/openapi.json',
    output: {
      target: 'lib/api/index.ts',
      mode: 'tags-split',           // 태그별로 폴더 분리
      client: 'react-query',
      schemas: 'lib/api/schemas',
      override: {
        mutator: {
          path: 'lib/http.ts',
          name: 'httpClient',
        },
      },
    },
  },
};
```

`pnpm gen:api` 실행 시 FastAPI 의 OpenAPI 를 fetch 하여 `lib/api/` 아래에 React Query 훅 (`useGetCredentials`, `useCreateConfigMutation` 등) 자동 생성.

### FastAPI 라우터에서 태그 명시

```python
router = APIRouter(prefix="/api/configs", tags=["configs"])
```

태그 기반 분리 → Orval 이 `lib/api/configs/configs.ts` 로 묶음 → import 동선 깔끔.

---

## 9. 비기능 요구사항

### 9.1 보안
- OCI private key 파일은 컨테이너 내부 `chmod 600`, 호스트 볼륨 마운트
- private key passphrase, **알림 채널 토큰/webhook URL** → DB 저장 시 AES-256-GCM 암호화 (`cryptography`)
- 인증:
  - 단일 관리자 — env `APP_USERNAME` + `APP_PASSWORD_HASH` (Argon2id)
  - 회원가입 엔드포인트 없음
  - 세션 쿠키: HTTP-only, `SameSite=Lax`, prod 에서 `Secure=true`
  - 로그인 rate limit (IP 당 5회/분, `slowapi`), 10회 연속 실패 시 5분 IP 차단
- **API 서버 외부 노출 차단 (1차 방어선)**:
  - `docker-compose.yml` 에서 server 컨테이너는 `ports` 미선언, `expose: ["8000"]` 만
  - 호스트의 8000 포트로 직접 접근 불가 (`curl localhost:8000/...` 실패)
  - 브라우저는 `http://localhost:3000/api/...` 만 호출, Next.js 가 내부 네트워크로 프록시
- **CORS (2차 방어선)**:
  - 프로덕션 (Next.js 프록시 경유) 에서는 server 가 보는 Origin 이 없거나 내부 → CORS preflight 트리거 안 됨
  - dev (web 따로 띄울 때) 를 위해 FastAPI 가 `CORS_ORIGINS` env 의 출처만 허용 + `allow_credentials=True`
  - 모르는 Origin 의 요청은 거부
- HTTPS 종단은 리버스 프록시 (Caddy/Nginx) 가 담당 — 본 시스템 외부
- API 응답에서 민감 필드 (private key, 토큰, webhook URL, passphrase) 는 항상 마스킹

### 9.2 동시성 (다중 계정 + 다중 config 병렬)
- SQLite WAL 모드 (`PRAGMA journal_mode=WAL`) — 여러 task 가 동시에 읽기 안전
- 워커와 API 요청 핸들러가 같은 프로세스 → 별도 IPC 불필요
- SQLModel 세션은 요청/태스크 단위로 분리 (task 시작 시 new session, 종료 시 close)
- **계정별 Semaphore**: `credential_semaphores[credential_id]` 기본 max=1 → 동일 OCI 테넌시 호출 직렬화 (rate limit 회피)
- **전역 Semaphore**: `OCI_MAX_CONCURRENT` (env, 기본 10) → 시스템 전체 동시 호출 상한
- 알림은 별도 흐름 — config task 와 독립 (실패해도 OCI 호출 영향 없음)
- 백그라운드 task 가 DB 쓸 때 `INSERT/UPDATE` 만 — supervisor 가 활성 목록을 캐시하지 않고 매번 조회 (작은 N 에 충분)

### 9.3 로깅 (커스텀 설계)

#### 9.3.1 목표
1. 사람이 읽는 stdout 로그 (Docker `docker compose logs`)
2. 구조화된 영구 저장 (DB `LogEntry`) — 웹 UI 에서 검색/필터링
3. 웹 UI 실시간 스트리밍 (SSE)
4. 컨텍스트 자동 전파 (`config_id`, `attempt_id`, `credential_id`)
5. 한 곳에서 부트스트랩 — 일반 코드는 `logger = logging.getLogger(__name__)` 만 알면 됨
6. 시도 이력은 DB `Attempt` 테이블이 정식 기록 (LogEntry 는 보조적 운영 로그)

#### 9.3.2 핸들러 구성

| 핸들러 | 출력 | 레벨 임계값 | 포맷 |
|---|---|---|---|
| `StreamHandler(stdout)` | Docker stdout | `LOG_LEVEL` (env, 기본 INFO) | JSON (`JsonFormatter`) |
| `DbLogHandler` | `LogEntry` 테이블 | INFO 이상 (env로 별도 조정) | dict → INSERT |
| `LogBusHandler` | 인메모리 pub/sub | INFO 이상 | dict → 구독자 큐 |

루트 로거에 3개 핸들러 부착. 라이브러리 로그 (`uvicorn`, `sqlalchemy`) 는 별도 레벨 설정 (기본 WARNING).

#### 9.3.3 커스텀 JsonFormatter 출력 예시

```json
{
  "ts": "2026-06-03T10:23:45.123Z",
  "level": "ERROR",
  "logger": "app.workers.poller",
  "message": "OCI launch_instance 호출 실패",
  "config_id": 3,
  "attempt_id": 142,
  "exc_info": "Traceback (most recent call last):\n  ..."
}
```

#### 9.3.4 컨텍스트 주입 패턴

```python
logger.info(
    "OCI 인스턴스 생성 시도",
    extra={"config_id": config.id, "attempt_id": attempt.id},
)
```

`JsonFormatter` 와 `DbLogHandler` 가 `record.__dict__` 에서 사전 정의 키 (`config_id`, `attempt_id`, `credential_id`) 를 추출하여 컬럼/JSON 필드로 매핑.

선택: 폴링 루프에서 `contextvars` 로 `config_id` 를 묶고, `logging.Filter` 로 자동 주입 → 매 호출마다 `extra=` 안 써도 됨 (v0.2 개선 항목).

#### 9.3.5 DbLogHandler 안전성

- **동기 INSERT**: `emit()` 은 동기 메서드 — SQLite 동기 INSERT 사용 (트래픽 낮음, 충분)
- **재귀 방지**: 핸들러 자체에서 발생하는 로그/SQLAlchemy 내부 로그는 propagate 차단 (필터로 logger name prefix 제외)
- **장애 격리**: `emit()` 내부 예외는 `self.handleError(record)` 로 stderr 만 출력 → 앱 흐름에 영향 없음
- **배치 옵션 (v0.2)**: 트래픽 증가 시 `QueueHandler` + 별도 비동기 워커로 배치 flush

#### 9.3.6 LogBus (인메모리 pub/sub)

```python
# app/log_bus.py
class LogBus:
    def __init__(self) -> None:
        self._subscribers: set[asyncio.Queue[dict]] = set()

    def publish(self, record: dict) -> None:
        for q in list(self._subscribers):
            try:
                q.put_nowait(record)
            except asyncio.QueueFull:
                pass  # 느린 구독자는 버림 (back-pressure)

    @asynccontextmanager
    async def subscribe(self) -> AsyncIterator[asyncio.Queue[dict]]:
        q: asyncio.Queue[dict] = asyncio.Queue(maxsize=500)
        self._subscribers.add(q)
        try:
            yield q
        finally:
            self._subscribers.discard(q)

log_bus = LogBus()
```

`LogBusHandler.emit()` 이 `log_bus.publish(...)` 호출. SSE 엔드포인트는 `log_bus.subscribe()` 로 큐를 받아 yield.

#### 9.3.7 SSE 엔드포인트 (sse-starlette)

```python
from sse_starlette.sse import EventSourceResponse

@router.get("/api/logs/stream")
async def stream_logs(level: str | None = None, config_id: int | None = None):
    async def gen():
        async with log_bus.subscribe() as q:
            while True:
                rec = await q.get()
                if level and rec["level"] != level: continue
                if config_id is not None and rec.get("config_id") != config_id: continue
                yield {"event": "log", "data": json.dumps(rec)}
    return EventSourceResponse(gen())
```

#### 9.3.8 로그 보존 정책

- 보존: 최근 **7일** 또는 **최대 10,000행** 중 먼저 도달
- 정리: `workers/log_pruner.py` 가 5분마다 깨어나 cutoff 기준으로 DELETE
- 정책 값은 `AppSetting` 에 저장 → 추후 UI 에서 조정 가능

#### 9.3.9 환경 변수

| 변수 | 기본값 | 설명 |
|---|---|---|
| `LOG_LEVEL` | `INFO` | stdout/DB/Bus 공통 최소 레벨 |
| `LOG_LEVEL_DB` | (= `LOG_LEVEL`) | DB 핸들러만 별도 조정 (DEBUG 폭주 방지) |
| `LOG_RETENTION_DAYS` | `7` | LogEntry 보존 기간 |
| `LOG_RETENTION_ROWS` | `10000` | LogEntry 최대 행 수 |

### 9.4 에러 복구
- 컨테이너 크래시 시 Docker Compose `restart: unless-stopped`
- DB 마이그레이션 실패 시 서버 시작 차단 (init 컨테이너에서 `alembic upgrade head`)

### 9.5 테스트 (의무화)

#### 9.5.1 원칙
- **commit 단위마다 테스트 동봉 필수** — task 파일의 모든 구현 하위작업은 `T1 (테스트 작성)` + `T2 (테스트 실행/검증)` 서브태스크를 포함
- 테스트 없이 PR/커밋 금지 — `task-executor` 가 거부
- 외부 IO (OCI SDK, httpx, 파일 시스템) 는 모킹. SQLite 는 in-memory (`sqlite:///:memory:`) 또는 임시 파일

#### 9.5.2 서버 (Python / pytest)
- 디렉토리: `apps/server/tests/{unit,api,integration}/`
- fixture (`conftest.py`):
  - `engine` — in-memory SQLite, schema 자동 생성
  - `session` — 트랜잭션 롤백 기반 격리
  - `client` — `httpx.AsyncClient(transport=ASGITransport(app))`
  - `oci_mock` — `oci.core.ComputeClient` 메서드 패치
  - `authed_client` — 미리 로그인된 세션 쿠키 포함
- 명령:
  ```bash
  pytest -q                                          # 빠른 실행
  pytest -q --cov=app --cov-report=term-missing     # 커버리지
  pytest tests/api/test_configs.py -q               # 특정 파일
  ```
- 커버리지 목표: **70% 이상** (services/workers 는 80%+)
- 비동기 테스트: `pytest-asyncio` (`@pytest.mark.asyncio`, `asyncio_mode = "auto"`)
- 외부 호출 차단: `pytest-httpx` 로 httpx 가로채기, 통과 안 된 호출은 실패

#### 9.5.3 웹 (Vitest + RTL + MSW)
- 단위 테스트: slice 옆에 `*.test.tsx` (예: `src/features/auth-login/ui/LoginForm.test.tsx`)
- 통합/시나리오: `tests/` 디렉토리 (페이지 단위)
- API 모킹: **MSW** — Orval 이 생성한 핸들러 또는 수동 핸들러 (`tests/mocks/handlers.ts`)
- 셋업 (`tests/setup.ts`):
  ```ts
  import { beforeAll, afterAll, afterEach } from 'vitest';
  import { server } from './mocks/server';
  beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
  afterEach(() => server.resetHandlers());
  afterAll(() => server.close());
  ```
- 명령:
  ```bash
  pnpm test                  # vitest run (CI 모드)
  pnpm test:watch            # 개발 중
  pnpm test --coverage
  ```
- 커버리지 목표: **50% 이상** (features/entities 는 70%+)
- 미처리 네트워크 호출은 테스트 실패 → MSW handler 누락 즉시 감지

#### 9.5.4 테스트 분류 가이드

| 범주 | 위치 | 대상 |
|---|---|---|
| Unit | `unit/` (server), slice 옆 (web) | 순수 함수, 컴포넌트 렌더, 훅 |
| API | `api/` (server) | FastAPI 엔드포인트 — DB + auth fixture 결합 |
| Integration | `integration/` (server), `tests/` (web) | 여러 모듈 결합 시나리오 |
| E2E | (v0.2) Playwright | 로그인 → 설정 등록 → 폴링 → 알림 |

#### 9.5.5 CI 게이트 (GitHub Actions, v0.2)
- PR/push 시 다음 단계 통과 필수:
  1. `pytest --cov` (커버리지 임계값)
  2. `ruff check` + `mypy`
  3. `pnpm test --coverage`
  4. `pnpm lint` (eslint-plugin-boundaries 포함 → FSD 위반 자동 감지)
  5. `pnpm tsc --noEmit`

#### 9.5.6 task-executor 에이전트 동작
- `T1`: 구현과 함께 테스트 파일 작성 (테스트 먼저 작성도 권장)
- `T2`: 관련 테스트 + 인접 테스트 실행
  - 서버: `pytest -q tests/...`
  - 웹: `pnpm vitest run [path]`
- 실패 시 `T3 (오류 수정)` 자동 추가

---

## 10. 배포 (Docker Compose)

```yaml
# docker-compose.yml (스케치)
services:
  server:
    build:
      context: .
      dockerfile: apps/server/Dockerfile
    # ports 미선언 — 호스트에 8000 노출 안 함 (외부 접근 차단)
    expose: ["8000"]                # 같은 Compose 네트워크 안의 web 만 접근 가능
    environment:
      DATABASE_URL: sqlite:////data/app.db
      APP_SECRET: ${APP_SECRET}
      APP_USERNAME: ${APP_USERNAME}
      APP_PASSWORD_HASH: ${APP_PASSWORD_HASH}
      CORS_ORIGINS: ${CORS_ORIGINS}
      OCI_MAX_CONCURRENT: ${OCI_MAX_CONCURRENT:-10}
      OCI_PER_CREDENTIAL_MAX: ${OCI_PER_CREDENTIAL_MAX:-1}
      LOG_LEVEL: ${LOG_LEVEL:-INFO}
      LOG_LEVEL_DB: ${LOG_LEVEL_DB:-INFO}
      LOG_RETENTION_DAYS: ${LOG_RETENTION_DAYS:-7}
      LOG_RETENTION_ROWS: ${LOG_RETENTION_ROWS:-10000}
    volumes:
      - ./data:/data
    restart: unless-stopped
    healthcheck:
      test: ["CMD", "curl", "-f", "http://localhost:8000/healthz"]
      interval: 30s
      timeout: 5s
      retries: 3

  web:
    build:
      context: .
      dockerfile: apps/web/Dockerfile
    ports: ["3000:3000"]            # 호스트에 노출되는 유일한 포트
    environment:
      INTERNAL_API_URL: http://server:8000      # Next.js rewrites 가 사용 (브라우저에는 노출 안 됨)
    depends_on:
      server:
        condition: service_healthy
    restart: unless-stopped
```

### `apps/server/Dockerfile` 핵심
```dockerfile
FROM python:3.12-slim-bookworm
WORKDIR /app
RUN pip install --no-cache-dir uv
COPY apps/server/pyproject.toml apps/server/uv.lock* ./
RUN uv sync --frozen --no-dev
COPY apps/server/ .
CMD ["sh", "-c", "alembic upgrade head && uvicorn app.main:app --host 0.0.0.0 --port 8000"]
```

### `apps/web/Dockerfile` 핵심 (multi-stage + pnpm)
```dockerfile
FROM node:20-bookworm-slim AS deps
RUN corepack enable
WORKDIR /app
COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
COPY apps/web/package.json apps/web/
RUN pnpm install --frozen-lockfile

FROM node:20-bookworm-slim AS builder
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY --from=deps /app/apps/web/node_modules ./apps/web/node_modules
COPY . .
# OpenAPI 가 빌드 시 필요하면 server 띄운 뒤 gen:api 후 build
RUN pnpm --filter web build

FROM node:20-bookworm-slim AS runner
WORKDIR /app
COPY --from=builder /app/apps/web/.next/standalone ./
COPY --from=builder /app/apps/web/.next/static ./apps/web/.next/static
COPY --from=builder /app/apps/web/public ./apps/web/public
CMD ["node", "apps/web/server.js"]
```

`.env.example`:
```
# 보안
APP_SECRET=                       # 32 bytes base64 — 세션 서명 + AES-256-GCM 키 도출
APP_USERNAME=admin                # 단일 관리자 사용자명
APP_PASSWORD_HASH=                # Argon2id 해시 — `python -m app.cli hash <password>` 로 생성
CORS_ORIGINS=http://localhost:3000

# 프런트 (브라우저는 same-origin /api 만 사용, INTERNAL_API_URL 은 Next.js 서버만 봄)
INTERNAL_API_URL=http://server:8000

# 동시성
OCI_MAX_CONCURRENT=10             # 전역 동시 OCI 호출 상한
OCI_PER_CREDENTIAL_MAX=1          # 계정당 동시 호출 상한 (1 권장)

# 로깅
LOG_LEVEL=INFO
LOG_LEVEL_DB=INFO
LOG_RETENTION_DAYS=7
LOG_RETENTION_ROWS=10000
```

초기 부트스트랩 절차 (README 에 동일 기재):
```bash
# 1. 비밀번호 해시 생성
docker compose run --rm server python -m app.cli hash "내비밀번호"
# 출력된 $argon2id$... 해시를 .env 의 APP_PASSWORD_HASH 에 붙여넣기

# 2. APP_SECRET 생성 (32 bytes base64)
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"

# 3. 스택 기동
docker compose up -d
```

---

## 11. MVP 범위 vs 추후 확장

### 진행 모델: 에이전트 팀

- `push-lead` 가 task 파일을 읽고 작업 유형별로 서브에이전트에 위임
- `server-worker` — Python/FastAPI/SQLModel/Alembic/워커/알림 채널/OCI SDK
- `web-worker` — Next.js/FSD/Orval/shadcn/Tailwind/MSW
- `test-runner` — pytest + vitest 실행, 실패 시 직접 수정 또는 `T3` 등록
- 같은 Push 안에서 독립 작업(server vs web)은 **병렬**, 의존 작업은 **순차**
- 모든 서브에이전트는 다음 스킬을 참조:
  - `fsd-architecture` (web), `fastapi-patterns` (server), `python-testing`, `web-testing`, `oss-selection`, `oci-sdk`, `notification-channels`

### MVP (Push 1~5)
- Push 1: 모노레포 인프라 — pnpm workspace, **FSD 디렉토리 + eslint-plugin-boundaries**, Docker, Alembic, FastAPI 헬스체크, Next.js + Tailwind + shadcn, **Next.js rewrites + server 외부 노출 차단**, **pytest/vitest 셋업 + MSW**, 루트 `pnpm test` 통합
- Push 2: 단일 관리자 인증 — Argon2 해시 검증, 세션 쿠키, rate limit, `/login` 페이지 (FSD: `pages/login` + `features/auth-login`), `middleware.ts` 가드, `cli hash` 헬퍼 — **각 단계 pytest/vitest 동봉**
- Push 3: 커스텀 로깅 인프라 (`JsonFormatter`, `DbLogHandler`, `LogBus`, `log_pruner`) + 로그 조회/SSE API + `/logs` 페이지 (FSD: `pages/logs` + `widgets/log-stream` + `features/log-filter`) — **테스트 동봉**
- Push 4: 자격증명/설정/알림 채널 CRUD + Orval 클라이언트 (`shared/api`) + UI 3개 페이지 (FSD: 각 `entities/*` + `features/*` + `pages/*`) + 채널 테스트 발송 (Discord/Slack/Telegram/ntfy) — **테스트 동봉**
- Push 5: 다중 계정 동시 폴링 워커 (supervisor + per-config task + per-credential semaphore) + 대시보드 + 성공/에러 시 다중 채널 발송 — **워커 통합 테스트 포함**

### v0.2
- `contextvars` 기반 자동 로그 컨텍스트 주입
- `QueueHandler` 기반 비동기 DB 로그 배치 flush
- `rate_limited` 5분 지속 시 알림 발송
- OCI 메타데이터 조회 헬퍼 UI
- ntfy 액션 버튼 (Click/Action 헤더)

### v0.3+
- 인스턴스 생성 후 cloud-init 주입
- 다중 사용자 (FastAPI-Users + NextAuth)
- Prometheus 메트릭

---

## 12. 결정 필요 (Open Questions)

| # | 질문 | 기본값 제안 |
|---|---|---|
| 1 | 서버/워커 분리 시점 | MVP 는 단일 프로세스 (FastAPI 내 task), 확장 시 분리 |
| 2 | Python 패키지 매니저 | `uv` (속도 + lockfile) |
| 3 | 인증 방식 | 단일 비밀번호 + 세션 쿠키 |
| 4 | Orval 생성 시점 | dev 수동 (`pnpm gen:api`), CI/Docker 빌드 시 자동 |
| 5 | UI 컴포넌트 라이브러리 | shadcn/ui (Tailwind 기반, 가벼움) |
| 6 | 데이터 페칭 캐싱 전략 | TanStack Query 기본 + 5초 refetchInterval (대시보드만) |
| 7 | 폴링 주기 글로벌 vs 설정별 | 설정별 `retry_interval_sec`, 전역 최소 200ms 가드 |
| 8 | 로깅 라이브러리 | 표준 `logging` 모듈 + 커스텀 핸들러 (structlog 불필요) |
| 9 | 로그 DB 쓰기 방식 | MVP: 동기 INSERT, v0.2: QueueHandler 비동기 배치 |
| 10 | 실시간 로그 전송 | SSE (`sse-starlette`) — WebSocket 보다 단순, 단방향이면 충분 |
| 11 | 로그 보존 | 7일 OR 10,000행 중 먼저 도달 (env 로 조정) |
| 12 | 다중 계정 동시성 모델 | per-config asyncio.Task + per-credential Semaphore (max=1), 글로벌 Semaphore (max=10) |
| 13 | 알림 채널 ↔ Config 관계 | many-to-many (`ConfigChannelLink` 테이블) |
| 14 | ntfy 인증 | Bearer 토큰 (옵션) — 채널 설정에 `token` 필드, 미설정 시 미인증 발송 |
| 15 | 비밀번호 저장 방식 | env 에 Argon2id 해시만 저장 (`APP_PASSWORD_HASH`), 평문 절대 저장 안 함 |
| 16 | 회원가입 / 비밀번호 재설정 UI | 없음 — env 재배포로 처리 (단일 사용자 운영 전제) |
| 17 | 웹 아키텍처 | FSD 6계층, `eslint-plugin-boundaries` 강제, slice 별 `index.ts` 공개 API |
| 18 | 서버 외부 노출 차단 | docker-compose `ports` 미선언 + `expose` 만, Next.js `rewrites()` 가 `/api/*` 프록시, CORS 는 보조 |
| 19 | 서버 테스트 스택 | pytest + pytest-asyncio + httpx ASGITransport + pytest-cov + polyfactory + pytest-httpx |
| 20 | 웹 테스트 스택 | vitest + @testing-library/react + @testing-library/user-event + MSW (`onUnhandledRequest: 'error'`) |
| 21 | 커버리지 목표 | 서버 70% / 웹 50% (services·workers 80%, features·entities 70%) |
| 22 | 테스트 의무 강제 시점 | task 분해 단계부터 `T1/T2` 서브태스크 자동 추가, task-executor 가 거부 |
| 23 | E2E 도구 | v0.2 이후 Playwright (MVP 에서는 단위/통합만) |
| 24 | OSS 라이선스 | 모두 허용 (GPL/AGPL 포함) — self-host, 재배포 없음 |
| 25 | 에이전트 팀 구조 | 도메인 분리: `push-lead` + `server-worker` + `web-worker` + `test-runner` |
| 26 | 에러 응답 표준 | `{ error: { code, message, details, request_id } }` 통일 |
| 27 | `request_id` 부여 | `RequestIdMiddleware` (ULID), 응답 헤더 `X-Request-Id` + 모든 로그 자동 포함 |

---

## 13. 성공 기준

- `docker compose up -d` 한 줄로 server + web 기동
- Next.js (`http://localhost:3000`) 에서 자격증명 + 설정 등록 가능
- FastAPI Swagger (`http://localhost:8000/docs`) 로 API 직접 호출 가능
- `pnpm gen:api` 로 Orval 클라이언트 재생성 → 웹 코드 타입 안전
- 워커가 OCI API 를 호출하고 시도 이력이 DB 에 누적
- **서로 다른 OCI 계정 2개 이상 + 각각 config 여러 개** 가 동시에 폴링되며, 동일 계정 내 호출은 직렬, 계정 간 호출은 병렬
- 가용성 확보 시 인스턴스 자동 생성 + **연결된 모든 알림 채널 (Discord/Slack/Telegram/ntfy)** 로 알림 도착
- ntfy 채널이 `https://ntfy.supabin.com/{topic}` 에 정상 발송됨 (Title/Priority/Tags 헤더 포함)
- 웹 `/logs` 페이지에서 워커/서버 로그를 실시간 + 과거 이력 모두 확인 가능 (레벨/logger/config 필터, 검색)
- 미인증 상태로 `/configs` 등 보호된 페이지 접근 시 자동으로 `/login` 으로 리다이렉트, 잘못된 비밀번호 5회 시 rate limit 적용
- 컨테이너 재시작 후에도 설정/이력/로그 보존
- **외부 차단 검증**: 호스트에서 `curl http://localhost:8000/healthz` 가 실패 (connection refused). 웹 통한 `curl http://localhost:3000/api/healthz` 만 성공
- **FSD 규칙 검증**: `pnpm lint` 가 레이어 위반 import (예: `entities` → `features`) 를 에러로 감지
- **테스트 검증**: `pnpm test` 한 줄로 서버 + 웹 전체 테스트 통과, 서버 커버리지 70%+ / 웹 50%+
