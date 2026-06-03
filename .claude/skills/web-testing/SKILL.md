---
name: web-testing
description: |
  본 프로젝트 웹 테스트 (Vitest + RTL + MSW). "vitest 테스트 추가", "컴포넌트 테스트", "MSW handler", "user-event", "RTL", "사용자 시나리오" 등에서 트리거.
  모든 commit 단위 작업에 테스트 동봉 필수. 등록 안 된 네트워크 호출은 테스트 실패 (`onUnhandledRequest: 'error'`).
---

# Web Testing — Vitest + RTL + MSW

## 위치 규칙

- **단위 테스트**: 대상 옆에 `*.test.tsx` (예: `src/features/auth-login/ui/LoginForm.test.tsx`)
- **통합/페이지 시나리오**: `tests/{name}.test.tsx`
- **MSW 핸들러**: `tests/mocks/handlers.ts`

## vitest.config.ts

```ts
import { defineConfig } from 'vitest/config';
import react from '@vitejs/plugin-react';
import path from 'node:path';

export default defineConfig({
  plugins: [react()],
  test: {
    environment: 'jsdom',
    globals: true,
    setupFiles: ['./tests/setup.ts'],
    coverage: {
      provider: 'v8',
      reporter: ['text', 'html'],
      thresholds: { lines: 50, branches: 50, functions: 50, statements: 50 },
    },
  },
  resolve: { alias: { '@': path.resolve(__dirname, 'src') } },
});
```

## tests/setup.ts

```ts
import '@testing-library/jest-dom/vitest';
import { afterAll, afterEach, beforeAll } from 'vitest';
import { server } from './mocks/server';

beforeAll(() => server.listen({ onUnhandledRequest: 'error' }));
afterEach(() => server.resetHandlers());
afterAll(() => server.close());
```

## tests/mocks/server.ts + handlers.ts

```ts
// server.ts
import { setupServer } from 'msw/node';
import { handlers } from './handlers';
export const server = setupServer(...handlers);

// handlers.ts
import { http, HttpResponse } from 'msw';
export const handlers = [
  http.get('/api/auth/me', () => HttpResponse.json({ username: 'admin' })),
  http.get('/api/configs', () => HttpResponse.json([])),
];
```

테스트별로 핸들러 덮어쓰기:
```ts
import { http, HttpResponse } from 'msw';
import { server } from '../../../tests/mocks/server';

it('shows error on 401', async () => {
  server.use(
    http.get('/api/auth/me', () => HttpResponse.json({ error: { code: 'unauthorized' } }, { status: 401 })),
  );
  // ...
});
```

## RTL + user-event 패턴

```tsx
import { render, screen } from '@testing-library/react';
import userEvent from '@testing-library/user-event';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { LoginForm } from './LoginForm';

function wrap(ui: React.ReactNode) {
  const qc = new QueryClient({ defaultOptions: { queries: { retry: false } } });
  return <QueryClientProvider client={qc}>{ui}</QueryClientProvider>;
}

it('submits credentials', async () => {
  const user = userEvent.setup();
  render(wrap(<LoginForm />));
  await user.type(screen.getByLabelText(/username/i), 'admin');
  await user.type(screen.getByLabelText(/password/i), 'secret');
  await user.click(screen.getByRole('button', { name: /login/i }));
  expect(await screen.findByText(/welcome/i)).toBeInTheDocument();
});
```

## 쿼리 선택 우선순위 (Testing Library 권장)

1. `getByRole` (접근성 + 의미)
2. `getByLabelText` (폼)
3. `getByPlaceholderText`
4. `getByText`
5. `getByDisplayValue`
6. `getByAltText` (이미지)
7. `getByTitle`
8. `getByTestId` — 최후 수단

## 비동기 — findBy / waitFor

```tsx
expect(await screen.findByText(/loaded/i)).toBeInTheDocument();
// or
await waitFor(() => expect(mockFn).toHaveBeenCalled());
```

`getBy*` 는 동기 — 비동기 등장에는 `findBy*` (자동 retry).

## SSE 테스트 (로그 스트림)

`EventSource` 는 jsdom 에 없음. `event-source-polyfill` 또는 모킹:
```ts
class FakeEventSource {
  onmessage: ((e: MessageEvent) => void) | null = null;
  close = vi.fn();
}
vi.stubGlobal('EventSource', FakeEventSource);
```
또는 SSE 호출 자체를 hook 으로 분리해 hook 만 단위 테스트.

## Orval 생성 훅 사용 테스트

Orval 이 생성한 `useGetConfigs()` 같은 훅은 MSW 가 가로채는 fetch 호출을 함. 따라서 컴포넌트 테스트에서 그대로 사용 + handler 만 신경 쓰면 됨.

## FSD 슬라이스별 테스트 범위

| Slice | 테스트 |
|---|---|
| `shared/ui/*` | 시각 + 접근성 (snapshot 또는 axe) |
| `shared/lib/*` | 순수 함수 단위 |
| `entities/*/model` | 상태/훅 단위 |
| `entities/*/ui` | 렌더 + props 분기 |
| `features/*` | 사용자 액션 시나리오 (user-event) |
| `widgets/*` | 통합 (여러 features 결합) |
| `pages/*` | 시나리오 (`tests/`) |

## 실행

```bash
pnpm test                 # 한 번 실행
pnpm test:watch           # 개발 중
pnpm test --coverage
pnpm test src/features/auth-login
```

## 안티패턴

- `getByTestId` 남용 (최후 수단)
- 실제 fetch (MSW 없이) → `onUnhandledRequest: 'error'` 가 잡아냄
- `act()` 명시적 호출 → `userEvent` / `findBy*` 가 알아서 함
- `setTimeout` 으로 비동기 대기 → `waitFor` / `findBy*`
- snapshot 만으로 검증 → 의미 있는 assertion 추가
- 한 테스트에서 여러 페이지/플로우 시뮬레이션 → 분리
