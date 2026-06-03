# Tasks: Oracle Cloud Ampere A1 자동 신청 시스템 - Push 8

> PRD: `.claude/tasks/prd.md` (확장 — 사용자 추가 요구사항)
> Push 범위: 운영 세팅 — 실사용 `.env` 생성, 서버 재시작 시 폴링 루프 자동 재개 보장, PostgreSQL/Redis env 스위치 지원, docker-compose 프로필, 실행 가이드
> 상태: 🔲 진행 중

---

### 관련 파일

- `.env` - 실사용 값 생성 (APP_SECRET, APP_PASSWORD_HASH 등)
- `.env.example` - PostgreSQL/Redis 항목 추가
- `apps/server/src/app/config.py` - `redis_url` 등 설정 추가
- `apps/server/src/app/db/session.py` - PostgreSQL 분기 (pool 설정)
- `apps/server/src/app/api/deps.py` - slowapi storage Redis 전환
- `apps/server/src/app/workers/poller.py` - 재시작 재개 검증/보강
- `apps/server/pyproject.toml` - `psycopg[binary]`, `redis`/`limits[redis]` 의존성
- `docker-compose.yml` - postgres/redis 프로필 서비스
- `README.md` - 실행 가이드 (dev/Docker/PostgreSQL/Redis)

---

### 에이전트 실행 전략 (push-lead)

전 작업 `server-worker` 담당 (8.5 문서는 push-lead 직접 가능), 순차 실행.

| 작업 | 담당 | 의존성 |
|---|---|---|
| 8.1 .env 생성 + dev 실행 스크립트 | `server-worker` | — |
| 8.2 재시작 자동 재개 보장 | `server-worker` | — |
| 8.3 PostgreSQL env 지원 | `server-worker` | — |
| 8.4 Redis env 지원 | `server-worker` | 8.3 (compose 프로필 함께 정리) |
| 8.5 실행 가이드 문서 | `server-worker` 또는 push-lead | 8.1~8.4 |

- 원칙: **기본값은 변경 없음** (SQLite + in-memory rate limit) — env 설정 시에만 PostgreSQL/Redis 활성 (옵셔널 의존성, 미설정 시 import 회피)
- PostgreSQL/Redis 실 서버 없는 환경 — 테스트는 URL 분기/엔진 옵션/storage 선택 로직 단위 검증 (실 연결 mock)
- 각 T2 커밋 직전 `test-runner` 검증, 8.5.T2 에서 전체 스위트 게이트
- 참조 스킬: `fastapi-patterns`, `python-testing`, `oss-selection`

---

## 작업

- [ ] 8.0 운영 세팅 (Push 8)
    - [x] 8.1 실사용 `.env` 생성 + dev 편의 — APP_SECRET (32 bytes base64 자동 생성), APP_USERNAME=admin, APP_PASSWORD_HASH (`uv run python -m app.cli hash` 로 임의 초기 비밀번호 해시 — 평문 비밀번호는 `.env` 주석이 아닌 최종 보고에만 기재), DATABASE_URL 은 로컬 dev 용 `sqlite:///./data/app.db` (Docker 용은 compose 가 override), `data/keys/` 디렉토리 준비, 루트 `package.json` 에 `dev:server` 가 `.env` 로드 + alembic upgrade 선행하도록 정비
        - [x] 8.1.T1 pytest 테스트 작성 — Settings env 로딩 (`.env` override), cli hash 출력 검증 회귀
        - [x] 8.1.T2 `.env` 로 서버 기동 smoke (`uv run uvicorn app.main:app --port 8001` → `/healthz` 200 → 로그인 성공 확인 후 종료) 실행 및 검증
    - [x] 8.2 재시작 시 폴링 루프 자동 재개 보장 — supervisor 가 startup 시 DB 의 `enabled=True` config 를 즉시 재spawn 하는지 통합 테스트로 고정 (재시작 시뮬레이션: supervisor 종료 → 새 supervisor 기동 → 기존 enabled config task 재생성 확인), lifespan 에서 첫 폴링 전 alembic 적용 상태 가드, `rate_limited`/백오프 상태가 재시작 후 초기화되어 즉시 재시도되는 동작 명문화 (문서 + 테스트), compose `restart: unless-stopped` 유지 확인
        - [x] 8.2.T1 pytest 테스트 작성 — `tests/integration/test_restart_resume.py` (enabled config 2개 + 비활성 1개 상태에서 supervisor 재기동 → enabled 만 재spawn, 성공 config 는 재시작 후 미재개)
        - [x] 8.2.T2 `uv run pytest -q tests/integration/` 실행 및 검증
    - [ ] 8.3 PostgreSQL env 지원 — `pyproject.toml` 에 `psycopg[binary]` 추가, `db/session.py` postgres 분기 (`pool_size`/`max_overflow`/`pool_pre_ping` env 조정 가능, sqlite 전용 connect_args/WAL 은 sqlite 에만), alembic env 가 동일 URL 사용 확인, `docker-compose.yml` 에 `postgres` 프로필 서비스 (postgres:16-alpine, volume, healthcheck, server 가 프로필 활성 시 `DATABASE_URL=postgresql+psycopg://...` 사용 예시 주석), `.env.example` 에 PostgreSQL 항목
        - [ ] 8.3.T1 pytest 테스트 작성 — `tests/unit/db/test_engine_dialects.py` (sqlite URL → WAL pragma 등록/postgres URL → pool 옵션 적용·pragma 미등록, URL 분기 로직 — 실 연결 없이 엔진 구성 검증)
        - [ ] 8.3.T2 `uv run pytest -q tests/unit/db/` + `docker compose config` 정적 검증 (프로필 포함) 실행 및 검증
    - [ ] 8.4 Redis env 지원 — `REDIS_URL` 설정 추가 (기본 빈값 = 미사용), slowapi rate limit storage 를 `REDIS_URL` 설정 시 redis backend 로 전환 (`limits[redis]`), 미설정 시 기존 in-memory 유지 (로그인 차단 로직 포함 storage 추상화), `docker-compose.yml` 에 `redis` 프로필 서비스 (redis:7-alpine, healthcheck), `.env.example` 에 Redis 항목
        - [ ] 8.4.T1 pytest 테스트 작성 — `tests/unit/test_rate_limit_storage.py` (REDIS_URL 미설정 → memory storage / 설정 → redis storage URI 선택, fakeredis 또는 mock 으로 차단 카운터 동작), 기존 rate limit 테스트 회귀 없음
        - [ ] 8.4.T2 `uv run pytest -q tests/unit/test_rate_limit_storage.py tests/api/test_auth_ratelimit.py` 실행 및 검증
    - [ ] 8.5 실행 가이드 + 최종 검증 — README 에 "실행 방법" 섹션 (① 로컬 dev: uv + pnpm 듀얼 기동, ② Docker: `docker compose up -d`, ③ PostgreSQL 전환: `--profile postgres` + DATABASE_URL, ④ Redis 전환: `--profile redis` + REDIS_URL, ⑤ 재시작 자동 재개 동작 설명), `.env.example` 최종 정리, OSS 표 갱신 (psycopg/limits)
        - [ ] 8.5.T1 전체 회귀 — 서버 pytest 전체 + 웹 vitest 전체 통과 확인
        - [ ] 8.5.T2 루트 `pnpm test` + `docker compose config`/`docker compose --profile postgres --profile redis config` 정적 검증 실행 및 검증
