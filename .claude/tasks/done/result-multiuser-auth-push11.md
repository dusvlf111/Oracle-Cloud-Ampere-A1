# 결과보고서: tasks-multiuser-auth-push11

> 완료일: 2026-06-04
> 브랜치: `push11-key-encryption` (base: origin/main @ 68382ed)
> 범위: 서버 — OCI private key 를 파일 저장(`/data/keys/{id}.pem`) → Fernet DB 암호화(`private_key_enc`)로 전환, `key_content` 인메모리 전달, 파일→DB 마이그레이션, CORS 회귀 테스트
> PRD: §7 OCI Private Key DB 암호화 (multiuser-auth 3개 Push 전부 완료 → PRD done/ 이동)

## 구현 요약

| 작업 | 도메인 | 상태 | 커밋 |
|---|---|---|---|
| 11.1 Fernet 유틸 (`fernet_encrypt`/`fernet_decrypt`, HKDF 도출 키) | server | ✅ | 62a1e5f |
| 11.2 모델 전환 + Alembic 파일→DB 데이터 마이그레이션 | server | ✅ | 3e7f57d |
| 11.3 호출부 전환 (`build_config` key_content, credentials/meta/worker) | server | ✅ | 24c3992 |
| 11.4 정리 + CORS 미들웨어 + 회귀 테스트 | server | ✅ | a1fa98d |

전 작업 단일 에이전트 순차 직접 구현 (Task 도구 미사용). 각 하위 작업 완료 직후 + Push 완료 시 ntfy 알림 전송 완료.

## 변경 파일

### Server (src)
- `apps/server/src/app/services/crypto.py` — `fernet_encrypt`/`fernet_decrypt` 추가 (AES-GCM 와 병존, HKDF 컨텍스트 분리 `_HKDF_INFO_FERNET`)
- `apps/server/src/app/db/models.py` — `OciCredential.private_key_path` → `private_key_enc: str`
- `apps/server/alembic/versions/b2c3d4e5f6a7_key_db_encryption.py` — 신규 데이터 마이그레이션 (down_revision: `a1b2c3d4e5f6`)
- `apps/server/src/app/services/oci_client.py` — `build_config(..., key_content=...)` (`key_file` 제거), 비동기 래퍼 `key_content` 화
- `apps/server/src/app/api/credentials.py` — 업로드 → 메모리 암호화 저장, PUT 재업로드 재암호화/유지, verify 가 `key_content` 사용, delete 파일 정리 제거, 파일 I/O 전부 삭제
- `apps/server/src/app/api/meta.py` — `_cred_dict` 가 복호화 PEM(`key_content`) 전달
- `apps/server/src/app/workers/config_task.py` — launch 경로 `key_content` 인메모리 복호화
- `apps/server/src/app/config.py` — `keys_dir` deprecated 주석
- `apps/server/src/app/main.py` — `CORSMiddleware` 추가 (`cors_origins` allow-list)

### Server (tests)
- `apps/server/tests/unit/services/test_crypto_fernet.py` (신규, 6) — 라운드트립/변조/말포름드/키 독립성/APP_SECRET 부재
- `apps/server/tests/unit/db/test_key_encryption_migration.py` (신규, 4) — 파일 있음→암호화+삭제, 누락→경고+빈값, 컬럼 드롭/NOT NULL, downgrade 비지원
- `apps/server/tests/api/test_cors.py` (신규, 4) — 허용 Origin 통과(GET/preflight), 미허용 Origin 헤더 부재/preflight 거부
- `apps/server/tests/api/test_credentials.py` — 파일 단언 → DB enc 단언, verify key_content 검증, 누락키→ok:false, 무노출 단언
- `apps/server/tests/unit/services/test_oci_client.py` — `key_content` 단언 + missing key KeyError
- `apps/server/tests/unit/workers/test_config_task.py` — 픽스처가 PEM Fernet 암호화 저장
- `apps/server/tests/api/test_meta.py`, `test_ownership_scope.py`, `test_query_scope.py` — 제거된 `app.api.credentials.get_settings` 패치 정리 + fernet 캐시 클리어
- `tests/unit/db/test_log_entry.py` — 비가역 마이그레이션 경계 존중 (downgrade 대상 `a1b2c3d4e5f6`)
- `test_status.py`/`test_attempts.py`/`test_configs.py`/`test_users.py`/integration — `private_key_path` → `private_key_enc` 플레이스홀더

