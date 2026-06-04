# Tasks: 다중 사용자 권한 분리 - Push 9

> PRD: `.claude/tasks/todo/prd-multiuser-auth.md` (§5 데이터 모델, §6 인증/권한 흐름)
> Push 범위: 서버 — User 모델 + 무중단 마이그레이션, 승인제 회원가입, 유저 관리 API, 리소스 소유권 스코프
> 상태: 🔲 진행 중

---

### 관련 파일

- `apps/server/src/app/db/models.py` - `User` 모델 + `owner_id` 컬럼 3종
- `apps/server/alembic/versions/` - User 생성 + AppSetting→User 이전 + owner 백필
- `apps/server/src/app/services/auth.py` - DB User 기반 인증으로 전환
- `apps/server/src/app/api/auth.py` - register / 로그인 status 분기 / me 확장
- `apps/server/src/app/api/users.py` - 유저 관리 (admin 전용)
- `apps/server/src/app/api/deps.py` - `require_admin`, 세션 user_id/role
- `apps/server/src/app/api/{credentials,configs,channels,attempts,status,logs}.py` - 소유권 스코프
- `apps/server/tests/api/test_users.py`, `test_auth_register.py`, `test_ownership_scope.py`

---

### 에이전트 실행 전략 (push-lead)

전 작업 `server-worker` 담당, 순차 실행 (모델 → 인증 → 관리 API → 스코프 순서로 의존).

| 작업 | 의존성 |
|---|---|
| 9.1 → 9.2 → 9.3 → 9.4 | 순차 (User 모델 → 가입 → 로그인/세션 → 관리) |
| 9.5 → 9.6 | 9.3 (세션 user_id 필요), 9.5 와 9.6 은 파일 분리돼 있으나 deps 공유 — 순차 권장 |

- 마이그레이션은 멱등·무중단: 기존 admin (AppSetting) 자동 이전, 기존 리소스 owner 백필 — 운영 DB 에서 한 번에 적용 가능해야 함
- conftest 의 `authed_client`/`admin_settings` fixture 전환은 9.2 에서 일괄 — 이후 커밋 회귀 기준
- 각 T2 커밋 직전 `test-runner` 검증, 9.6.T2 에서 전체 스위트 + 커버리지 게이트
- 참조 스킬: `fastapi-patterns`, `python-testing`

---

## 작업

- [ ] 9.0 서버 권한 분리 (Push 9)
    - [x] 9.1 `User` 모델 + 무중단 마이그레이션 — User 테이블 (username unique/role/status/approved_at/approved_by), `OciCredential`/`InstanceConfig`/`NotificationChannel` 에 `owner_id` FK, Alembic: ① user 생성 ② AppSetting `admin_username`/`admin_password_hash` → `User(role=admin, status=active)` 이전 + 키 삭제 ③ 기존 리소스 owner 백필 ④ NOT NULL 적용
        - [x] 9.1.T1 pytest 테스트 작성 — 마이그레이션 시나리오 (기존 admin+리소스 있는 DB → upgrade → User 행/백필 검증), 모델 관계
        - [x] 9.1.T2 `uv run pytest -q tests/unit/db/` + 임시 DB `alembic upgrade head` 실행 및 검증
    - [x] 9.2 회원가입 API — `POST /api/auth/register` (rate limit 5/min/IP 재사용): 최초 유저 → admin/active + 자동 로그인 (기존 setup 동작 흡수, `/api/auth/setup` 은 register 위임 wrapper 로 deprecated 유지), 이후 → user/pending 201 세션 미발급, 중복 409 `username_taken`. `services/auth.py` 를 AppSetting → User 테이블 기반으로 전환, conftest fixture 일괄 전환
        - [x] 9.2.T1 pytest 테스트 작성 — 최초 가입=admin 자동로그인, 2번째 가입=pending 무세션, 중복 409, rate limit 429, setup 하위호환
        - [x] 9.2.T2 `uv run pytest -q tests/api/test_auth_register.py tests/api/test_auth_setup.py` 실행 및 검증
    - [x] 9.3 로그인 status 분기 + 세션 확장 — pending → 403 `account_pending`, disabled → 403 `account_disabled`, active 만 세션 발급. 세션에 `user_id`/`role` 저장, `GET /api/auth/me` → `{username, role, status}`, `require_login` 이 User 객체 반환하도록 확장
        - [x] 9.3.T1 pytest 테스트 작성 — pending/disabled 로그인 403 (코드 구분), active 성공, me 응답 role 포함, 기존 세션 하위호환 (재로그인 요구)
        - [x] 9.3.T2 `uv run pytest -q tests/api/test_auth.py` 실행 및 검증
    - [x] 9.4 유저 관리 API — `api/users.py` (admin 전용): `GET /api/users`, `POST /{id}/approve|reject|disable|enable`. 마지막 admin disable 금지 409, disable 시 해당 유저 세션 무효화 기반 마련 + 소유 config 전체 `enabled=False` (supervisor 자동 cancel), reject 는 pending 만 삭제 가능
        - [x] 9.4.T1 pytest 테스트 작성 — 승인→로그인 가능, 거부→삭제, disable→config 비활성+로그인 차단, enable 복구, 마지막 admin 보호, user 권한으로 접근 시 403/404
        - [x] 9.4.T2 `uv run pytest -q tests/api/test_users.py` 실행 및 검증
    - [x] 9.5 리소스 소유권 스코프 (CRUD) — `require_admin` dependency, credentials/configs/channels 의 목록·단건·수정·삭제에 `owner_id` 필터 (admin 전체), 생성 시 owner 자동 지정, 타인 리소스 → 404 은닉, config↔channel 연결은 동일 소유자만 422
        - [x] 9.5.T1 pytest 테스트 작성 — `tests/api/test_ownership_scope.py`: user A/B 교차 접근 404, admin 전체 조회, 타 소유자 채널 연결 거부
        - [x] 9.5.T2 `uv run pytest -q tests/api/test_ownership_scope.py tests/api/test_credentials.py tests/api/test_configs.py tests/api/test_channels.py` 실행 및 검증
    - [ ] 9.6 조회 계열 스코프 — attempts/status(polling)/logs/SSE: user 는 본인 config_id 집합 기준 서버측 필터, admin 전체. meta 조회는 본인 credential 만
        - [ ] 9.6.T1 pytest 테스트 작성 — attempts/폴링현황/logs/SSE 스코프 (A 의 로그가 B 에게 안 보임), meta credential 404
        - [ ] 9.6.T2 `uv run pytest -q` 전체 + 커버리지 70%+ 게이트 실행 및 검증
