# 결과보고서: tasks-prd-push7

> 완료일: 2026-06-03
> 범위: 웹 모바일 대응 (반응형 + 모바일 전용 컴포넌트 분리) + PWA 설치 지원
> 브랜치: `push7-mobile-pwa` (push6-worker-dashboard HEAD 0cf9534 에서 분기)

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 7.1 반응형 기반 인프라 (useMediaQuery + 드로어/햄버거) | web | ✅ | 48df9e6 |
| 7.2 대시보드 + 시도 이력 모바일 (AttemptCardList) | web | ✅ | 111100d |
| 7.3 관리 페이지 3종 모바일 (카드/풀스크린 다이얼로그/터치 타깃) | web | ✅ | 1b25107 |
| 7.4 로그 페이지 모바일 (접이식 필터 + 모바일 로그 행) | web | ✅ | e03dede |
| 7.5 PWA (@serwist/next + manifest + 아이콘) | web | ✅ | 9806679 |

전 작업 단일 에이전트 순차 직접 구현 (서브에이전트 Task 도구 미가용). 각 하위 작업마다 T1(테스트 작성)+T2(검증) 후 커밋.

## 테스트 결과

- vitest: **113 passed** (33 파일) — 기존 84 → +29 신규, 회귀 0
  - 신규: useMediaQuery(4), Sidebar 드로어(+4), Header 햄버거(+1), AttemptCardList(4), AttemptsTable 뷰 패리티(+1), Dashboard 복사(+1), 페이지 모바일 다이얼로그/스택(+4), LogFilterBar 토글(+1), LogRow 모바일(+2), format.test(3), pwa.test(4)
- lint (eslint + boundaries): clean
- tsc --noEmit: clean
- `pnpm build`: 성공 — App Router 6개 라우트 prerender, `public/sw.js` (43KB) serwist 번들 생성 확인

## 분리한 모바일 컴포넌트 (FSD 위반 없음 — 모두 같은 slice 내부)

- `entities/attempt/ui/AttemptCardList.tsx` — 시도 이력 모바일 카드 리스트 (AttemptsTable 과 동일 slice, 데이터 동일)
- `entities/log/lib/format.ts` → `formatShortTimestamp` 추가 (모바일 로그 행 타임스탬프 축약)
- 그 외는 Tailwind 반응형 유틸 (`md:`/`sm:`) 분기로 처리 — 컴포넌트 분리 없이 같은 트리에서 두 표현 토글:
  - `widgets/sidebar`: 데스크톱 rail(`md:flex`) + 모바일 드로어(오버레이/슬라이드, 라우트 변경 자동 닫힘)
  - `widgets/header`: 햄버거 버튼 `md:hidden`
  - `entities/attempt/ui/AttemptsTable`: 테이블 `hidden md:table` + 카드 `md:hidden`
  - `entities/config/ui/ConfigRow`: `flex-col sm:flex-row` 스택
  - `entities/log/ui/LogRow`: `flex-wrap`, 메시지 `w-full md:flex-1`, 타임스탬프 short/full 토글
  - `features/log-filter/ui/LogFilterBar`: 모바일 접이식 패널 (토글 버튼 + `hidden`/`md:flex`)
  - 페이지 다이얼로그 4종: 모바일 바텀시트(`items-end`, `w-full rounded-t-md`) / sm 모달(`sm:w-80`)

드로어 open 상태는 `app/(protected)/layout.tsx`(app 레이어)에서 보유하고 Header/Sidebar 두 위젯에 props 로 주입 — 위젯 간 cross-slice import 회피 (boundaries 규칙 준수).

## PWA 구현 방식: @serwist/next (serwist 아님 = 수동)

- **선정**: `@serwist/next@9.5.11` (+`serwist@9.5.11`), MIT, next-pwa 의 유지보수 후속. npm 설치 성공하여 수동 manifest+SW 대안 불필요. TS 타입 자체 포함, 활성 유지보수. → `oss-selection` 체크리스트 통과.
- **서비스 워커** `app/sw.ts`: 정적 자산은 `defaultCache` (Next 기본), `/api/*` 는 `NetworkOnly` (폴링/SSE 데이터 stale 방지). `skipWaiting`/`clientsClaim`/`navigationPreload` 활성.
- **next.config.ts**: `withSerwistInit({ swSrc:"app/sw.ts", swDest:"public/sw.js", disable: NODE_ENV==="development" })` — dev 에서 SW 비활성.
- **manifest** `app/manifest.ts`: name/short_name/standalone/theme_color(#0f172a)/background_color/icons(192·512 any + 192·512 maskable).
- **아이콘** `public/icons/{icon,maskable}-{192,512}.png`: 네트워크 이미지 도구 없이 Node zlib 로 단색(#0f172a) 유효 PNG 생성 (검증 완료). 추후 브랜드 아이콘으로 교체 권장.
- **layout 메타**: `viewport.themeColor`, `metadata.manifest`/`appleWebApp`/`icons.apple`.
- **생성물**: `public/sw.js`(+`swe-worker-*.js`) 는 빌드 산출물 → `.gitignore` + eslint ignore 추가.

### PWA 사용법 (README 미수정 — 여기 기재)
- 프로덕션 빌드(`pnpm --filter web build && pnpm --filter web start`)에서만 SW 등록, dev 는 비활성.
- 브라우저 설치: 데스크톱 주소창 설치 아이콘 / 모바일 "홈 화면에 추가". standalone 모드로 실행.
- `/api/*` 는 항상 네트워크 직격(캐시 안 함), 정적 자산은 SW 캐시.

## 이슈 및 해결

- **next build 가 FSD `src/pages` 를 Pages Router 로 오인식** → 슬라이스 UI/테스트 파일이 라우트로 등록되어 빌드 실패 (MSW 클라이언트 번들 유입, default export 누락). dev/vitest 에서는 안 드러나던 잠재 이슈가 serwist 의 전체 빌드로 표면화.
  - **해결**: 빈 루트 `apps/web/pages/`(README 만) 추가 → Next 가 Pages Router 를 루트 `pages/` 로 인식하고 `src/pages` 스캔을 중단. App Router(루트 `app/`)는 영향 없음. 빌드 6개 라우트만 정상 prerender. (ignoreBuildErrors 등 회피책은 불필요해져 제거, ignore-loader 의존성도 제거.)
- **eslint 가 생성된 `public/sw.js` 스캔** → 209 no-undef/no-unused-expressions. eslint.config.js `ignores` 에 `public/sw.js`, `public/swe-worker-*.js` 추가로 해결.
- **react-hooks/exhaustive-deps 룰 미설치** (Sidebar 자동닫힘 effect) → disable 주석 제거하고 `onCloseRef` 패턴으로 lint 충돌 회피.

## 미완료 항목

없음 — 7.1~7.5 및 모든 T1/T2 완료.

## OSS Dependencies 추가분 (README 표 반영 대상 — Push 8 충돌 회피로 미반영)

| 패키지 | 버전 | 라이선스 | 용도 | 대안 |
|---|---|---|---|---|
| @serwist/next | 9.5.11 | MIT | Next.js PWA 서비스 워커 통합 | next-pwa(유지보수 중단) |
| serwist | 9.5.11 | MIT | SW 런타임 (Serwist/NetworkOnly/defaultCache) | workbox 직접 구성 |

## git 상태

- 5개 커밋, 브랜치 `push7-mobile-pwa`, **push 안 함** (지시 준수).
- `tasks-prd-push8.md` 워킹트리 수정분 미변경 (stash 안 함).
