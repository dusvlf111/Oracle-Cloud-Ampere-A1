# Tasks: 다중 사용자 권한 분리 - Push 11

> PRD: `.claude/tasks/todo/prd-multiuser-auth.md` (§7 OCI Private Key DB 암호화)
> Push 범위: 서버 — OCI private key 를 파일 저장 → Fernet DB 암호화로 전환, `key_content` 메모리 전달, 파일 마이그레이션, CORS 회귀 테스트
> 선행 조건: 없음 (Push 9 와 독립 — 단 9 가 먼저 머지됐다면 그 위에서 분기)
> 상태: 🔲 진행 중

---

### 관련 파일

- `apps/server/src/app/services/crypto.py` - Fernet 유틸 (`APP_SECRET` HKDF 도출)
- `apps/server/src/app/db/models.py` - `private_key_path` → `private_key_enc`
- `apps/server/alembic/versions/` - 파일 → DB 이전 마이그레이션
- `apps/server/src/app/services/oci_client.py` - `key_content` 전달
- `apps/server/src/app/api/credentials.py` - 업로드 → 암호화 저장
- `docker-compose.yml`, `README.md`, `.env.example` - keys 볼륨 의존 제거
- `apps/server/tests/unit/services/test_crypto_fernet.py`, `tests/api/test_cors.py`

---

### 에이전트 실행 전략 (push-lead)

전 작업 `server-worker` 담당, 순차 (유틸 → 모델/마이그레이션 → 호출부 → 정리).

| 작업 | 의존성 |
|---|---|
| 11.1 → 11.2 → 11.3 → 11.4 | 순차 |

- **마이그레이션 안전 원칙**: 파일 읽기→암호화→DB 저장이 전부 성공한 뒤에만 파일 삭제. 파일 누락 credential 은 경고 로그 + 건너뜀 (verify 실패로 사용자가 재업로드)
- 평문 키는 어떤 로그/응답/디스크에도 노출 금지 (메모리 복호화 → `key_content` 직행)
- 각 T2 커밋 직전 `test-runner` 검증, 11.4.T2 에서 전체 스위트 게이트
- 참조 스킬: `fastapi-patterns`, `python-testing`, `oci-sdk`

---

## 작업

- [ ] 11.0 OCI 키 DB 암호화 (Push 11)
    - [x] 11.1 Fernet 유틸 — `crypto.py` 에 `fernet_encrypt/fernet_decrypt` (키: `APP_SECRET` 에서 HKDF-SHA256 도출, 기존 AES-GCM 와 병존), 타입힌트+docstring
        - [x] 11.1.T1 pytest 테스트 작성 — 라운드트립, 변조 토큰 거부, AES-GCM 유틸 회귀
        - [x] 11.1.T2 `uv run pytest -q tests/unit/services/test_crypto_fernet.py tests/unit/services/test_crypto.py` 실행 및 검증
    - [x] 11.2 모델 전환 + 파일 마이그레이션 — `OciCredential.private_key_path` → `private_key_enc: str`, Alembic data migration: 기존 `/data/keys/{id}.pem` 읽기 → Fernet 암호화 → DB 저장 → **성공분만** 파일 삭제 (누락 파일은 경고 + 빈 값 → verify 실패 유도), downgrade 는 비지원 명시
        - [x] 11.2.T1 pytest 테스트 작성 — 마이그레이션 시나리오 (키 파일 있는 credential → upgrade → enc 저장+파일 삭제, 파일 누락 → 경고+스킵)
        - [x] 11.2.T2 `uv run pytest -q tests/unit/db/` + 임시 DB `alembic upgrade head` 실행 및 검증
    - [x] 11.3 호출부 전환 — `oci_client.build_config` 가 `key_content` (복호화 PEM 문자열) 사용 (파일 경로 제거), `api/credentials.py` 업로드 → Fernet 암호화 저장 + PUT 재업로드 동일 처리, 삭제 시 파일 정리 로직 제거, `keys_dir` 설정 deprecated
        - [x] 11.3.T1 pytest 테스트 작성 — 생성→DB 에 Fernet 토큰만 (평문/파일 없음), verify/launch 가 key_content 로 동작 (oci mock), PUT 키 재업로드/유지, 응답 무노출
        - [x] 11.3.T2 `uv run pytest -q tests/api/test_credentials.py tests/unit/services/test_oci_client.py tests/unit/workers/` 실행 및 검증
    - [ ] 11.4 정리 + CORS 회귀 — compose 의 keys 볼륨 안내 주석/README/.env.example 갱신 (`/data` 는 SQLite 만), `tests/api/test_cors.py` 신규 (허용 Origin 통과 / 미허용 Origin preflight 거부), OSS 표 변경 없음 확인
        - [ ] 11.4.T1 pytest 테스트 작성 — CORS 허용/거부, compose 정적 검증 (`scripts/verify-compose.mjs`) 통과 유지
        - [ ] 11.4.T2 `uv run pytest -q` 전체 + `node scripts/verify-compose.mjs` + 루트 `pnpm test` 실행 및 검증
