---
name: fsd-architecture
description: |
  Next.js 웹의 FSD (Feature-Sliced Design) 슬라이스/레이어 결정. "이 컴포넌트 어디에 둘까", "feature 만들어", "entity 추출", "FSD 위반 같은데", "page에서 뭐 import하지" 등에서 트리거.
  본 프로젝트는 `src/{app,pages,widgets,features,entities,shared}` 6계층. `eslint-plugin-boundaries` 강제. Next.js `app/` 은 얇은 라우트 진입점만.
---

# FSD Architecture — Feature-Sliced Design

본 프로젝트 Next.js 웹의 슬라이스/레이어 결정 가이드.

## 레이어 (위 → 아래)

| 레이어 | 책임 | 예시 |
|---|---|---|
| `app` | Providers, global setup | QueryClientProvider, ThemeProvider, globals.css |
| `pages` | 페이지 단위 조합 | LoginPage, DashboardPage, ConfigsPage |
| `widgets` | 큰 UI 블록 (재사용 가능) | Header, Sidebar, LogStream, AttemptsTable |
| `features` | 사용자 액션 단위 | auth-login, config-create, channel-test, log-filter |
| `entities` | 도메인 엔티티 (조회/표시) | config, credential, channel, attempt, log |
| `shared` | 도메인 무관 공용 | ui kit, http client, utils, api(Orval) |

## Import 규칙 (`eslint-plugin-boundaries` 강제)

- 상위 → 하위 OK
- 하위 → 상위 **금지**
- 같은 레이어 다른 slice 간 직접 import **금지** (`shared` 또는 명시적 deps 만)
- 각 slice 는 `index.ts` 공개 API — 외부에서 그것만 import

```
허용:   pages/configs → features/config-create → entities/config → shared/ui/Button
금지:   entities/config → features/config-create (역방향)
금지:   features/auth-login → features/config-create (같은 레이어)
```

## Slice 디렉토리 패턴

```
src/{layer}/{slice-name}/
├── ui/                  # 컴포넌트
├── model/               # 상태, 훅, 비즈니스 로직
├── api/                 # 슬라이스 전용 API 래퍼 (대부분 shared/api 직접 사용)
├── lib/                 # 슬라이스 내부 유틸
└── index.ts             # 공개 API (외부에서 import 가능한 것만)
```

`shared/api` 는 Orval 생성물이라 디렉토리 구조가 다름.

## 어디에 둬야 할지 결정 트리

```
이 코드는…
├─ 페이지 전체를 구성? → pages
├─ 페이지 일부지만 사용자 액션? → features
├─ 페이지 일부지만 단순 표시? → entities (조회/렌더)
├─ 여러 페이지 공통 큰 UI 블록? → widgets
├─ 도메인 무관 (버튼/입력/유틸)? → shared
└─ 전역 설정/Provider? → app
```

## Slice 명명

- `feature`: 동사 + 명사 (`auth-login`, `config-create`, `channel-test`)
- `entity`: 명사 (`config`, `credential`)
- `widget`: 명사 (`sidebar`, `log-stream`)
- `page`: 명사 + Page (`ConfigsPage`)

## Next.js App Router 와의 매핑

```
app/configs/page.tsx  ←  얇은 진입점
  import { ConfigsPage } from '@/pages/configs';
  export default ConfigsPage;
```

`app/` 내 페이지 컴포넌트는 **3줄 이내**. 모든 조합은 `src/pages/{name}` 에.

## tsconfig path 별칭

```json
{
  "paths": {
    "@/app/*":      ["./src/app/*"],
    "@/pages/*":    ["./src/pages/*"],
    "@/widgets/*":  ["./src/widgets/*"],
    "@/features/*": ["./src/features/*"],
    "@/entities/*": ["./src/entities/*"],
    "@/shared/*":   ["./src/shared/*"]
  }
}
```

## ESLint 규칙 (요지)

```js
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
}]
```

## 안티패턴

- **page 가 entity 의 내부 파일을 직접 import** — `index.ts` 공개 API 만 사용
- **entity 가 feature 를 import** — 역방향, 즉시 에러
- **feature 끼리 직접 import** — 같은 레이어 금지. 공통 로직이면 entity 또는 shared 로 추출
- **shared 가 도메인 코드 포함** — `shared/api/configs/...` 는 Orval 생성물(예외)이지만, shared 의 다른 곳에 `Config` 타입 알면 안 됨
- **App Router 페이지 컴포넌트에 비즈니스 로직** — 진입점은 import + export 만

## 신규 Slice 생성 절차

1. 어느 레이어인지 결정 트리로 판단
2. 디렉토리 생성: `src/{layer}/{name}/` + `ui/` `model/` `index.ts`
3. `index.ts` 에 공개 컴포넌트/훅만 export
4. 테스트 파일 옆에 `*.test.tsx`
5. import 시 `@/...` 별칭 사용 (상대 경로 금지)
