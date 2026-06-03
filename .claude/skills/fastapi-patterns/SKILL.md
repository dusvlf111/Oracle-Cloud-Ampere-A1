---
name: fastapi-patterns
description: |
  본 프로젝트 FastAPI 서버의 라우터/SQLModel/Alembic/의존성 패턴. "FastAPI 엔드포인트 추가", "SQLModel 모델", "마이그레이션", "Depends 어떻게", "에러 표준" 등에서 트리거.
  서버는 외부 노출 차단, 모든 라우터 세션 인증, 응답 에러 표준 `{error: {code, message, details, request_id}}`.
---

# FastAPI Patterns

본 프로젝트 서버 코드 작성 시 따르는 패턴.

## 디렉토리 매핑

```
app/
├── main.py            # FastAPI 앱, lifespan, 미들웨어
├── config.py          # pydantic-settings
├── db/
│   ├── session.py     # 엔진/세션
│   └── models.py      # SQLModel
├── api/
│   ├── {도메인}.py    # APIRouter (prefix=/api/{도메인}, tags=[도메인])
│   └── deps.py        # Depends 모음, AppError
├── schemas/           # *Create/*Update/*Read Pydantic
├── services/
│   ├── crypto.py
│   ├── oci_client.py
│   ├── auth.py
│   └── notifier/
└── workers/
    ├── poller.py
    ├── config_task.py
    └── log_pruner.py
```

## 라우터 패턴

```python
# app/api/configs.py
from fastapi import APIRouter, Depends
from sqlmodel import Session, select
from app.api.deps import get_session, require_login, AppError
from app.db.models import InstanceConfig
from app.schemas.config import ConfigCreate, ConfigRead, ConfigUpdate

router = APIRouter(prefix="/api/configs", tags=["configs"])

@router.get("", response_model=list[ConfigRead])
def list_configs(session: Session = Depends(get_session), _=Depends(require_login)):
    return session.exec(select(InstanceConfig)).all()

@router.post("", response_model=ConfigRead, status_code=201)
def create_config(body: ConfigCreate, session: Session = Depends(get_session), _=Depends(require_login)):
    cfg = InstanceConfig(**body.model_dump(exclude={"channel_ids"}))
    session.add(cfg)
    session.flush()
    # 채널 링크
    for ch_id in body.channel_ids:
        session.add(ConfigChannelLink(config_id=cfg.id, channel_id=ch_id))
    session.commit()
    session.refresh(cfg)
    return cfg

@router.get("/{config_id}", response_model=ConfigRead)
def get_config(config_id: int, session: Session = Depends(get_session), _=Depends(require_login)):
    cfg = session.get(InstanceConfig, config_id)
    if not cfg:
        raise AppError("config_not_found", 404, f"InstanceConfig id={config_id} not found", {"config_id": config_id})
    return cfg
```

라우터를 `app/main.py` 에 `app.include_router(router)` 로 등록 + 태그는 Orval 폴더 분리에 사용.

## Pydantic 스키마 분리

```python
# app/schemas/config.py
from sqlmodel import SQLModel
class ConfigBase(SQLModel):
    name: str
    credential_id: int
    shape: str = "VM.Standard.A1.Flex"
    # ...

class ConfigCreate(ConfigBase):
    channel_ids: list[int] = []

class ConfigUpdate(SQLModel):
    enabled: bool | None = None
    # 부분 갱신 — 모든 필드 Optional

class ConfigRead(ConfigBase):
    id: int
    enabled: bool
    channel_ids: list[int]
    created_at: datetime
    updated_at: datetime
```

DB 모델 (`InstanceConfig`) 과 응답 모델 (`ConfigRead`) 을 분리해 sensitive 필드 / 계산 필드 제어.

## 의존성 (Depends)

```python
# app/api/deps.py
from sqlmodel import Session
from app.db.session import engine

def get_session():
    with Session(engine) as session:
        yield session

def require_login(request: Request):
    user = request.session.get("user")
    if not user:
        raise AppError("unauthorized", 401, "Login required", None)
    return user
```

세션은 generator 의존성 — 요청 끝나면 자동 close.

## 표준 에러

PRD §8 "표준 에러 응답" 의 `AppError` 패턴 사용. `raise AppError(code, status_code, message, details)`. 일반 `HTTPException` 대신 항상 `AppError` — 응답 스키마 통일.

## SQLModel + Alembic

```bash
# 새 마이그레이션 자동 생성
cd apps/server && alembic revision --autogenerate -m "add channel"

# 적용
alembic upgrade head

# 롤백 한 단계
alembic downgrade -1
```

- `alembic/env.py` 가 `from app.db.models import SQLModel; target_metadata = SQLModel.metadata` 로 모델 인식
- SQLite 컬럼 변경 제한 — `op.batch_alter_table()` 으로 감싸기

## SQLite 동시성

```python
# app/db/session.py
from sqlmodel import create_engine
engine = create_engine(
    settings.database_url,
    connect_args={"check_same_thread": False},
    pool_pre_ping=True,
)
# 마이그레이션 후 WAL
with engine.begin() as conn:
    conn.exec_driver_sql("PRAGMA journal_mode=WAL")
    conn.exec_driver_sql("PRAGMA synchronous=NORMAL")
    conn.exec_driver_sql("PRAGMA foreign_keys=ON")
```

## Lifespan + 워커

```python
# app/main.py
from contextlib import asynccontextmanager
from app.workers.poller import poller_supervisor

@asynccontextmanager
async def lifespan(app: FastAPI):
    task = asyncio.create_task(poller_supervisor())
    pruner = asyncio.create_task(log_pruner_loop())
    yield
    task.cancel()
    pruner.cancel()
    await asyncio.gather(task, pruner, return_exceptions=True)

app = FastAPI(lifespan=lifespan)
```

## 미들웨어 순서 (위 → 아래로 들어옴, 역순으로 나감)

1. `SessionMiddleware` (itsdangerous, `secret_key=settings.APP_SECRET`)
2. `RequestIdMiddleware` (ULID → `request.state.request_id` + 응답 헤더 `X-Request-Id`)
3. `CORSMiddleware` (`allow_origins=settings.cors_origins`, `allow_credentials=True`)
4. `SlowAPIMiddleware` (로그인 rate limit)

## 비동기 vs 동기 라우터

- DB IO 만: 동기 라우터 (`def`) + 동기 세션 — SQLAlchemy/SQLModel 친화
- OCI / HTTP 외부 호출 포함: 비동기 (`async def`) + `asyncio.to_thread(...)` (OCI sync SDK)
- 혼용 가능. FastAPI 가 동기 라우터를 thread pool 에서 실행

## 안티패턴

- 라우터 내부에서 직접 비즈니스 로직 구현 → `services/` 에 분리
- `HTTPException` 직접 사용 → `AppError` 통일
- DB 모델을 응답으로 직접 반환 (sensitive 필드 노출) → `*Read` 분리
- 세션을 함수 시작에서 열고 끝에서 닫기 → `Depends(get_session)` generator 사용
- `print()` 디버깅 → `logger = logging.getLogger(__name__); logger.info(...)` (LogEntry 자동 기록)
