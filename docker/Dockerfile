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

# --- Pass 1: install DEPENDENCIES ONLY, from the lockfile + pyproject metadata.
# This layer depends only on uv.lock and the pyproject.toml files copied above,
# NOT on source. So editing application code doesn't invalidate it — torch and
# the rest are reinstalled only when dependencies actually change.
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package mdhpp-api --no-install-workspace

# --- Pass 2: copy source, then install just the workspace packages.
# Fast: the heavy third-party deps are already in the venv from pass 1; this
# only builds/installs the small first-party packages on top.
COPY packages/ packages/
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --frozen --no-dev --package mdhpp-api

# ---- Stage 2: runtime -------------------------------------------------------
# Slim final image: just the venv and source, no uv, no build tooling.
FROM python:3.12-slim AS runtime

RUN groupadd --system app && useradd --system --gid app --create-home app

WORKDIR /app

COPY --from=builder --chown=app:app /app/.venv /app/.venv
COPY --from=builder --chown=app:app /app/packages /app/packages

# Pre-create the model/HF cache dirs owned by `app`. Named volumes mounted onto
# these paths inherit the directory's ownership, so the non-root app user can
# write downloaded weights. Without this the volume mounts root-owned and model
# downloads fail with PermissionError.
RUN mkdir -p /home/app/.cache/huggingface /home/app/.cache/mdhpp \
    && chown -R app:app /home/app/.cache

ENV PATH="/app/.venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    HF_HOME=/home/app/.cache/huggingface

USER app

EXPOSE 8000

# Overridable; docker-compose can set a per-service command.
# Uses the `serve` console script (api pyproject [project.scripts]), which runs
# uvicorn against the app. The reverse proxy fronts this on :80.
CMD ["serve"]
