# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 7

> PRD: `.claude/tasks/prd.md` (확장 — 사용자 추가 요구사항)
> Push 범위: 웹 모바일 대응 (반응형 + 필요 시 모바일 전용 컴포넌트 분리) + PWA 설치 지원
> 상태: ✅ 완료

---

### 관련 파일

- `apps/web/src/shared/lib/` - `useMediaQuery` 등 반응형 훅
- `apps/web/src/widgets/sidebar/` - 데스크톱 사이드바 → 모바일 드로어 분리
- `apps/web/src/widgets/header/` - 햄버거 메뉴 버튼 (모바일)
- `apps/web/src/entities/attempt/` - 시도 이력 테이블 → 모바일 카드 뷰
- `apps/web/src/pages/{dashboard,credentials,configs,channels,logs}/` - 페이지 반응형
- `apps/web/app/layout.tsx` - viewport/theme-color 메타
- `apps/web/app/manifest.ts` - PWA Web App Manifest
- `apps/web/public/icons/` - PWA 아이콘 (192/512, maskable)
- `apps/web/next.config.ts` - 서비스 워커 통합 (@serwist/next)

---

### 에이전트 실행 전략 (push-lead)

전 작업 `web-worker` 담당, 순차 실행 (7.1 기반 위에 7.2~7.4 가 쌓이고, 7.5 는 독립적이라 마지막 또는 병렬 가능).

| 작업 | 담당 | 의존성 |
|---|---|---|
| 7.1 반응형 기반 (드로어/햄버거/훅) | `web-worker` | — |
| 7.2 대시보드+시도 이력 모바일 | `web-worker` | 7.1 |
| 7.3 관리 페이지 3종 모바일 | `web-worker` | 7.1 |
| 7.4 로그 페이지 모바일 | `web-worker` | 7.1 |
| 7.5 PWA (manifest + SW + 설치) | `web-worker` | — (7.1~7.4 와 파일 비중첩) |

- 모바일 분기 원칙: Tailwind 반응형 유틸 우선 (`sm:`/`md:`/`lg:`), 구조가 크게 다를 때만 컴포넌트 분리 (`ui/XxxMobile.tsx` — 같은 slice 내부, FSD 위반 금지)
- PWA OSS 선정: `@serwist/next` (next-pwa 의 유지보수 후속, MIT) — `oss-selection` 체크리스트 통과 후 README OSS 표 기재
- 각 T2 커밋 직전 `test-runner` 검증, 7.5.T2 에서 lint+tsc+전체 vitest 게이트
- 참조 스킬: `fsd-architecture`, `web-testing`, `oss-selection`

---

## 작업

- [x] 7.0 모바일 대응 + PWA (Push 7)
    - [x] 7.1 반응형 기반 인프라 — `shared/lib/useMediaQuery` 훅 (SSR 안전), `widgets/sidebar` 모바일 드로어 변환 (오버레이 + 슬라이드, 라우트 이동 시 자동 닫힘), `widgets/header` 햄버거 버튼 (`md:` 미만 표시), `app/layout.tsx` viewport 메타 (`width=device-width, initial-scale=1`), `(protected)/layout.tsx` 반응형 그리드 (모바일: 사이드바 숨김/드로어)
        - [x] 7.1.T1 vitest 테스트 작성 — useMediaQuery (matchMedia mock), 드로어 열기/닫기/라우트 변경 시 닫힘, 햄버거 버튼 표시 분기
        - [x] 7.1.T2 `pnpm --filter web vitest run src/widgets src/shared/lib` 실행 및 검증
    - [x] 7.2 대시보드 + 시도 이력 모바일 — 카운트 카드 1열 스택 (`grid-cols-1 sm:grid-cols-2 lg:grid-cols-4`), `entities/attempt` 시도 이력: 데스크톱 테이블 유지 + 모바일 카드 리스트 컴포넌트 분리 (`AttemptCardList`), 성공 인스턴스 카드 OCID 줄바꿈/복사 버튼
        - [x] 7.2.T1 vitest 테스트 작성 — 모바일 카드 리스트 렌더 (상태 배지/필터 동작 동일성), 뷰포트 분기 (matchMedia mock)
        - [x] 7.2.T2 `pnpm --filter web vitest run src/entities/attempt src/pages/dashboard` 실행 및 검증
    - [x] 7.3 관리 페이지 3종 모바일 — credentials/configs/channels: 폼 그리드 1열 전환, 목록 테이블/행 → 모바일 카드 전환, 다이얼로그/모달 모바일 풀스크린 (`sm:max-w-…` 분기), 터치 타깃 44px 보장 (버튼/토글)
        - [x] 7.3.T1 vitest 테스트 작성 — 각 페이지 모바일 렌더 (카드 전환, 기존 기능 시나리오 회귀 없음 — 생성/토글/테스트 발송)
        - [x] 7.3.T2 `pnpm --filter web vitest run src/pages/credentials src/pages/configs src/pages/channels` 실행 및 검증
    - [x] 7.4 로그 페이지 모바일 — `features/log-filter` 모바일에서 접이식 필터 패널 (bottom sheet 스타일), 로그 행 좁은 화면 레이아웃 (타임스탬프 축약, 메시지 줄바꿈), 가상 스크롤 모바일 동작 유지
        - [x] 7.4.T1 vitest 테스트 작성 — 필터 패널 토글, 모바일 로그 행 렌더, 기존 SSE/일시정지 회귀 없음
        - [x] 7.4.T2 `pnpm --filter web vitest run src/features/log-filter src/widgets/log-stream src/pages/logs` 실행 및 검증
    - [x] 7.5 PWA — `@serwist/next` 도입 (서비스 워커: 정적 자산 캐시, `/api/*` 는 NetworkOnly — 폴링 데이터 stale 방지), `app/manifest.ts` (name/short_name/standalone/theme_color/icons 192·512·maskable), `public/icons/` 아이콘 생성, `app/layout.tsx` theme-color/apple-touch-icon 메타, dev 에서는 SW 비활성
        - [x] 7.5.T1 vitest 테스트 작성 — manifest.ts 필드 검증 (필수 키/아이콘 사이즈), next.config 통합 단위 테스트
        - [x] 7.5.T2 `pnpm --filter web build` (SW 생성물 확인) + `pnpm --filter web test` + lint/tsc 전체 게이트 실행 및 검증
