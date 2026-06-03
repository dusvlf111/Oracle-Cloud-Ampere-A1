# 결과보고서: tasks-prd-push5

> 완료일: 2026-06-03
> 브랜치: `push5-web-ui` (HEAD: `push4-domain-api` 에서 분기)
> 범위: 웹 관리 UI — Orval 타입 클라이언트(`shared/api`), 자격증명/설정/알림 채널 3개 페이지(FSD: entities + features + pages), 채널 테스트 발송 UI

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 5.1 Orval 클라이언트 셋업 + httpClient mutator + MSW 베이스 | web | ✅ | `b515819` |
| 5.2 엔티티 3종 (credential/config/channel) | web | ✅ | `840a497` |
| 5.3 자격증명 페이지 (verify/생성 폼/삭제) | web | ✅ | `12f0f72` |
| 5.4 알림 채널 페이지 (동적 CRUD 폼 + 테스트 발송) | web | ✅ | `116c263` |
| 5.5 인스턴스 설정 페이지 (생성 폼 + optimistic 토글) | web | ✅ | `f5756e9` |

전 작업 단일 에이전트로 순차 직접 구현 (5.1→5.2→5.3→5.4→5.5). 5.3~5.5 는 FSD slice 가 완전히 분리되어 병렬 구현 가능한 구조이나, Task 도구 미사용 환경에 따라 순차 처리.

## 변경 파일

### 5.1 — Orval / 공용 인프라
- `apps/web/src/shared/http/client.ts` — `httpClient` Orval mutator 추가 (apiFetch 재사용, 멀티파트/쿼리/에러봉투 처리), `apiFetch` 가 raw body(FormData) 패스스루 지원
- `apps/web/src/shared/http/index.ts` — `httpClient`/`HttpClientConfig` export
- `apps/web/orval.config.ts` — 로컬 파일/URL 양쪽 input 문서화
- `apps/web/tests/mocks/handlers.ts` — credentials/configs/channels/attempts 베이스 핸들러
- `apps/web/tests/api-client.test.tsx` — 생성 훅 smoke + 에러봉투 + multipart 검증 (5.1.T1)
- `.gitignore` — `apps/server/openapi.json` 추출 산출물 ignore (생성물 `src/shared/api/` 는 기존 ignore)
- `apps/web/tests/next-rewrites.test.ts` — 기존 파일의 tsc strict-null 오류 1줄 보정(`rules![0]`)

### 5.2 — entities (각 slice `{ui, model, api, index.ts}`)
- `apps/web/src/entities/credential/` — `CredentialCard`(마스킹 식별자 + passphrase 배지)
- `apps/web/src/entities/config/` — `ConfigRow`(enabled 배지 + 스펙 요약 + 채널 수)
- `apps/web/src/entities/channel/` — `ChannelCard`(타입 아이콘 + 마스킹 config 표시)
- 각 slice `api/index.ts` 는 Orval 생성 훅을 도메인 별칭으로 재노출

### 5.3 — 자격증명
- `apps/web/src/features/credential-verify/` — `CredentialVerifyButton`({ok,error} 콜백), `CredentialCreateForm`(multipart 파일 업로드, rhf+zod), schema
- `apps/web/src/pages/credentials/ui/CredentialsPage.tsx` — 목록 + 생성 + verify 결과 + 삭제 확인 다이얼로그
- `apps/web/app/(protected)/credentials/page.tsx` — 라우트 진입점

### 5.4 — 알림 채널
- `apps/web/src/features/channel-test/` — `ChannelCreateForm`(zod discriminated union 동적 필드), `ChannelTestButton`(ok/error 표시), `model/schema.ts`, `model/transform.ts`(ntfy tags 콤마 분리)
- `apps/web/src/pages/channels/ui/ChannelsPage.tsx` — 목록 + 생성 + 테스트 발송 + 삭제 확인
- `apps/web/app/(protected)/channels/page.tsx` — 라우트 진입점

