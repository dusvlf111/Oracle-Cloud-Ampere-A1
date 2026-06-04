# Oracle Cloud Ampere A1 자동 신청 시스템

OCI Free Tier Ampere A1(ARM) 인스턴스를 가용성 확보 시까지 자동으로 재시도하여
생성하는 self-hosted 시스템. FastAPI 서버 + 백그라운드 워커와 Next.js(FSD) 웹이
pnpm workspace 모노레포로 공존한다. 상세 스펙은 [`.claude/tasks/prd.md`](.claude/tasks/prd.md).

OCI Always Free 의 Ampere A1 인스턴스는 인기 리전에서 상시 용량 부족(`Out of host
capacity`)으로 신청이 거의 즉시 거부되기 때문에, 사람이 수동으로 콘솔을 반복 클릭하는
대신 이 시스템이 등록된 인스턴스 설정으로 생성 요청을 일정 간격으로 **자동 재시도**한다.
용량이 확보되어 인스턴스 생성에 **성공하면 즉시 폴링을 중단**하고 등록해 둔 알림 채널
(Discord/Slack/Telegram/ntfy 등)로 다중 발송한다. 웹은 **최초 가입 사용자가 곧 관리자**가
되는 부트스트랩 모델이며, 이후 가입자는 관리자 **승인제**로 추가되는 다중 사용자 구조다.

## 스크린샷

### 대시보드

![대시보드](README/1_dashboard.png)

폴링 운영 현황을 한눈에 보는 메인 화면이다. 상단에 활성 설정(Active configs) /
비활성 설정(Inactive configs) / 전체 설정(Total configs) 개수를 카드로 요약하고,
"폴링 중인 설정" 영역에 현재 재시도 중인 인스턴스 설정(Shape `VM.Standard.A1.Flex`,
스펙 4 OCPU / 24 GB, 폴링 간격 300s, 누적 시도 횟수 등)을 보여 준다. 하단의
"최근 시도 이력" 테이블은 Config ID 입력과 Status 드롭다운(All 등)으로 필터링할 수 있고,
시각(Time)·대상 설정(Config)·상태(Status, 예: `Out of host capacity`)·소요 시간(Duration,
ms/s)·상세 사유(Detail)를 시간 역순으로 나열해 매 시도의 결과를 추적하게 해 준다.

### OCI 자격증명

![OCI 자격증명](README/2_credentials.png)

인스턴스 생성에 필요한 OCI API 자격증명을 등록·관리하는 화면이다. 상단 "구성 파일
붙여넣기" 드롭다운으로 `~/.oci/config` 형식 텍스트를 붙여넣어 필드를 자동 채우거나,
Name·Tenancy OCID·User OCID·Fingerprint·Region(드롭다운 선택 또는 "직접 입력")·
Passphrase(선택)를 직접 입력하고 Private key(PEM) 파일을 업로드한 뒤 "Create credential"
로 저장한다. 비밀 값은 서버에서 AES-256-GCM 으로 암호화되어 보관되며, 하단 "Existing"
목록에서 등록된 자격증명을 확인할 수 있다.

### 인스턴스 설정

![인스턴스 설정](README/3_configs.png)

자동 재시도로 생성할 인스턴스의 사양을 정의하는 화면이다. Name, SSH public key,
사용할 Credential(드롭다운 선택)을 지정하고 Shape(`VM.Standard.A1.Flex`),
OCPUs(예: 4, "Free Tier 한도: 4 OCPU" 안내), Memory(예: 24 GB, "권장: OCPU×6 = 24 GB"),
Boot volume(예: 50 GB, "Free Tier 총 200 GB 한도"), Availability domain(자격증명 선택 후
선택), Image OCID 등을 입력한다. Free Tier 한도를 넘지 않도록 각 필드에 가이드 문구가
표시되며, 저장된 설정이 활성화되면 대시보드의 폴링 대상이 된다.

### 알림 채널

![알림 채널](README/4_channels.png)

인스턴스 생성 성공 시 통지받을 채널을 등록하는 화면이다. Name 을 지정하고
Type 드롭다운(예: discord)에서 채널 종류를 고른 뒤 Webhook URL 을 입력하고
"Create channel" 로 추가한다. 채널 종류에 따라 입력 필드가 달라지며(웹훅 URL,
토큰 등), 하단 "Existing" 목록에서 등록된 채널을 확인하고 테스트 발송으로 연결을
검증할 수 있다. 발송은 실패 시 재시도/백오프(tenacity)가 적용된다.

### 로그

![로그](README/5_logs.png)

워커와 API 가 남기는 로그를 실시간으로 조회하는 화면이다. 상단 필터 바에서
Levels(DEBUG/INFO/WARNING/CRITICAL 토글), Logger, Config ID, Since/Until(기간),
Search(메시지 검색)로 좁혀 볼 수 있고 Reset 으로 초기화한다. 로그 행은 시각·레벨·
로거 이름(예: `app.workers.config_loop`)·메시지(예: `OutOfCapacity`, `launch_instance`)와
오른쪽에 관련 config/credential 태그를 함께 표시한다. 표시 중인 행 수가 나오며
"Pause" 버튼으로 실시간 스트림(SSE)을 일시정지하고, "Delete log..." 로 로그를 정리할 수
있다(대량일 때 가상 스크롤 적용).

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

## 실행 방법

기본 동작은 **무설정** 이다 — SQLite + 인메모리 로그인 rate limit. PostgreSQL/Redis 는
**풀 모드 오버라이드** (`docker-compose.full.yml`) 또는 `.env` 로 켜는 **옵션**이다
(미설정 시 외부 서비스 의존 없음).

