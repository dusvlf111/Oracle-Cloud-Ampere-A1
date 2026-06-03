---
name: python-testing
description: |
  본 프로젝트 서버 테스트 (pytest). "pytest 테스트 추가", "fixture", "httpx mock", "OCI mock", "비동기 테스트", "커버리지" 등에서 트리거.
  스택: pytest + pytest-asyncio + pytest-cov + httpx ASGITransport + pytest-httpx + polyfactory. 모든 commit 단위 작업에 테스트 동봉 필수.
---

# Python Testing — pytest

## 디렉토리

```
apps/server/tests/
├── conftest.py           # 공용 fixture
├── unit/                 # 순수 함수, 작은 모듈
├── api/                  # FastAPI 엔드포인트
└── integration/          # 여러 모듈 결합 시나리오
```

## conftest.py 표준 fixture

```python
import pytest
import asyncio
from httpx import AsyncClient, ASGITransport
from sqlmodel import Session, SQLModel, create_engine
from sqlalchemy.pool import StaticPool
from app.main import app
from app.db.session import get_session_dep

@pytest.fixture
def engine():
    eng = create_engine(
        "sqlite:///:memory:",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    SQLModel.metadata.create_all(eng)
    yield eng
    eng.dispose()

@pytest.fixture
def session(engine):
    with Session(engine) as s:
        yield s

@pytest.fixture
async def client(engine):
    def _get_session():
        with Session(engine) as s:
            yield s
    app.dependency_overrides[get_session_dep] = _get_session
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as c:
        yield c
    app.dependency_overrides.clear()

@pytest.fixture
async def authed_client(client):
    await client.post("/api/auth/login", json={"username": "admin", "password": "test"})
    yield client
```

## pyproject.toml 설정

```toml
[tool.pytest.ini_options]
asyncio_mode = "auto"
addopts = "-ra -q --strict-markers --strict-config"
markers = ["slow: marks tests as slow"]

[tool.coverage.run]
branch = true
source = ["app"]
omit = ["app/cli.py", "app/__main__.py"]

[tool.coverage.report]
fail_under = 70
exclude_lines = ["pragma: no cover", "raise NotImplementedError"]
```

## 패턴 — 동기 함수

```python
def test_encrypt_decrypt_roundtrip():
    cipher = encrypt("hello", key)
    assert decrypt(cipher, key) == "hello"
```

## 패턴 — 비동기 함수

```python
async def test_ntfy_send_success(httpx_mock):
    httpx_mock.add_response(url="https://ntfy.supabin.com/topic", status_code=200)
    await send_ntfy({"server_url": "https://ntfy.supabin.com", "topic": "topic"}, payload)
    req = httpx_mock.get_request()
    assert req.headers["Title"] == payload.title
```

## 패턴 — API 엔드포인트

```python
async def test_create_config_requires_auth(client):
    r = await client.post("/api/configs", json={...})
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "unauthorized"

async def test_create_config_success(authed_client, session):
    r = await authed_client.post("/api/configs", json={
        "name": "test", "credential_id": 1, "image_ocid": "...", "subnet_ocid": "...",
        "availability_domain": "AD-1", "ssh_public_key": "ssh-ed25519 ..."
    })
    assert r.status_code == 201
    assert r.json()["enabled"] is True
```

## 패턴 — OCI SDK 모킹

```python
from unittest.mock import patch, MagicMock

async def test_config_task_handles_out_of_capacity(session):
    fake_client = MagicMock()
    fake_client.launch_instance.side_effect = oci.exceptions.ServiceError(
        status=500, code="InternalError", headers={}, message="Out of host capacity"
    )
    with patch("app.services.oci_client.build_client", return_value=fake_client):
        await run_one_attempt(config_id=1, session=session)
    attempt = session.exec(select(Attempt)).first()
    assert attempt.status == "out_of_capacity"
```

## 외부 호출 차단 (httpx)

```python
# pytest-httpx 가 자동 가로채기. 등록 안 한 호출은 실패.
@pytest.fixture(autouse=True)
def block_external_http(httpx_mock):
    yield   # 테스트가 등록 안 한 URL 호출 시 RuntimeError
```

## 팩토리 (polyfactory)

```python
from polyfactory.factories.sqlmodel_factory import SQLModelFactory
from app.db.models import InstanceConfig

class ConfigFactory(SQLModelFactory[InstanceConfig]):
    __set_as_default_factory_for_type__ = True
    __random_seed__ = 42

cfg = ConfigFactory.build()  # 랜덤이지만 결정적
```

## 실행

```bash
pytest -q                                   # 빠른 실행
pytest -q -k "config and not slow"          # 필터링
pytest --cov=app --cov-report=term-missing  # 커버리지
pytest tests/api/test_configs.py::test_create_config_success -xvs  # 단일 + 상세
```

## 커버리지 목표

- 전체 70%+
- `services/` `workers/` 80%+
- API 라우터: smoke + 주요 분기 + 401/422/404
- 마이그레이션, CLI 헬퍼는 제외

## 안티패턴

- 진짜 OCI/Discord/ntfy 호출 → 절대 금지 (`httpx_mock` 또는 `oci_mock`)
- 진짜 파일 시스템 쓰기 → `tmp_path` fixture
- 진짜 시간 의존 → `freezegun` 또는 `monkeypatch.setattr(time, "time", ...)`
- DB autouse 픽스처가 commit 한 후 미정리 → 항상 트랜잭션 롤백 또는 in-memory 새로 생성
- `time.sleep()` 로 비동기 대기 → `await asyncio.sleep(0)` 또는 이벤트 사용
- 한 테스트가 여러 endpoint 호출 → 분리 (한 테스트 = 한 의도)
