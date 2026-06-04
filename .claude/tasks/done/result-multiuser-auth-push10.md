# 결과보고서: tasks-multiuser-auth-push10

> 완료일: 2026-06-04
> 범위: 웹 (Next.js/FSD) — 회원가입/승인 대기 화면, 유저 관리 페이지(admin), 사이드바 role 분기
> 브랜치: `push10-multiuser-web` (base: origin/main 14bdae9 — Push 9 머지됨)
> 단일 에이전트 순차 실행 (Task 서브에이전트 도구 미지원 환경 → 10.1→10.4 직접 구현)

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 10.1 클라이언트 재생성 + 유저 엔티티 | web | ✅ | 42987cd, 2f924c7 |
| 10.2 가입 플로우 + 로그인 403 분기 | web | ✅ | 6b9e613 |
| 10.3 유저 관리 페이지 + 승인/거부 액션 | web | ✅ | 2ce703f |
| 10.4 사이드바 role 분기 + /users 라우트 | web | ✅ | (이 커밋) |

- 42987cd `chore(web): sync OpenAPI client — register/users/me 훅 생성`
  (Push 9 OpenAPI 반영해 openapi.json 스냅샷 갱신 → Orval 재생성)

## 주요 결정

- **auth-setup slice 흡수**: 계획대로 `features/auth-setup` 을 신규 `features/auth-register`
  로 통합하고 제거. 최초 가입(needs_setup)은 "관리자 계정 생성" 문구 + 자동 로그인 유지,
  이후 가입은 "가입 신청" → "승인 대기 중입니다" 안내. 분기는 서버가 돌려주는
  `RegisterResponse.status`(active=자동로그인 / pending=대기) 기준.
- **세션 role 노출**: `entities/user/model/session.ts` 의 `useSession()` 이
  `GET /api/auth/me`({username, role, status}) 를 래핑하고 `isAdmin` 플래그 제공.
  사이드바/유저관리 라우트가 공통 소비 (FSD: widgets·pages → entities 허용).
- **반응형**: 기존 패턴(`hidden md:table` / `md:hidden`, `min-h-11`, `text-base`,
  카드 전환) 재사용. UsersPage 데스크톱 테이블 + 모바일 카드 동시 렌더.
- **거부 확인 모달**: 파괴적 액션(reject)만 확인 다이얼로그. 승인/비활성/활성은 즉시.
- **last_admin 가드**: 비활성 시 409 `last_admin` → "마지막 관리자는 비활성화할 수 없습니다" 안내.
- **`/users` 비-admin 접근**: `UsersRoute` 가 세션 role 로 클라이언트 게이트 + 안내 화면
  (서버는 여전히 source of truth로 403/404 반환).

## 변경 파일

### 신규 — entities/user
- `src/entities/user/index.ts`
- `src/entities/user/model/types.ts` (User/Me/UserStatus/UserRole, isAdmin)
- `src/entities/user/model/session.ts` (useSession)
- `src/entities/user/api/index.ts` (useMe/useUsers/approve·reject·disable·enableUser 재export)
- `src/entities/user/ui/StatusBadge.tsx` (pending/active/disabled)
- `src/entities/user/ui/RoleBadge.tsx` (admin/user)

### 신규 — features/auth-register
- `src/features/auth-register/index.ts`
- `src/features/auth-register/model/register.ts`, `model/schema.ts`
- `src/features/auth-register/ui/RegisterForm.tsx`, `ui/PendingNotice.tsx`

### 신규 — features/user-approve
- `src/features/user-approve/index.ts`
- `src/features/user-approve/model/actions.ts` (useUserActions)
- `src/features/user-approve/ui/UserActions.tsx`

### 신규 — pages/users + route
- `src/pages/users/index.ts`
- `src/pages/users/ui/UsersPage.tsx`, `ui/UsersRoute.tsx`
- `app/(protected)/users/page.tsx`

### 수정
- `src/features/auth-login/ui/LoginForm.tsx` (403 account_pending/disabled 메시지)
- `src/pages/login/ui/LoginPage.tsx` (setup/login/signup/pending 모드)
- `src/widgets/sidebar/ui/Sidebar.tsx` (admin 전용 "유저 관리" 메뉴 + useSession)
- `apps/server/openapi.json` (Push 9 스냅샷 갱신)
- `tests/mocks/handlers.ts` (auth/me + users 기본 핸들러)

### 제거
- `src/features/auth-setup/**` (auth-register 로 흡수)

### 테스트 (신규/수정)
- `entities/user/ui/StatusBadge.test.tsx`, `entities/user/model/session.test.tsx`
- `features/auth-register/ui/RegisterForm.test.tsx`
- `features/auth-login/ui/LoginForm.test.tsx` (403 케이스 추가)
- `features/user-approve/model/actions.test.tsx`
- `pages/login/ui/LoginPage.test.tsx` (신규 모드/회귀)
- `pages/users/ui/UsersPage.test.tsx`, `pages/users/ui/UsersRoute.test.tsx`
- `widgets/sidebar/ui/Sidebar.test.tsx` (role 분기 + QueryClient 래퍼)

## 테스트 결과 (10.4.T2 게이트)

- vitest: **45 files / 198 tests passed** (Push 9 이전 175+ → 198 로 증가)
- tsc `--noEmit`: 통과
- eslint (FSD boundaries): 통과 (0 위반)
- 커버리지: Statements **93.63%**, Branches 83.49%, Functions 85.5% — 50% 게이트 통과
  - 신규 슬라이스: entities/user UI 100%, UsersRoute 100%, UsersPage 96.4%

## UI 동작 요약

- **로그인 화면(`/login`)**
  - `needs_setup=true`: "관리자 계정 생성" 폼 → 제출 시 active 자동로그인 → `/` 리다이렉트
  - `needs_setup=false`: "Sign in" 폼 + "가입 신청" 토글 링크
  - 가입 신청(이후 사용자): pending 응답 → "승인 대기 중입니다" 카드(세션 없음)
  - 로그인 403: `account_pending`="관리자 승인 대기 중입니다", `account_disabled`="비활성화된 계정입니다"
- **사이드바**: admin 세션에만 "유저 관리"(Users 아이콘) 메뉴 노출, user 는 숨김
- **유저 관리(`/users`, admin)**: pending 상단 정렬 테이블(데스크톱)/카드(모바일),
  status·role 배지, 행별 승인/거부(확인 모달)/비활성/활성 → 액션 후 목록 캐시 무효화 재조회
  - 마지막 admin 비활성 시도 → 안내 메시지
- **`/users` 비-admin 직접 접근**: "접근 권한이 없습니다" 안내 화면

## 새로 만든 스킬

- 없음 (기존 `fsd-architecture`, `web-testing` 패턴 재사용)

## 이슈 및 특이사항

- origin/main(14bdae9)에 커밋된 `apps/server/openapi.json` 스냅샷이 Push 9
  엔드포인트(register/users)를 누락한 상태였음. `uv` 가용 환경이라
  `scripts/sync-api.mjs` 가 FastAPI 앱에서 스키마를 재추출해 갱신 → Orval 재생성으로 해결.
- 생성물(`src/shared/api/**`)은 .gitignore 대상(prebuild 훅 재생성)이라 커밋 제외,
  `openapi.json` 스냅샷만 커밋.
- 데스크톱 테이블 + 모바일 카드가 jsdom 에서 동시 렌더되므로 테스트는
  `within(getByTestId("users-table"))` 로 스코프해 중복 매치 회피.
- **git push 미수행** (지시사항 준수). 브랜치 `push10-multiuser-web` 에 로컬 커밋만 존재.
