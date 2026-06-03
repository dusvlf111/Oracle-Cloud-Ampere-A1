# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 5

> PRD: `.claude/tasks/prd.md` (§5 FSD, §7.1/7.2/7.5.2 UI, §8 Orval 흐름, §11 MVP Push 4 웹 파트)
> Push 범위: 웹 관리 UI — Orval 타입 클라이언트 (`shared/api`), 자격증명/설정/알림 채널 3개 페이지 (FSD: `entities/*` + `features/*` + `pages/*`), 채널 테스트 발송 UI
> 상태: 🔲 진행 중

---

### 관련 파일

- `apps/web/orval.config.ts` - OpenAPI → React Query 훅 (tags-split, mutator: `shared/http`)
- `apps/web/src/shared/api/` - Orval 자동 생성 (gitignored)
- `apps/web/tests/mocks/handlers.ts` - 도메인 MSW 핸들러
- `apps/web/src/entities/{credential,config,channel}/` - 엔티티 ui/model/api
- `apps/web/src/features/credential-verify/` - 자격증명 검증 버튼
- `apps/web/src/features/{config-create,config-toggle}/` - 설정 생성 폼/토글
- `apps/web/src/features/channel-test/` - 채널 테스트 발송
- `apps/web/src/pages/{credentials,configs,channels}/` - 페이지 조합
- `apps/web/app/(protected)/{credentials,configs,channels}/page.tsx` - 라우트 진입점

---

### 에이전트 실행 전략 (push-lead)

전 작업 `web-worker` 담당. **선행 조건: Push 4 완료** (Orval 이 서버 `/openapi.json` 필요).

| 작업 | 담당 | 의존성 |
|---|---|---|
| 5.1 | `web-worker` | Push 4 (서버 OpenAPI) |
| 5.2 | `web-worker` | 5.1 (생성된 `shared/api` 타입) |
| 5.3 ∥ 5.4 ∥ 5.5 | `web-worker` 최대 3개 병렬 spawn | 5.2 (slice 영역 비중첩: credentials / channels / configs) |

```
5.1 → 5.2 ──┬── [web-worker A] 5.3 (credentials)
            ├── [web-worker B] 5.4 (channels)
            └── [web-worker C] 5.5 (configs)
```

- **병렬 조건**: 5.3~5.5 는 FSD slice 가 완전 분리 — 공용 파일(`tests/mocks/handlers.ts`) 추가는 5.1 에서 선반영, 병렬 워커는 자기 도메인 핸들러만 수정
- 각 T2 커밋 직전 `test-runner` 검증, 5.5.T2 에서 lint(FSD)+커버리지 50%+ 게이트
- 참조 스킬: `fsd-architecture`, `web-testing`, `oss-selection`

---

## 작업

- [ ] 5.0 웹 관리 UI (Push 5)
    - [x] 5.1 Orval 클라이언트 셋업 — `orval.config.ts` (tags-split, react-query client, `shared/http` mutator), `pnpm gen:api` 스크립트, 생성물 `shared/api/` gitignore, 도메인 MSW 핸들러 베이스 (`tests/mocks/handlers.ts`: credentials/configs/channels/attempts)
        - [x] 5.1.T1 vitest 테스트 작성 — 생성된 훅 smoke 테스트 (`useGetCredentials` 가 MSW 응답을 반환, 표준 에러 응답 파싱)
        - [x] 5.1.T2 서버 기동 후 `pnpm gen:api` 성공 + `pnpm --filter web tsc --noEmit` + `pnpm --filter web test` 실행 및 검증
    - [ ] 5.2 엔티티 3종 — `entities/credential` (목록 카드, 마스킹 표시), `entities/config` (목록 행, enabled 배지), `entities/channel` (타입 아이콘, 마스킹 config 표시) — 각 slice `{ui,model,api,index.ts}`
        - [ ] 5.2.T1 vitest 테스트 작성 — 엔티티별 렌더 테스트 (마스킹 값 표시, enabled/disabled 상태, 타입별 아이콘)
        - [ ] 5.2.T2 `pnpm --filter web vitest run src/entities` 실행 및 검증
    - [ ] 5.3 자격증명 페이지 — `features/credential-verify` (검증 버튼 → `{ok,error}` 토스트), 자격증명 생성 폼 (multipart: private key 파일 업로드, react-hook-form + zod), 삭제 확인, `pages/credentials` 조합 + 라우트
        - [ ] 5.3.T1 vitest 테스트 작성 — 생성 폼 제출 (파일 포함 FormData, MSW 검증), verify 성공/실패 토스트, 삭제 흐름 (user-event 시나리오)
        - [ ] 5.3.T2 `pnpm --filter web vitest run src/features/credential-verify src/pages/credentials` 실행 및 검증
    - [ ] 5.4 알림 채널 페이지 — 채널 CRUD 폼 (타입 선택 시 동적 필드: discord/slack webhook, telegram bot_token/chat_id, ntfy server_url/topic/token/priority/tags — zod discriminated union), `features/channel-test` (테스트 발송 버튼 → ok/error 결과 표시), `pages/channels` 조합 + 라우트
        - [ ] 5.4.T1 vitest 테스트 작성 — 타입 전환 시 폼 필드 변경, ntfy 채널 생성 제출 페이로드 검증, 테스트 발송 성공/실패 표시 (MSW)
        - [ ] 5.4.T2 `pnpm --filter web vitest run src/features/channel-test src/pages/channels` 실행 및 검증
    - [ ] 5.5 인스턴스 설정 페이지 — `features/config-create` (전체 폼 필드 + `channel_ids` 멀티 선택, zod 검증), `features/config-toggle` (토글 → optimistic update + 캐시 무효화), `pages/configs` 조합 + 라우트
        - [ ] 5.5.T1 vitest 테스트 작성 — 설정 생성 폼 (필수 필드 검증, channel_ids 선택 포함 제출), 토글 동작 (MSW: enabled 반전 응답), 페이지 통합 시나리오
        - [ ] 5.5.T2 `pnpm --filter web test` + `pnpm --filter web lint` (FSD 위반 없음) 실행 및 검증 — 웹 커버리지 50%+ (features/entities 70%+) 확인
