# 결과보고서: tasks-multiuser-auth-push9

> 완료일: 2026-06-04
> 범위: 서버 — User 모델 + 무중단 마이그레이션, 승인제 회원가입, 유저 관리 API, 리소스/조회 소유권 스코프
> 브랜치: `push9-multiuser-server` (base `origin/main` cf5a084) — **push 미수행** (메인 에이전트 처리)

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 9.1 User 모델 + 무중단 owner_id 마이그레이션 | server | ✅ | b565912 |
| 9.2 User 테이블 기반 회원가입 API (register) | server | ✅ | 6db43b1 |
| 9.3 로그인 status 분기 + 세션 확장 | server | ✅ | 4fe4899 |
| 9.4 유저 관리 API (approve/reject/disable/enable) | server | ✅ | 04297ac |
| 9.5 리소스 소유권 스코프 (CRUD) | server | ✅ | b70cc5b |
| 9.6 조회 계열 스코프 (attempts/status/logs/SSE/meta) | server | ✅ | 5ca31cb |

전 작업 `server-worker` 도메인, 순차 실행 (모델→가입→로그인/세션→관리→스코프).

## 변경 파일

### Server (src)
- `apps/server/src/app/db/models.py` — `User` 모델 + `OciCredential`/`InstanceConfig`/`NotificationChannel` 에 `owner_id` FK
- `apps/server/alembic/versions/a1b2c3d4e5f6_multiuser_auth.py` — 무중단·멱등 마이그레이션
- `apps/server/src/app/services/auth.py` — AppSetting→User 테이블 전환 (register_user/authenticate→User/active_admin_count)
- `apps/server/src/app/api/auth.py` — register/setup wrapper/login status gate/me 확장
- `apps/server/src/app/api/users.py` — 신규 유저 관리 API
- `apps/server/src/app/api/deps.py` — require_login→User 반환, require_admin/is_admin 추가, 레거시 세션 하위호환
- `apps/server/src/app/api/{credentials,configs,channels}.py` — CRUD owner_id 스코프 + 동일 소유자 링크 강제
- `apps/server/src/app/api/{attempts,status,logs,meta}.py` — 조회 계열 owner 스코프
- `apps/server/src/app/main.py` — users 라우터 등록

### Server (tests)
- 신규: `tests/unit/db/test_user_migration.py`, `tests/api/test_auth_register.py`, `tests/api/test_users.py`, `tests/api/test_ownership_scope.py`, `tests/api/test_query_scope.py`, `tests/unit/api/test_deps_auth.py`
- 전환: `conftest.py` (admin_settings→register_user, make_user/login_as fixture), `test_auth.py`, `test_auth_setup.py`, `tests/unit/services/test_auth.py`, `tests/unit/db/test_models.py`, `test_configs.py`, `test_attempts.py`, `test_status.py`, `tests/unit/workers/test_config_task.py`, `tests/integration/test_poller_supervisor.py`, `tests/integration/test_restart_resume.py` (owner_id 부여 회귀 복구)

## 테스트 결과

- pytest: **293 passed**, 0 failed (baseline 240 → +53)
- 커버리지: **94%** (게이트 70%+ 충족)
- 임시 DB `alembic upgrade head` 정상 적용 (user 테이블 + owner_id NOT NULL 확인)
- 운영 DB 시나리오 검증: 기존 admin(AppSetting)+리소스 보유 DB → upgrade → User(admin/active) 생성 + AppSetting 키 삭제 + 전 리소스 owner 백필 + 멱등성 + 무admin 안전성

## 마이그레이션 (무중단·멱등)

리비전 `a1b2c3d4e5f6` (down_revision `1b9a876eab13`):
1. `user` 테이블 생성 (존재 시 skip)
2. `AppSetting.admin_username`/`admin_password_hash` → `User(role=admin, status=active)` 이전 + 키 삭제 (이미 동명 유저 존재 시 재사용 → 멱등)
3. owner_id 컬럼 nullable 추가 → admin id 로 백필 (batch_alter_table, SQLite 호환)
4. NULL 잔존 없을 때만 NOT NULL + FK 적용

운영 DB(기존 admin+리소스)에 한 번에 적용 가능. downgrade 지원 (키 파일 복원 비대상).

## API 계약 요약

### POST /api/auth/register (공개, rate limit 5/min/IP)
- 최초 유저 (테이블 비어있음):
  ```json
  201 {"username": "rootadmin", "role": "admin", "status": "active"}
  ```
  → 세션 쿠키 자동 발급 (auto-login)
- 이후 유저:
  ```json
  201 {"username": "member1", "role": "user", "status": "pending"}
  ```
  → 세션 미발급
- 중복: `409 {"error": {"code": "username_taken"}}`
- `/api/auth/setup` 은 register 위임 deprecated wrapper (하위호환 유지)

### POST /api/auth/login
- pending: `403 account_pending`, disabled: `403 account_disabled`, active 만 세션 발급
- 성공: `200 {"username", "role", "status"}` (세션 user_id/role 저장)

### GET /api/auth/me → `{"username", "role", "status"}`

### GET /api/users (admin 전용)
```json
[{"id": 1, "username": "admin", "role": "admin", "status": "active",
  "created_at": "...", "approved_at": "..."}]
```
- `POST /api/users/{id}/approve|reject|disable|enable`
- 마지막 active admin disable → `409 last_admin`
- disable 시 소유 config 전체 `enabled=False` (supervisor 자동 cancel)
- 비admin 접근 → `403 forbidden`, 미존재 → `404 user_not_found`

### 소유권 스코프 (PRD §6.3)
- credentials/configs/channels/attempts/status/logs/SSE/meta: 비admin 은 `owner_id == 본인` 만, admin 전체
- 타인 리소스 접근 → **404 은닉** (403 아님)
- config↔channel 링크: 미보유 채널 404, 소유자 불일치 → `422 owner_mismatch`

## 이슈 및 해결

- **owner_id NOT NULL 회귀**: User/owner_id 도입으로 직접 모델 INSERT 하던 다수 기존 테스트(워커/통합/CRUD seed)가 FK/NOT NULL 위반. 각 테스트 헬퍼에 owner User 시드 + owner_id 부여로 해결 (T3 성격, 전 스위트 green 복구).
- **setup 하위호환 의미 변경**: 기존 `/setup` 2회차 409 → 이제 일반 pending 가입(201). PRD Open Question #1 "register 통합" 방침에 맞춰 테스트 갱신.
- **레거시 세션**: Push 9 이전 `user`(username) 만 담긴 세션도 require_login 이 username→User 로 resolve (PRD §9.4 "재로그인 1회 허용" 범위 내). 비active 계정 세션은 즉시 무효화(401).
- ruff 미설치 환경 → 린트 게이트 생략 (pytest/커버리지 게이트로 검증).

## 새로 만든 스킬
- 없음 (반복 패턴 미발생 — 기존 fastapi-patterns/python-testing 스킬 범위 내)

## 후속 (Push 9 범위 외)
- Push 10: 웹 (가입/대기 화면, 유저 관리 페이지, 사이드바 role 분기, me 확장 Orval 재생성)
- Push 11: OCI 키 Fernet DB 암호화 + key_content 전환 + CORS 회귀 (Push 9 와 독립)
