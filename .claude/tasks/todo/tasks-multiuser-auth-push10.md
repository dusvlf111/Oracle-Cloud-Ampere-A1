# Tasks: 다중 사용자 권한 분리 - Push 10

> PRD: `.claude/tasks/todo/prd-multiuser-auth.md` (§8 웹)
> Push 범위: 웹 — 회원가입/승인 대기 화면, 유저 관리 페이지 (admin), 사이드바 role 분기
> 선행 조건: **Push 9 완료** (register/users API + me 확장이 OpenAPI 에 있어야 Orval 생성 가능)
> 상태: 🔲 진행 중

---

### 관련 파일

- `apps/web/src/entities/user/` - 유저 엔티티 (status/role 배지)
- `apps/web/src/features/auth-register/` - 가입 신청 폼 + 승인 대기 안내
- `apps/web/src/features/auth-login/` - pending/disabled 403 에러 안내
- `apps/web/src/features/user-approve/` - 승인/거부/비활성 액션
- `apps/web/src/pages/users/`, `apps/web/app/(protected)/users/page.tsx` - 유저 관리
- `apps/web/src/widgets/sidebar/` - admin 전용 메뉴 분기
- `apps/web/tests/mocks/handlers.ts` - users/register 핸들러

---

### 에이전트 실행 전략 (push-lead)

전 작업 `web-worker` 담당. Push 9 머지 후 `node scripts/sync-api.mjs` 로 클라이언트 재생성이 첫 단계.

| 작업 | 의존성 |
|---|---|
| 10.1 | Push 9 (OpenAPI) |
| 10.2 ∥ 10.3 | 10.1 — slice 비중첩이라 병렬 가능 (단일 에이전트면 순차) |
| 10.4 | 10.1 (me 의 role) |

- 기존 auth-setup slice 는 register 로 흡수 — 최초 가입(=admin) 화면 문구 "관리자 계정 생성" 유지, 이후 가입은 "가입 신청" 문구
- 각 T2 커밋 직전 `test-runner` 검증, 10.4.T2 에서 lint(FSD)+커버리지 게이트
- 참조 스킬: `fsd-architecture`, `web-testing`

---

## 작업

- [ ] 10.0 웹 권한 분리 UI (Push 10)
    - [x] 10.1 클라이언트 재생성 + 유저 엔티티 — `node scripts/sync-api.mjs` (register/users/me 훅), `entities/user` (status: pending/active/disabled 배지, role 표시), me 확장(`{username, role, status}`) 반영 — 세션 컨텍스트에 role 노출
        - [x] 10.1.T1 vitest 테스트 작성 — 유저 status/role 배지 렌더, me 훅 role 파싱 (MSW)
        - [x] 10.1.T2 `pnpm --filter web vitest run src/entities/user` + tsc 실행 및 검증
    - [x] 10.2 가입 플로우 — `features/auth-register`: 최초 가입(needs_setup) 은 기존 "관리자 계정 생성" 동작 유지, 이후 가입은 "가입 신청" → 성공 시 "승인 대기 중입니다" 안내 화면 (세션 없음). `features/auth-login`: 403 `account_pending`("관리자 승인 대기 중") / `account_disabled`("비활성화된 계정") 에러 메시지 분기
        - [x] 10.2.T1 vitest 테스트 작성 — 가입 신청→대기 안내, 최초 가입→자동 로그인 리다이렉트 회귀, 로그인 403 두 코드별 메시지 (MSW)
        - [x] 10.2.T2 `pnpm --filter web vitest run src/features/auth-register src/features/auth-login src/pages/login` 실행 및 검증
    - [ ] 10.3 유저 관리 페이지 (admin) — `pages/users` + `features/user-approve`: 목록 테이블 (pending 상단 정렬 + 뱃지), 행별 승인/거부/비활성/활성 버튼 (거부는 확인 모달), 액션 후 캐시 무효화. 모바일 카드 전환 (기존 패턴)
        - [ ] 10.3.T1 vitest 테스트 작성 — 목록 렌더, 승인 클릭→PATCH 요청+목록 갱신, 거부 확인 모달, 비활성 (MSW)
        - [ ] 10.3.T2 `pnpm --filter web vitest run src/pages/users src/features/user-approve` 실행 및 검증
    - [ ] 10.4 사이드바 role 분기 + 라우트 — admin 에게만 "유저 관리" 메뉴 노출 (me.role 기반), user 가 `/users` 직접 접근 시 서버 403/404 → 안내 화면, `app/(protected)/users/page.tsx` 라우트
        - [ ] 10.4.T1 vitest 테스트 작성 — admin/user 별 사이드바 메뉴 분기, 비 admin 접근 안내
        - [ ] 10.4.T2 `pnpm --filter web test` 전체 + `pnpm --filter web lint` (FSD) + 커버리지 50%+ 게이트 실행 및 검증