### 루트
- `docker-compose.yml` — `./data:/data` 볼륨 주석 (SQLite 전용, keys 디렉토리 불필요)
- `.env.example` — `KEYS_DIR` 미사용 안내
- `README.md` — KEYS_DIR 안내 갱신, OSS 표 cryptography 항목에 Fernet 명시
- `package.json` — `dev:server` 의 `mkdir -p data/keys` → `mkdir -p data`

## 테스트 결과 (11.4.T2 전체 게이트)

- pytest: **311 passed** (baseline 293 → +18 신규: crypto_fernet 6 / key_migration 4 / cors 4 / credentials·oci_client 추가 4)
- vitest: **198 passed** (45 files) — 회귀 없음
- `node scripts/verify-compose.mjs`: **OK** (server 호스트 미노출 / web :3000 / depends_on healthy 유지)
- 임시 DB `alembic upgrade head`: **성공** (`7c268f67372f → … → b2c3d4e5f6a7`)

## 마이그레이션 안전성 검증

- **성공분만 삭제**: `b2c3d4e5f6a7.upgrade()` 는 PEM 읽기 → Fernet 암호화 → `private_key_enc` UPDATE 커밋 **후**에만 `path.unlink()` 호출. 중단 시 파일 보존 + 재실행 시 `existing_enc` 비어있는 행만 재처리(멱등). 테스트 `test_migration_encrypts_present_key_and_deletes_file` 가 암복호화 라운드트립 + 파일 삭제를 검증.
- **누락 파일 처리**: 키 파일 부재 시 WARNING 로그 + `private_key_enc=''` 저장(데이터 날조 없음, 크래시 없음). verify 경로에서 빈 PEM → `build_config` KeyError → `{ok:false}` 수렴. 테스트 `test_migration_missing_file_warns_and_stores_empty` + `test_verify_missing_key_converges_to_ok_false` 가 검증.
- **평문 무노출**: 평문 PEM 은 업로드/마이그레이션/verify/launch 모두 지역 변수(`content`/`pem`/`key_content`)에만 존재 — 로그·응답·디스크 어디에도 기록 안 함. 응답 스키마(`CredentialRead`)에 키 필드 자체가 없고, `test_create_encrypts_key_to_db_and_masks` 가 응답 무노출 + 저장값이 평문이 아님을 단언.
- **비가역성 명시**: `downgrade()` 는 `NotImplementedError` (평문 파일 삭제로 복원 불가). `test_downgrade_is_unsupported` 가 검증, `test_log_entry` 다운체인 테스트는 경계(`a1b2c3d4e5f6`)까지만 수행하도록 조정.
- **도메인 분리**: Fernet 키는 `_HKDF_INFO_FERNET` 컨텍스트로 별도 도출 → AES-GCM 키와 재사용 없음 (`test_fernet_and_aesgcm_keys_are_independent` 검증).

## 새로 만든 스킬

- 없음. (반복 패턴 — Fernet/마이그레이션 안전성 — 은 기존 `python-testing`/`fastapi-patterns` 범위 내, 신규 추출 불필요)

## OSS 도입

- 신규 OSS 없음. `cryptography` (이미 의존성)의 `Fernet` 모듈만 추가 사용 → `oss-selection` 체크리스트 비해당. README OSS 표 설명만 보강.

## 이슈 및 특이사항

- main.py 에 CORSMiddleware 가 **부재**했음(설정 `cors_origins` 만 존재) — 11.4 에서 정식 추가하며 회귀 테스트 동봉. allow-list 기반 + credentials 허용.
- `test_cors.py` 는 import-time CORS 설정 의존을 피하려 `importlib.reload(app.main)` 로 격리 후 teardown 복원.
- Alembic env 의 `fileConfig()` 가 로거를 비활성화하여 마이그레이션 WARNING 캡처가 어려움 — 테스트에서 `logging.config.fileConfig` 를 no-op 패치하여 안정적으로 검증.
- git push 미실행 (지시사항 준수). 4개 커밋 `push11-key-encryption` 브랜치 로컬 보관.
