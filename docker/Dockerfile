# syntax=docker/dockerfile:1

# ---- Stage 1: builder -------------------------------------------------------
# Resolve and install the workspace into a self-contained venv using uv.
FROM python:3.12-slim AS builder

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_PYTHON_DOWNLOADS=never

WORKDIR /app

# Copy only what uv needs to resolve first, so the dependency layer caches
# independently of source-code changes.
COPY pyproject.toml uv.lock ./
COPY packages/core/pyproject.toml packages/core/pyproject.toml
COPY packages/ingestion/pyproject.toml packages/ingestion/pyproject.toml
COPY packages/retrieval/pyproject.toml packages/retrieval/pyproject.toml
COPY packages/api/pyproject.toml packages/api/pyproject.toml

# Then the source, then a full sync so the workspace packages install too.
COPY packages/ packages/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev

# ---- Stage 2: runtime -------------------------------------------------------
# Slim final image: just the venv and source, no uv, no build tooling.
FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/packages /app/packages

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1

USER app

EXPOSE 8000

# Overridable; docker-compose sets the concrete command per service.
CMD ["serve"]
