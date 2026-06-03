# syntax=docker/dockerfile:1
FROM python:3.12-slim-bookworm AS base
WORKDIR /app

# uv for fast, reproducible installs.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

# Runtime needs curl for the compose healthcheck.
RUN apt-get update \
    && apt-get install -y --no-install-recommends curl \
    && rm -rf /var/lib/apt/lists/*

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    PYTHONPATH=/app/src

# Install dependencies first (better layer caching).
COPY apps/server/pyproject.toml apps/server/uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

# App source.
COPY apps/server/ ./

EXPOSE 8000

# Apply migrations, then serve. The server is reachable only inside the compose
# network (see docker-compose.yml: no host `ports`).
CMD ["sh", "-c", "uv run alembic upgrade head && uv run uvicorn app.main:app --host 0.0.0.0 --port 8000"]
