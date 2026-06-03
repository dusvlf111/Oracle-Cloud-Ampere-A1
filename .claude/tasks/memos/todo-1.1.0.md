# OCI Bot TODO

## 1순위 — 개발 시작 전 필수

### 인증 / 권한
- [ ] 유저 권한 분리
  - 일반 유저 회원가입 시 어드민 승인 후 로그인 가능
  - 어드민: 전체 유저 작업 및 로그 확인 가능
  - 일반 유저: 본인 것만 조회 가능
- [ ] Rate limiting — 로그인 브루트포스 방지 (`slowapi`)
- [ ] CORS 설정 — FastAPI 허용 도메인 명시
- [ ] OCI 키 암호화 — Fernet으로 DB 저장 시 암호화 필수

### 봇 안정성
- [ ] 서버 startup 시 실행 중인 job 자동 복구
- [ ] 봇 최대 시도 횟수 / 타임아웃 설정
- [ ] ntfy 알림 — 인스턴스 생성 성공/실패 푸시

### 개발 환경
- [ ] `.env.example` 작성 — 환경변수 문서화
- [ ] `loguru` 도입 — Python 로그 포맷
- [ ] `pre-commit hook` — lint/format 자동화

---

## 2순위 — 배포 전

### 인프라
- [ ] 헬스체크 엔드포인트 `/health` — Docker 재시작 조건
- [ ] Alembic startup 자동 실행 — 배포 시 스키마 자동 동기화
- [ ] DB 백업 스크립트 — cron으로 주기적 SQLite 파일 백업
- [ ] Docker Compose 에러 트래킹 / 애널리틱스 세팅
  - Glitchtip — 에러 트래킹
  - Umami — 애널리틱스

### API 동기화
- [ ] Orval — FastAPI `/openapi.json` 기반 Next.js 클라이언트 자동 생성
- [ ] `dev` 스크립트에 orval 자동 실행 연결

---

## 3순위 — 안정화 후

### 테스트 / CI
- [ ] Playwright E2E 테스트 도입
- [ ] GitHub Actions 세팅
  - lint / test / build 자동화
  - main 브랜치 푸시 시 자동 배포

### 운영
- [ ] 무중단 배포 Docker Compose 세팅
- [ ] PostgreSQL 전환 (동시 접속 늘어날 때)
- [ ] Celery + Redis 전환 (서비스 규모 커질 때)

---

## 확정 스택

```
Next.js        UI
FastAPI        API 서버
SQLite         DB (→ PostgreSQL)
SQLAlchemy     ORM
Alembic        DB 마이그레이션
Orval          API 클라이언트 자동생성
Fernet         OCI 키 암호화
loguru         로그
Sentry         에러 모니터링
Glitchtip      에러 트래킹 (self-hosted)
Umami          애널리틱스 (self-hosted)
ntfy           푸시 알림
```