# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 2

> PRD: `.claude/tasks/prd.md` (§7.7 인증, §8 표준 에러 응답, §11 MVP Push 2)
> Push 범위: 단일 관리자 인증 — 표준 에러 응답(AppError + RequestIdMiddleware), Argon2 해시 검증, 세션 쿠키, slowapi rate limit + IP 차단, `cli hash` 헬퍼, `/login` 페이지 (FSD: `pages/login` + `features/auth-login`), `middleware.ts` 가드
> 상태: 🔲 진행 중

---

### 관련 파일

- `apps/server/src/app/api/deps.py` - `AppError`, `require_login`, rate limit
- `apps/server/src/app/main.py` - 미들웨어/예외 핸들러 등록
- `apps/server/src/app/services/auth.py` - argon2 해싱/검증, 세션
- `apps/server/src/app/cli.py` - `python -m app.cli hash <password>` (typer)
- `apps/server/src/app/api/auth.py` - login/logout/me 라우터
- `apps/server/tests/api/test_auth.py` - 인증 API 테스트
- `apps/web/src/shared/http/` - fetch 인스턴스 (Orval mutator 겸용, `credentials: 'include'`)
- `apps/web/src/features/auth-login/` - 로그인 폼 (react-hook-form + zod)
- `apps/web/src/pages/login/` - 로그인 페이지 조합
- `apps/web/app/login/page.tsx`, `apps/web/app/middleware.ts` - 라우트 + 가드

---

### 에이전트 실행 전략 (push-lead)

| 작업 | 담당 | 의존성 |
|---|---|---|
| 2.1 → 2.3 → 2.4 | `server-worker` | — (2.3 은 2.1 에러 표준 + 2.2 auth 서비스 필요) |
| 2.2 | `server-worker` | — (2.1 과 독립, 같은 워커 내 선행 처리 가능) |
| 2.5 → 2.6 | `web-worker` | — (MSW 모킹 기반이라 서버 완성 불필요, API 계약은 PRD §8 고정) |

```
[server-worker] 2.1 ──┬→ 2.3 → 2.4
                2.2 ──┘
[web-worker]    2.5 → 2.6          (server 체인과 병렬)
```

- **병렬**: server 체인(2.1~2.4) ∥ web 체인(2.5~2.6) — 웹은 MSW 핸들러로 PRD §8 계약 기준 개발
- 각 T2 는 커밋 직전 `test-runner` 검증, Push 완료 시 통합 게이트 (Orval 미도입 단계 — `shared/http` 수동 타입)
- 참조 스킬: `fastapi-patterns`, `python-testing` / `fsd-architecture`, `web-testing`

---

## 작업

- [ ] 2.0 단일 관리자 인증 (Push 2)
    - [x] 2.1 표준 에러 응답 인프라 — `AppError(code, status_code, message, details)` + 전역 exception handler (`{error: {code, message, details, request_id}}`), `RequestIdMiddleware` (ULID 부여 → `request.state` + `X-Request-Id` 헤더), `validation_error`/`internal_error` 핸들러 (PRD §8)
        - [x] 2.1.T1 pytest 테스트 작성 — `tests/api/test_errors.py` (AppError → JSON 스키마 검증, 422 변환, X-Request-Id 헤더 존재/로그 포함)
        - [x] 2.1.T2 `pytest -q tests/api/test_errors.py` 실행 및 검증
    - [x] 2.2 auth 서비스 + CLI 헬퍼 — `services/auth.py` (argon2-cffi 해시 검증, env `APP_USERNAME`/`APP_PASSWORD_HASH` 비교), `cli.py` (typer: `hash <password>` → Argon2id 해시 출력)
        - [x] 2.2.T1 pytest 테스트 작성 — `tests/unit/services/test_auth.py` (해시 생성→검증 라운드트립, 불일치 거부), CLI 출력 형식 (`$argon2id$` prefix)
        - [x] 2.2.T2 `pytest -q tests/unit/services/test_auth.py` 실행 및 검증
    - [x] 2.3 세션 + 인증 API — `SessionMiddleware` (itsdangerous, HTTP-only, SameSite=Lax, prod Secure), `api/auth.py` (`POST /api/auth/login`, `POST /api/auth/logout` 204, `GET /api/auth/me`), `deps.py` `require_login` (미인증 401 `unauthorized`), `/healthz`·`/api/auth/login` 만 공개
        - [x] 2.3.T1 pytest 테스트 작성 — `tests/api/test_auth.py` (정상 로그인→Set-Cookie→me 200, 잘못된 비밀번호 401, 로그아웃 후 me 401, 보호 엔드포인트 미인증 401), conftest 에 `authed_client` fixture 추가
        - [x] 2.3.T2 `pytest -q tests/api/test_auth.py` 실행 및 검증
    - [x] 2.4 무차별 대입 방어 — slowapi (IP 당 5회/분 → 429 `rate_limited` + `retry_after_sec`), 연속 실패 10회 → 5분 IP 차단 (in-memory), 로그인 시도(성공/실패) WARNING 로그
        - [x] 2.4.T1 pytest 테스트 작성 — `tests/api/test_auth_ratelimit.py` (6회째 429, 10회 실패 후 차단, 차단 해제 시간 mock)
        - [x] 2.4.T2 `pytest -q tests/api/test_auth_ratelimit.py` 실행 및 검증
    - [ ] 2.5 web: 로그인 기능 — `shared/http` (fetch 래퍼, `credentials: 'include'`, 표준 에러 파싱), `features/auth-login` (react-hook-form + zod 폼, 401/429 에러 표시), `pages/login` + `app/login/page.tsx` 진입점
        - [ ] 2.5.T1 vitest 테스트 작성 — `features/auth-login/ui/LoginForm.test.tsx` (MSW: 성공 시 리다이렉트 콜백, 401 에러 메시지, 429 rate limit 메시지, zod 검증)
        - [ ] 2.5.T2 `pnpm --filter web vitest run src/features/auth-login` 실행 및 검증
    - [ ] 2.6 web: 인증 가드 + 로그아웃 — `app/middleware.ts` (session 쿠키 부재 시 `/login` 리다이렉트, `/login` 제외), `features/auth-logout` (로그아웃 버튼 + me 캐시 무효화), `(protected)/layout.tsx`
        - [ ] 2.6.T1 vitest 테스트 작성 — middleware 단위 테스트 (쿠키 유/무 분기), `features/auth-logout` 테스트 (MSW: 로그아웃 호출 → 리다이렉트)
        - [ ] 2.6.T2 `pnpm --filter web test` 실행 및 검증 (lint 포함 FSD 위반 없음 확인)