### 5.5 — 인스턴스 설정
- `apps/web/src/features/config-create/` — `ConfigCreateForm`(전체 폼 + credential 선택 + channel_ids 멀티 선택), schema
- `apps/web/src/features/config-toggle/` — `useToggleConfig`(optimistic update + 롤백 + 캐시 무효화), `ConfigToggle`
- `apps/web/src/pages/configs/ui/ConfigsPage.tsx` — 목록 + 생성 + 토글 + 삭제 확인
- `apps/web/app/(protected)/configs/page.tsx` — 라우트 진입점
- `apps/web/vitest.config.ts` — 커버리지 include/exclude(생성물/배럴/테스트 제외)
- `apps/web/package.json`, `pnpm-lock.yaml` — `@vitest/coverage-v8` 추가
- `README.md` — OSS Dependencies 갱신

## 테스트 결과

- **vitest: 70 passed (24 test files)** — Push 4 기준 38개 → +32개
- 커버리지(`@vitest/coverage-v8`, src 대상, 생성물/배럴 제외):
  - Statements 90.19% / Branches 79.25% / Functions 84.21% / Lines 90.19%
  - 게이트(웹 50%+, features/entities 70%+) 충족 — entities/features 페이지 UI 모두 90% 내외
- `pnpm --filter web tsc --noEmit`: ✅ 0 errors
- `pnpm --filter web lint` (eslint-plugin-boundaries FSD): ✅ 위반 없음

## Orval 흐름 검증

- OpenAPI 추출: `cd apps/server && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi()))" > openapi.json` (서버 미기동, exit 0, 25.5KB)
- `OPENAPI_URL=../server/openapi.json pnpm gen:api` → `src/shared/api/` 7개 태그(auth/credentials/configs/channels/attempts/logs/meta) + 스키마 생성 성공
- 생성물은 gitignore, 설정/스크립트(`orval.config.ts`, `gen:api`)만 커밋

## 새로 만든 스킬

- 없음 (기존 `fsd-architecture`, `web-testing`, `oss-selection` 패턴 재사용)

## OSS 도입

- `@vitest/coverage-v8@2.1.9` — vitest.config 가 이미 `provider: "v8"` 로 설정되어 있었으나 패키지 미설치 상태. 커버리지 게이트 검증을 위해 추가. vitest 와 동일 메이저(2.1.x) 고정, MIT 라이선스. README OSS 표 반영.

## 이슈 및 해결

1. **Orval mutator 시그니처 불일치** — 기존 `apiFetch(path, {json})` 와 Orval 이 요구하는 axios-like config(`{url, method, params, data, headers, signal}`) 가 달라 gen:api 실패. `httpClient` 어댑터를 추가해 해결. Orval 이 emit 하는 server-absolute 경로(`/api/...`)가 `apiFetch` 의 `/api` 베이스와 중복되는 문제는 prefix strip 으로 처리.
2. **multipart Content-Type 깨짐** — Orval 이 `Content-Type: multipart/form-data`(boundary 없음) 를 강제. `httpClient` 에서 FormData 본문일 때 해당 헤더를 제거해 브라우저가 boundary 를 채우도록 수정.
3. **MSW `request.formData()` jsdom 행(hang)** — multipart 본문을 MSW 핸들러에서 `formData()`/본문 파싱 시 jsdom+undici 조합으로 타임아웃. 테스트는 `content-type` 헤더(multipart + boundary)와 응답 처리로 검증하도록 변경.
4. **config-create `max_attempts` 빈 입력 검증 실패** — `z.coerce.number()` 가 빈 문자열을 0 으로 변환해 `min(1)` 위반. `z.preprocess` 로 빈 입력→undefined 처리.
5. **테스트 tsc strict-null 좁힘** — 콜백 내 변수 할당이 외부에서 `never`/`null` 로 좁혀지는 문제를 holder 객체 패턴으로 회피.

## 미완료 항목

- 없음. 5.0 전체(5.1~5.5 및 모든 T1/T2) 완료.

## 비고

- `git push` 미수행 (지시 준수). 브랜치 `push5-web-ui` 에 5개 커밋.
- 워킹트리의 `tasks-prd-push6.md` 수정분은 stash/커밋하지 않고 그대로 유지.
- 각 하위 작업 완료 시 + Push 완료 시 ntfy 알림 발송.
