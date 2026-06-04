# PRD: 다중 사용자 권한 분리 + 보안 강화 (v0.2)

> 상태: 초안 v0.1
> 작성일: 2026-06-04
> 기반: `.claude/tasks/prd.md` (v0.6) 의 운영 중 시스템 — 본 PRD 는 §3 비목표였던 "다중 사용자 없음"을 공식 철회하고 승인제 다중 사용자로 확장한다

---

## 1. 개요

현재 시스템은 **최초 가입자 1명 = 관리자** 단일 사용자 구조다 (PR #3 에서 env 방식에서 전환).
본 확장은 **일반 유저 회원가입 + 어드민 승인제**를 도입해 여러 사용자가 각자의 OCI
자격증명/설정/알림 채널을 격리된 상태로 운영할 수 있게 한다. 동시에 OCI private key
저장 방식을 파일에서 **DB 암호화 저장(Fernet)** 으로 전환해 보안을 강화한다.

## 2. 현황 (이미 구현됨 — 본 PRD 범위에서 제외/검증만)

| 항목 | 상태 | 비고 |
|---|---|---|
| Rate limiting (`slowapi`) | ✅ 구현 | 로그인/가입 IP 당 5회/분 + 연속 실패 10회 → 5분 차단, Redis storage 옵션(`REDIS_URL`) |
| CORS 허용 도메인 명시 | ✅ 구현 | `CORS_ORIGINS` env allow-list + `allow_credentials`, Next.js rewrites 프록시가 1차 방어선 |
| passphrase/채널 토큰 암호화 | ✅ 구현 | AES-256-GCM (`services/crypto.py`, `APP_SECRET` 키 도출) |
| OCI private key | ⚠️ 파일 저장 | `/data/keys/{id}.pem` chmod 600 — **본 PRD 에서 DB 암호화로 전환** |

→ 신규 회원가입 엔드포인트에 기존 rate limit 데코레이터를 동일 적용하는 것으로 1·2번 요구 충족.
CI 게이트에 CORS 미허용 Origin 거부 회귀 테스트 추가.

## 3. 목표 (Goals)

- **회원가입**: 누구나 가입 신청 가능 → `pending` 상태 → **어드민 승인 후에만 로그인 가능**
- **역할 분리**:
  - `admin` — 전체 유저의 자격증명/설정/채널/시도이력/로그 조회·관리, 유저 승인/거부/비활성화
  - `user` — **본인 소유 리소스만** CRUD/조회 (타인 리소스는 404 로 은닉)
- **소유권 모델**: 모든 도메인 리소스에 `owner_id` 도입, 기존 데이터는 admin 소유로 마이그레이션
- **OCI 키 DB 암호화**: private key PEM 을 Fernet 으로 암호화해 DB 저장, 파일 저장 제거
- 기존 단일 관리자(최초 가입자)는 자동으로 `admin` 역할 유지 — 무중단 마이그레이션

## 4. 비목표 (Non-goals)

- OAuth / 소셜 로그인 / 이메일 인증 (가입은 username+password 만)
- 비밀번호 재설정 플로우 (v0.3 — 어드민이 유저 비밀번호 초기화로 대체 검토)
- 조직/팀 단위 공유, 리소스 공동 소유
- 유저별 OCI 동시성 쿼터 차등 (전역 semaphore 정책 유지)
- 감사 로그 (audit trail) 전용 테이블 — `LogEntry` 로 충분

## 5. 데이터 모델 변경 (SQLModel + Alembic)

```python
class User(SQLModel, table=True):
    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)          # 3자+
    password_hash: str                                       # Argon2id
    role: str = Field(default="user", index=True)            # "admin" | "user"
    status: str = Field(default="pending", index=True)       # "pending" | "active" | "disabled"
    created_at: datetime
    approved_at: datetime | None = None
    approved_by: int | None = Field(default=None, foreign_key="user.id")
```

- **소유권 컬럼 추가** (4개 모델): `OciCredential.owner_id`, `InstanceConfig.owner_id`,
  `NotificationChannel.owner_id` — `Field(foreign_key="user.id", index=True)`.
  `Attempt`/`LogEntry` 는 config 경유로 소유자 판정 (컬럼 추가 없음 — join 필터)
- **마이그레이션 전략** (무중단):
  1. `user` 테이블 생성
  2. 기존 `AppSetting` 의 `admin_username`/`admin_password_hash` → `User(role=admin, status=active)` 행으로 이전 후 AppSetting 키 삭제
  3. 기존 모든 리소스의 `owner_id` ← 그 admin user id 로 백필
  4. `owner_id` NOT NULL 제약 적용
- 채널 ↔ config 연결은 **같은 소유자끼리만** 허용 (검증)

## 6. 인증/권한 흐름

### 6.1 회원가입 (신규)
- `POST /api/auth/register {username, password}` (공개, **rate limit 5/min/IP** — 기존 데코레이터 재사용)
  - 최초 유저(테이블 비어있음) → `role=admin, status=active` 즉시 활성 + 자동 로그인 (기존 `setup` 동작 흡수 — `/api/auth/setup` 은 register 로 통합하고 하위호환 유지 또는 제거)
  - 이후 유저 → `role=user, status=pending` → 201 `{status: "pending"}` (세션 미발급)
  - username 중복 → 409 `username_taken`
- `pending`/`disabled` 유저 로그인 시도 → 403 `account_pending` / `account_disabled` (메시지로 구분)

### 6.2 어드민 유저 관리 (신규)
| Method | Path | 설명 |
|---|---|---|
| GET | `/api/users` | 유저 목록 (admin 전용) — id/username/role/status/created_at |
| POST | `/api/users/{id}/approve` | pending → active |
| POST | `/api/users/{id}/reject` | pending 유저 삭제 |
| POST | `/api/users/{id}/disable` | active → disabled (즉시 세션 무효화, 해당 유저 config 전체 자동 비활성화) |
| POST | `/api/users/{id}/enable` | disabled → active |

- admin 본인 비활성화 금지 (마지막 admin 보호)
- (옵션) 가입 신청 시 admin 알림 채널로 통지 — admin 소유 채널 중 `notify_admin=true` 표시된 채널

### 6.3 권한 적용 (deps)
- `require_login` → 세션에 `user_id`/`role` 저장 (기존 username 만 → 확장)
- `require_admin` 신규 dependency
- **스코프 규칙**: 모든 목록/단건 조회·수정·삭제에 `owner_id == current_user.id` 필터
  (admin 은 전체). 타인 리소스 접근 → **404** (403 아님 — 존재 은닉)
- 로그(`GET /api/logs`, SSE): user 는 본인 config_id 집합으로 서버측 필터, admin 전체
- 시도이력/폴링현황: 동일 스코프
- 워커: 변경 없음 (시스템 전역 폴링 — disabled 유저의 config 는 비활성화돼 있으므로 자연 제외)

## 7. OCI Private Key DB 암호화 (Fernet)

- `OciCredential.private_key_path` → **`private_key_enc: str`** (Fernet 토큰) 교체
- `cryptography.fernet.Fernet` — 키는 `APP_SECRET` 에서 HKDF 도출 (기존 AES-GCM 유틸과 별도 함수, 같은 모듈)
  - 참고: 기존 `crypto.py` 의 AES-256-GCM 과 병존 — 신규 필드만 Fernet (요구사항 명시), 기존 passphrase/채널 필드는 점진 통일 (open question #3)
- OCI SDK 호출 시 파일 미사용: oci config dict 에 `key_content` 로 복호화된 PEM 을 메모리 전달 (SDK 공식 지원 — 디스크에 평문 키가 닿지 않음)
- **마이그레이션**: 기존 `/data/keys/*.pem` 파일 → 읽어서 암호화 후 DB 저장 → 파일 삭제. 실패 시 롤백 안전 (파일 우선 삭제 금지)
- API 응답에는 키 관련 어떤 형태도 노출 금지 (기존 마스킹 정책 유지)
- `data/keys` 볼륨 의존 제거 → compose/README 갱신

## 8. 웹 (FSD)

| 항목 | slice |
|---|---|
| 회원가입 폼 (가입 신청 → "승인 대기 중" 안내 화면) | `features/auth-register` (기존 auth-setup 확장/대체) |
| 로그인 시 pending/disabled 에러 안내 | `features/auth-login` 수정 |
| 유저 관리 페이지 — 목록/승인/거부/비활성 (admin 전용 메뉴) | `pages/users` + `features/user-approve` + `entities/user` |
| admin 전용 메뉴 가드 (sidebar 에 role 분기) | `widgets/sidebar` 수정 |
| "전체 보기" 토글 (admin 이 특정 유저 리소스 필터) | `features/owner-filter` (v0.2 옵션) |
| 본인 데이터만 보이는 것은 서버 스코프로 자동 — 웹 변경 최소 | — |

- 세션 `GET /api/auth/me` 응답 확장: `{username, role, status}` — Orval 재생성
- 미들웨어: 기존 세션 쿠키 가드 유지 (role 분기는 서버 + 클라이언트 메뉴 레벨)

## 9. 비기능 요구사항

- **테스트 의무** (기존 정책): 모든 commit 에 pytest/vitest 동봉
  - 핵심 시나리오: 가입→pending 로그인 거부→승인→로그인 성공, user A 가 user B 리소스 접근 시 404, admin 전체 조회, 마지막 admin 비활성화 거부, 키 마이그레이션 라운드트립, register rate limit 429
- 기존 240+ pytest / 175+ vitest 회귀 금지
- 마이그레이션은 단방향 안전 (downgrade 시 키 파일 복원은 비지원 — 백업 안내)
- 세션 하위호환: 배포 직후 기존 admin 세션은 재로그인 1회 요구 허용

## 10. Push 계획 (task-maker 분해용)

| Push | 범위 | 비고 |
|---|---|---|
| Push 9 | User 모델 + 마이그레이션(AppSetting→User, owner 백필) + register/승인 API + require_admin + 리소스 스코프 적용 | 서버 |
| Push 10 | 웹 — 가입/대기 화면, 유저 관리 페이지, 사이드바 role 분기, me 확장 | 웹 (Push 9 의존) |
| Push 11 | OCI 키 Fernet DB 암호화 + key_content 전환 + 파일 마이그레이션 + CORS 회귀 테스트 | 서버, Push 9 와 독립 가능 |

## 11. Open Questions

| # | 질문 | 기본값 제안 |
|---|---|---|
| 1 | `/api/auth/setup` 하위호환 | register 로 통합, setup 은 1~2 릴리스 deprecated 유지 후 제거 |
| 2 | 가입 신청 어드민 통지 | v0.2 옵션 (admin 채널 재사용) — MVP 는 유저 관리 페이지 뱃지만 |
| 3 | 암호화 방식 통일 | 신규 키는 Fernet (요구사항), 기존 AES-GCM 필드는 차기 통일 |
| 4 | disabled 유저의 실행 중 폴링 | disable 시 해당 유저 config 전체 enabled=False 처리 (supervisor 가 자동 cancel) |
| 5 | user 의 채널 공유 | 금지 — 소유자 격리 원칙 유지 |

## 12. 성공 기준

- 신규 가입자는 승인 전 로그인 불가 (403 + 안내), 승인 후 로그인 가능
- user A 로그인 시 B 의 credential/config/channel/attempt/log 가 목록·단건·SSE 어디에도 안 보임 (404)
- admin 은 유저 관리 페이지에서 승인/거부/비활성 수행 + 전체 리소스/로그 조회
- DB 파일을 열어도 OCI private key 평문 확인 불가 (Fernet 토큰만), `/data/keys` 디렉토리 불필요
- `pnpm test` 전체 통과 (서버 70%+/웹 50%+ 커버리지 게이트 유지), 기존 기능 회귀 0
