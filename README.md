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

### 부트스트랩 절차 (PRD §10)

```bash
# 1. 비밀번호 해시 생성 (Argon2id) — cli 헬퍼
docker compose run --rm server python -m app.cli hash "내비밀번호"
#    출력된 $argon2id$... 해시를 .env 의 APP_PASSWORD_HASH 에 붙여넣기

# 2. APP_SECRET 생성 (32 bytes base64 — 세션 서명 + AES-256-GCM 키 도출)
python -c "import secrets, base64; print(base64.b64encode(secrets.token_bytes(32)).decode())"
#    출력 값을 .env 의 APP_SECRET 에 붙여넣기

# 3. .env 작성 (.env.example 복사) 후 스택 기동
cp .env.example .env      # 위 1~2 값 채우기
docker compose up -d
```

기동 후 `web` 컨테이너만 호스트 `3000` 포트에 노출된다. `server` 는 같은 compose
네트워크 안에서만 접근 가능하고, FastAPI lifespan 이 폴링 supervisor + log_pruner 를
백그라운드 task 로 기동한다(PRD §7.3, §9.3.8).

### 외부 노출 차단 검증 (PRD §13)

```bash
# 서버는 호스트에 미노출 → connection refused 이어야 정상
curl -sf http://localhost:8000/healthz && echo "노출됨(실패)" || echo "차단됨(정상)"

# Next.js rewrites 경유는 성공해야 정상
curl -sf http://localhost:3000/api/healthz && echo "프록시 OK"
```

> 참고: 본 작업 환경에는 docker 가 설치되어 있지 않아 라이브 기동/curl 검증을 수행할
> 수 없다. 대신 `node scripts/verify-compose.mjs` 로 `docker-compose.yml` 의
> `ports`/`expose`/rewrites 구성을 **정적 검증**한다(아래 "검증" 참조).

### 검증 (정적)

```bash
node scripts/verify-compose.mjs    # server ports 미선언 + expose:8000, web ports:3000 확인
node scripts/verify-workspace.mjs  # pnpm workspace 구성 확인
```

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
| argon2-cffi | Argon2id 비밀번호 해시 (OWASP 권장) | MIT |
| typer | CLI 헬퍼 (`python -m app.cli hash`) | MIT |
| itsdangerous | 세션 쿠키 서명 (SessionMiddleware) | BSD-3 |
| slowapi | 로그인 rate limit (메모리 backend) | MIT |
| python-ulid | 요청 ID (ULID) 부여 | MIT |
| sse-starlette | 로그 실시간 스트림 SSE (`/api/logs/stream`, EventSourceResponse) | BSD-3 |
| cryptography | AES-256-GCM 암복호화 (passphrase/채널 토큰 `config_enc`) | Apache-2.0 / BSD-3 |
| tenacity | 알림 발송 재시도/백오프 (httpx 5xx·timeout) | Apache-2.0 |
| python-multipart | credentials API multipart 폼 + PEM 파일 업로드 | Apache-2.0 |
| oci | Oracle Cloud 공식 SDK (자격증명 verify, 인스턴스 생성) | UPL-1.0 / Apache-2.0 |

### Web (Node, pnpm)

| 패키지 | 용도 | 라이선스 |
|---|---|---|
| next, react, react-dom | Next.js 15 / React 19 | MIT |
| @tanstack/react-query | 데이터 페칭/캐싱 | MIT |
| tailwindcss, @tailwindcss/postcss | 스타일 (v4) | MIT |
| clsx, tailwind-merge, lucide-react | shadcn/ui 유틸/아이콘 | MIT |
| react-hook-form | 폼 상태 관리 | MIT |
| zod | 런타임 스키마 검증 (폼/에러 파싱) | MIT |
| @hookform/resolvers | react-hook-form ↔ zod 연결 | MIT |
| @tanstack/react-virtual | 로그 뷰어 가상 스크롤 (500행 초과 시) | MIT |
| @tanstack/react-table | 시도 이력 테이블 (headless, 대시보드) | MIT |
| eslint, typescript-eslint, eslint-config-next | 린트 | MIT |
| eslint-plugin-boundaries, eslint-plugin-import, eslint-import-resolver-typescript | FSD 레이어 규칙 강제 | MIT |
| vitest, @vitejs/plugin-react, jsdom | 테스트 러너 | MIT |
| @vitest/coverage-v8 | 웹 테스트 커버리지(v8 provider) | MIT |
| @testing-library/react, @testing-library/user-event, @testing-library/jest-dom | 컴포넌트 테스트 | MIT |
| msw | API 모킹 | MIT |
| orval | OpenAPI → TS 클라이언트/React Query 훅 생성 | MIT |
