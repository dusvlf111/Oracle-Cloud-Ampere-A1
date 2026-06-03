# 결과보고서: tasks-prd-push8

> 완료일: 2026-06-03
> 브랜치: `push8-ops` (HEAD `push7-mobile-pwa` 에서 분기)
> 범위: 운영 세팅 — 실사용 `.env` 생성, 서버 재시작 시 폴링 자동 재개 보장,
>       PostgreSQL/Redis env 스위치 지원, docker-compose 프로필, 실행 가이드

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 8.1 실사용 `.env` + dev 기동 정비 | server | ✅ | `f7635ad` |
| 8.2 재시작 폴링 자동 재개 보장 | server | ✅ | `f4abe55` |
| 8.3 PostgreSQL env 지원 | server | ✅ | `0fb25cc` |
| 8.4 Redis env 지원 | server | ✅ | `81ee866` |
| 8.5 실행 가이드 + 최종 검증 | docs | ✅ | (본 커밋) |

핵심 원칙 준수: **기본값 무변경** — SQLite + 인메모리 rate limit 가 디폴트,
PostgreSQL/Redis 는 `.env` + compose 프로필로만 활성화(옵셔널).

## 변경 파일

### Server (apps/server)
- `src/app/config.py` — `redis_url`, `db_pool_size`/`db_max_overflow`/`db_pool_pre_ping` 추가
- `src/app/db/session.py` — dialect 분기(postgres 풀 옵션 / sqlite WAL), `assert_schema_ready` 가드
- `src/app/main.py` — lifespan 첫 폴링 전 스키마 가드 호출
- `src/app/api/ratelimit.py` — `rate_limit_storage_uri()` (REDIS_URL 시 redis backend)
- `src/app/workers/config_task.py` — 재시작 시 백오프 초기화 동작 명문화(docstring)
- `alembic.ini` — `script_location`/`prepend_sys_path` 를 `%(here)s` 절대화(CWD 무관)
- `pyproject.toml` / `uv.lock` — `psycopg[binary]`, `limits[redis]`(+redis), dev `fakeredis[lua]`
- 테스트: `tests/unit/test_env_loading.py`, `tests/integration/test_restart_resume.py`,
  `tests/unit/db/test_engine_dialects.py`, `tests/unit/test_rate_limit_storage.py`

### Root / Ops
- `.env` — 실사용 값 생성 (커밋 안 됨, .gitignore 대상)
- `.env.example` — SESSION_SECURE/KEYS_DIR, PostgreSQL/Redis 옵션, Argon2 해시 따옴표 가이드
- `package.json` — `dev:server` 가 data/keys 준비 → `alembic upgrade head` → uvicorn(`--env-file .env`)
- `docker-compose.yml` — DATABASE_URL env-overridable, postgres(16-alpine)/redis(7-alpine) 프로필,
  DB 풀·REDIS_URL 전달, `postgres-data` volume, healthcheck
- `scripts/verify-compose.mjs` — postgres/redis 프로필·volume·healthcheck 정적 검증 확장
- `README.md` — "실행 방법" 5모드(로컬 dev/Docker/PostgreSQL/Redis/재시작 재개), OSS 표 갱신

## 테스트 결과

- 서버 pytest: **177 passed** (시작 시 155 → +22), 커버리지 **93%**
  - 8.1.T1 3 / 8.2.T1 5 / 8.3.T1 6 / 8.4.T1 8 신규
  - 8.1.T2 서버 기동 smoke: `/healthz` 200 + 로그인(정답) 200 확인 후 종료
- 웹 vitest: **113 passed** (회귀 없음 — 웹 코드 무변경)
- 루트 `pnpm test`: exit 0 (server && web)
- `node scripts/verify-compose.mjs`: OK (server 미노출, web :3000, postgres/redis 프로필)
- `node scripts/verify-workspace.mjs`: OK

## 생성된 .env 내용 요약 (실사용)

`.env` 는 `.gitignore` 대상이라 커밋되지 않음. 주요 값:

- `APP_SECRET` = 32 bytes base64 자동 생성 (`KfdEz2MD...UVq+cg=`)
- `APP_USERNAME` = `admin`
- `APP_PASSWORD_HASH` = Argon2id 해시 (작은따옴표로 감쌈 — `$` 손상 방지)
- `DATABASE_URL` = `sqlite:///./data/app.db` (로컬 dev)
- `KEYS_DIR` = `./data/keys`
- `SESSION_SECURE` = false, 로깅/동시성은 기본값
- PostgreSQL/Redis 항목은 주석 처리(미활성)

### 🔑 초기 관리자 비밀번호 (평문 — 본 보고서에만 기재)

```
username: admin
password: ddU-PWP7d4vkX-Nz
```

> 운영 반영 시 `uv run python -m app.cli hash '<새 비밀번호>'` 로 교체 권장.

## README 실행 가이드 요약

- ① 로컬 dev: `.env` 작성 → `pnpm dev:server`(alembic 선행) + `pnpm dev:web`
- ② Docker 기본: `docker compose up -d` (SQLite, web만 :3000 노출)
- ③ PostgreSQL: `.env` 에 `DATABASE_URL=postgresql+psycopg://...` + `docker compose --profile postgres up -d` → `exec server alembic upgrade head`
- ④ Redis: `.env` 에 `REDIS_URL=redis://redis:6379/0` + `docker compose --profile redis up -d`
- ⑤ 재시작 자동 재개: DB `enabled` 플래그가 진실 공급원, lifespan 이 enabled config 재spawn,
  rate_limited 백오프는 재시작 시 초기화, compose `restart: unless-stopped`

## 이슈 및 해결

1. **Argon2 해시 `$` 손상** — uv `--env-file` 이 dotenv 변수 확장을 수행해
   `$argon2id$v=19$m=...` 가 깨져 로그인 401. → `.env` 에서 해시를 **작은따옴표**로 감싸 해결,
   `.env.example` 에 가이드 추가. (8.1.T2 smoke 에서 재검증 200)
2. **alembic CWD 의존** — `script_location = alembic` 가 CWD 기준이라 루트 `dev:server`
   에서 실패. → `%(here)s/alembic` 절대화로 CWD 무관 동작(루트/apps/server 양쪽 OK).
3. **docker CLI 부재** — `docker compose config` 불가. → `verify-compose.mjs` 를 확장해
   postgres/redis 프로필·volume·healthcheck 를 정적 regex 검증으로 대체(README 명시).
4. **PostgreSQL/Redis 실 서버 부재** — postgres 분기는 실 연결 없이 엔진 풀 구성 검증,
   redis 는 `fakeredis[lua]` 로 RedisStorage 카운터(Lua incr/expire)까지 단위 검증.
   실 연결 절차는 README ③④ 에 수동 확인용으로 기재.

## 미완료 항목

없음 — 8.1~8.5 및 모든 T1/T2 완료.

## 비고

- `git push` 미수행(금지 준수). 모든 커밋은 로컬 `push8-ops` 브랜치.
- 신규 OSS 도입(psycopg/limits[redis]/fakeredis) 은 README OSS 표에 라이선스·용도 반영.
- 새로 만든 스킬 없음(기존 fastapi-patterns/python-testing/oss-selection 참조로 충분).
