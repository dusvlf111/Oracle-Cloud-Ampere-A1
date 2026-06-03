# 결과보고서: tasks-prd-push2

> 완료일: 2026-06-03
> 브랜치: `push2-auth` (HEAD: `push1-monorepo-infra` 에서 분기)
> 범위: 단일 관리자 인증 — 표준 에러 응답(AppError + RequestIdMiddleware), Argon2 해시 검증, 세션 쿠키, slowapi rate limit + IP 차단, `cli hash` 헬퍼, `/login` 페이지(FSD), `middleware.ts` 가드

## 실행 메모

- push-lead 전략상 server 체인(2.1~2.4) ∥ web 체인(2.5~2.6) 병렬이나, 본 실행은 서브에이전트 위임 도구(Task)를 사용할 수 없는 환경이라 단일 에이전트가 두 체인을 순차 구현(server → web). 도메인 분리/커밋 단위/테스트 동봉 규칙은 모두 준수.
- 모든 Python 작업은 `uv run`, 웹은 `pnpm exec`. git push 미수행.

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 2.1 표준 에러 응답 인프라 (AppError + RequestIdMiddleware + 핸들러) | server | ✅ | `47f7d0e` |
| 2.2 argon2 auth 서비스 + `cli hash` 헬퍼 | server | ✅ | `6b8d8cf` |
| 2.3 세션 미들웨어 + login/logout/me API + require_login | server | ✅ | `66aa6d0` |
| 2.4 slowapi rate limit + 연속실패 IP 차단 + WARNING 로그 | server | ✅ | `18c45aa` |
| 2.5 web 로그인 기능 (shared/http + features/auth-login + pages/login) | web | ✅ | `c416d02` |
| 2.6 web 인증 가드 + 로그아웃 (middleware + auth-logout + protected) | web | ✅ | `d4eba9e` |

(README OSS Dependencies 갱신은 최종 정리 커밋에 포함 — 아래 참조)

## 변경 파일

### Server (`apps/server/`)
- `src/app/api/__init__.py` (신규)
- `src/app/api/deps.py` — `AppError`, `RequestIdMiddleware`(ULID), `require_login`
- `src/app/api/errors.py` — 전역 핸들러(AppError/validation_error/internal_error/rate_limited)
- `src/app/api/auth.py` — `/api/auth/login|logout|me`
- `src/app/api/ratelimit.py` — slowapi Limiter + in-memory `FailureTracker`(mockable `_now`)
- `src/app/services/__init__.py`, `src/app/services/auth.py` — argon2 해시/검증/authenticate
- `src/app/cli.py` — typer `hash <password>`
- `src/app/main.py` — SessionMiddleware + RequestIdMiddleware + 핸들러/limiter/라우터 등록
- `src/app/config.py` — `session_secure` 추가
- `tests/conftest.py` — `admin_settings`, `authed_client`, rate-limit reset autouse fixture
- `tests/api/test_errors.py`, `tests/api/test_auth.py`, `tests/api/test_auth_ratelimit.py`
- `tests/unit/services/__init__.py`, `tests/unit/services/test_auth.py`
- `pyproject.toml` / `uv.lock` — argon2-cffi, typer, itsdangerous, slowapi, python-ulid

### Web (`apps/web/`)
- `src/shared/http/{client.ts,errors.ts,index.ts}` — `apiFetch`(credentials:'include') + `ApiError` 엔벨로프 파싱
- `src/shared/ui/{input.tsx,label.tsx,index.ts}`, `src/shared/index.ts` — UI 프리미티브 + 배럴
- `src/features/auth-login/{model/{schema,login}.ts, ui/LoginForm.tsx, index.ts}` + `ui/LoginForm.test.tsx`
- `src/features/auth-logout/{model/logout.ts, ui/LogoutButton.tsx, index.ts}` + `ui/LogoutButton.test.tsx`
- `src/pages/login/{ui/LoginPage.tsx,index.ts}`
- `app/layout.tsx`(루트 레이아웃 이전), `app/login/page.tsx`, `app/(protected)/{layout.tsx,page.tsx}`
- `middleware.ts` + `middleware.test.ts` — 세션 쿠키 가드
- `tests/mocks/handlers.ts` — `errorEnvelope` 헬퍼
- `vitest.config.ts` — `middleware.test.ts` include 추가
- `package.json` / `pnpm-lock.yaml` — react-hook-form, zod, @hookform/resolvers
- 삭제: `src/app/layout.tsx`(→ `app/layout.tsx`), `src/app/page.tsx`(→ `app/(protected)/page.tsx`)

## 테스트 결과

- pytest: **27 passed**, coverage **95%** (`uv run pytest -q --cov=app`)
- vitest: **15 passed** (6 files), `pnpm exec vitest run`
- eslint(FSD boundaries 포함): **통과 (0 위반)**
- tsc: 신규 코드 클린. `tests/next-rewrites.test.ts` 의 TS18048 2건은 **Push 1 부터 존재하던 선행 이슈**로 본 Push 범위 밖.

## 이슈 및 해결 (T3)

1. **`python -m app.cli hash` 가 `hash` 를 PASSWORD 인자로 오인 (exit 2)** — Typer 단일 명령 앱이 서브커맨드를 접지(collapse). `@cli.callback()` 추가 + `@cli.command(name="hash")` 로 명시하여 `hash` 를 정식 서브커맨드로 유지. (커밋 2.2)
2. **slowapi `enabled` 비활성화 실패** — 테스트에서 `limiter._enabled` 로 끄려 했으나 실제 속성은 `enabled`. 수정 후 10회 연속실패 차단 테스트 통과. (커밋 2.4)
3. **Next App Router 루트 충돌** — `src/app`(FSD 레이어)와 루트 `app/` 양쪽에 router 파일이 있으면 Next 가 충돌. router 를 루트 `app/` 으로 일원화하고 `src/app` 은 providers/styles 만 남기는 FSD app 레이어로 정리. 기존 홈 페이지는 `app/(protected)/page.tsx` 로 이전(유실 없음).
4. **middleware 위치** — 태스크 문구는 `app/middleware.ts` 이나 Next 15 런타임은 루트 `app/` 사용 시 `middleware.ts` 를 프로젝트 루트(`apps/web/middleware.ts`)에서 인식. 런타임 정확성 우선하여 `apps/web/middleware.ts` 에 배치(로직/테스트는 동일).

## 새로 만든 스킬

- 없음 (반복 패턴 미발생 — 인증 1회성 인프라).

## 미완료 항목

- 없음. 2.1~2.6 및 상위 2.0 모두 `[x]`.

## 후속 권고 (범위 밖)

- `apps/web/tests/next-rewrites.test.ts` 의 TS18048 2건 정리(별도 푸시).
- 세션 쿠키 secret: 운영 배포 시 `APP_SECRET` 필수 주입(현재 미설정 시 dev fallback). `SESSION_SECURE=true` 프로덕션 활성화.