> **자동 동기화**: `dev:server`/Docker 서버 기동은 `alembic upgrade head` 를 선행하고,
> `dev:web`/웹 빌드는 `scripts/sync-api.mjs` 가 OpenAPI → Orval 클라이언트를 자동
> 재생성한다 (스키마 미변경 시 생략, uv 없는 환경은 커밋된 `apps/server/openapi.json`
> 스냅샷 사용). 수동 실행: `pnpm gen:api`.

### ① 로컬 dev (uv + pnpm 듀얼 기동)

```bash
cp .env.example .env
# .env 작성:
#  - APP_SECRET:  python -c "import secrets,base64;print(base64.b64encode(secrets.token_bytes(32)).decode())"
#  - APP_PASSWORD_HASH:  cd apps/server && uv run python -m app.cli hash '내비밀번호'
#       ⚠️ 해시에 $ 가 있으므로 .env 에서 반드시 작은따옴표로 감쌀 것
#  - 로컬 dev 는 DATABASE_URL=sqlite:///./data/app.db 권장
#    (KEYS_DIR 은 Push 11 부터 미사용 — OCI private key 는 DB 에 Fernet 암호화 저장)

pnpm dev:server   # alembic upgrade head → uvicorn :8000 (.env 자동 로드)
pnpm dev:web      # sync-api(Orval 자동 재생성) → Next.js :3000 (/api 는 rewrites 로 :8000 프록시)
```

### ② Docker — 간단 모드 (SQLite, 기본)

```bash
cp .env.example .env   # APP_SECRET / APP_PASSWORD_HASH 채우기
docker compose up -d   # 또는 pnpm compose:up
```

`web` 만 호스트 `3000` 에 노출되고 `server` 는 compose 네트워크 내부 전용이다.
DB 는 `./data` 볼륨의 SQLite 이며 컨테이너 재시작 시 lifespan 이 폴링 supervisor 를
다시 기동한다(아래 ⑤). 서버 컨테이너는 시작 시 `alembic upgrade head` 를 자동 수행한다.

### ③ Docker — 풀 모드 (PostgreSQL + Redis 동봉 호스팅)

```bash
docker compose -f docker-compose.yml -f docker-compose.full.yml up -d
# 또는 pnpm compose:full
# 또는 .env 에 COMPOSE_FILE=docker-compose.yml:docker-compose.full.yml 지정 후 docker compose up -d
```

오버라이드가 PostgreSQL 16 + Redis 7 컨테이너를 띄우고 server 의
`DATABASE_URL`/`REDIS_URL` 을 자동 연결한다 (둘 다 호스트 미노출 — 내부 네트워크 전용).
`.env` 에 `DATABASE_URL`/`REDIS_URL` 을 직접 지정하면 외부 인스턴스로 우선 연결된다.
계정 변경: `POSTGRES_USER`/`POSTGRES_PASSWORD`/`POSTGRES_DB`,
풀 튜닝: `DB_POOL_SIZE`/`DB_MAX_OVERFLOW`/`DB_POOL_PRE_PING`.

### ④ 외부 PostgreSQL/Redis 사용 (선택)

```bash
# .env 에만 지정하면 간단 모드 그대로 외부 서비스에 연결된다
DATABASE_URL=postgresql+psycopg://user:pass@db.example.com:5432/oci
REDIS_URL=redis://cache.example.com:6379/0
```

`REDIS_URL` 이 비어 있으면 인메모리 rate limit 저장소를 쓴다(프로세스 단위).
SQLite 가 아니면 SQLAlchemy 커넥션 풀이 적용된다(`db/session.py` dialect 분기).

### ⑤ 재시작 자동 재개 동작

- 폴링 상태의 **단일 진실 공급원은 DB 의 `InstanceConfig.enabled` 플래그**다.
- 프로세스/컨테이너 재시작 시 FastAPI lifespan 이 폴링 supervisor 를 새로 생성하고,
  `enabled=True` 인 모든 config 의 폴링 task 를 즉시 재spawn 한다.
- 성공/인증오류로 `enabled=False` 가 된 config 는 재시작 후에도 재개되지 않는다.
- `rate_limited` 백오프·tenacity 재시도 카운터는 in-memory 라서 재시작 시 초기화되어
  즉시 재시도한다. compose `restart: unless-stopped` 로 크래시 시에도 자동 복구된다.

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
node scripts/verify-compose.mjs    # server 미노출 + web :3000 + postgres/redis 프로필·volume·healthcheck 정적 검증
node scripts/verify-workspace.mjs  # pnpm workspace 구성 확인
```

> docker CLI 가 있는 환경이라면 `docker compose config` /
> `docker compose --profile postgres --profile redis config` 로 동일하게 검증 가능하다.

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
| cryptography | AES-256-GCM 암복호화 (passphrase/채널 토큰 `config_enc`) + Fernet (OCI private key `private_key_enc`, Push 11) | Apache-2.0 / BSD-3 |
| tenacity | 알림 발송 재시도/백오프 (httpx 5xx·timeout) | Apache-2.0 |
| python-multipart | credentials API multipart 폼 + PEM 파일 업로드 | Apache-2.0 |
| oci | Oracle Cloud 공식 SDK (자격증명 verify, 인스턴스 생성) | UPL-1.0 / Apache-2.0 |
| psycopg[binary] | PostgreSQL 드라이버 (옵션 — `DATABASE_URL=postgresql+psycopg://`) | LGPL-3.0 |
| limits[redis] | slowapi rate-limit 저장소 backend (옵션 — `REDIS_URL` 설정 시 Redis) | MIT |
| fakeredis[lua] (dev) | Redis 저장소 단위 테스트 (Lua 스크립트 포함, 실 서버 불필요) | BSD-3 |

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
