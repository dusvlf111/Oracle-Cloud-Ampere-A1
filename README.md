# Oracle Cloud Ampere A1 자동 신청 시스템

OCI Free Tier Ampere A1(ARM) 인스턴스를 가용성 확보 시까지 자동으로 재시도하여
생성하는 self-hosted 시스템. FastAPI 서버 + 백그라운드 워커와 Next.js(FSD) 웹이
pnpm workspace 모노레포로 공존한다. 상세 스펙은 [`.claude/tasks/prd.md`](.claude/tasks/prd.md).

## 모노레포 구조

```
apps/
  server/   # FastAPI + 워커 (Python, uv)
  web/      # Next.js 15 (App Router) + FSD 6계층
packages/   # 공유 (현재 비어 있음)
docker-compose.yml
```

## 개발

```bash
# 의존성
pnpm install                      # 웹 + 워크스페이스
cd apps/server && uv sync         # 서버 (uv)

# 실행
pnpm dev:web                      # Next.js
pnpm dev:server                   # FastAPI (uvicorn --reload)

# 테스트 (서버 pytest + 웹 vitest)
pnpm test                         # = test:server && test:web

# 린트(FSD 레이어 규칙 포함) / 타입체크 / 빌드
pnpm lint
pnpm --filter web typecheck
pnpm build
```

## 배포 (Docker Compose)

API 서버는 호스트에 노출되지 않는다(컨테이너 `ports` 미선언, `expose`만).
브라우저는 `http://localhost:3000/api/*` 만 호출하고 Next.js `rewrites()` 가
내부 네트워크 `http://server:8000` 으로 프록시한다.

```bash
# 1. 비밀번호 해시 생성 (Push 2 의 cli 헬퍼)
docker compose run --rm server python -m app.cli hash "내비밀번호"
# 2. APP_SECRET 생성
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
# 3. .env 작성 후 기동
docker compose up -d
```

`.env.example` 참고. 보안/노출 차단 검증은 `node scripts/verify-compose.mjs`.

## OSS Dependencies

라이선스는 모두 허용(self-host, 재배포 없음). 선택 근거는 PRD §4 OSS 매트릭스 참조.

### Server (Python, uv)

| 패키지 | 용도 | 라이선스 |
|---|---|---|
| fastapi | ASGI 웹 프레임워크 | MIT |
| uvicorn[standard] | ASGI 서버 | BSD-3 |
| pydantic-settings | 타입 안전 설정 | MIT |
| sqlmodel | ORM (SQLAlchemy 2.0 + Pydantic) | MIT |
| alembic | DB 마이그레이션 | MIT |
| pytest, pytest-asyncio, pytest-cov, pytest-httpx | 테스트 | MIT |
| polyfactory | 테스트 팩토리 | MIT |
| httpx | 비동기/동기 HTTP 클라이언트 (ASGITransport) | BSD-3 |

### Web (Node, pnpm)

| 패키지 | 용도 | 라이선스 |
|---|---|---|
| next, react, react-dom | Next.js 15 / React 19 | MIT |
| @tanstack/react-query | 데이터 페칭/캐싱 | MIT |
| tailwindcss, @tailwindcss/postcss | 스타일 (v4) | MIT |
| clsx, tailwind-merge, lucide-react | shadcn/ui 유틸/아이콘 | MIT |
| eslint, typescript-eslint, eslint-config-next | 린트 | MIT |
| eslint-plugin-boundaries, eslint-plugin-import, eslint-import-resolver-typescript | FSD 레이어 규칙 강제 | MIT |
| vitest, @vitejs/plugin-react, jsdom | 테스트 러너 | MIT |
| @testing-library/react, @testing-library/user-event, @testing-library/jest-dom | 컴포넌트 테스트 | MIT |
| msw | API 모킹 | MIT |
| orval | OpenAPI → TS 클라이언트/React Query 훅 생성 | MIT |
