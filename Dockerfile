# syntax=docker/dockerfile:1
#
# FinAlly — multi-stage build.
#   Stage 1 builds the Next.js frontend as a static export.
#   Stage 2 installs the Python backend (uv) and serves both the API and the
#   static frontend from a single container on port 8000.
#
# See planning/PLAN.md §11 and planning/TEAM_CONTRACT.md §9 for the contract
# this file implements.

########################################
# Stage 1 — frontend static export
########################################
FROM node:20-slim AS frontend-build
WORKDIR /app/frontend

# Install dependencies first so this layer is cached independently of
# application source changes. Falls back to `npm install` until a lockfile
# exists (the frontend agent is building this project in parallel).
COPY frontend/package.json frontend/package-lock.json* ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi

COPY frontend/ .
RUN npm run build
# `output: 'export'` in next.config produces a static site in frontend/out.

########################################
# Stage 2 — backend runtime + static frontend
########################################
FROM python:3.12-slim AS runtime

# uv, copied from Astral's official distroless image — no pip bootstrap needed.
COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /usr/local/bin/

ENV PYTHONUNBUFFERED=1 \
    UV_LINK_MODE=copy \
    FINALLY_DB_PATH=/app/db/finally.db \
    FINALLY_STATIC_DIR=/app/static \
    PATH="/app/.venv/bin:$PATH"

WORKDIR /app

# Install Python dependencies from the lockfile before copying the rest of
# the source, so dependency changes and code changes invalidate the Docker
# layer cache independently.
COPY backend/pyproject.toml backend/uv.lock backend/README.md ./
COPY backend/app ./app
# --system-certs: this environment sits behind a TLS-intercepting proxy (see
# backend/CLAUDE.md); the flag makes uv trust the OS certificate store when
# fetching packages. Harmless on a normal network.
RUN uv sync --frozen --no-dev --system-certs

# Static frontend export, served by FastAPI's catch-all route mounted after
# all /api/* routes (see TEAM_CONTRACT.md §6).
COPY --from=frontend-build /app/frontend/out ./static

# Mount point for the SQLite database — named volume `finally-data` in
# docker-compose.yml. Created here so the directory exists even before the
# volume is attached (e.g. under `docker run` without -v).
RUN mkdir -p /app/db

EXPOSE 8000

# Bare `python` here resolves to the system interpreter, not the project
# venv — fine, since urllib is stdlib and this must never gain a dependency
# on anything `uv sync` installed.
HEALTHCHECK --interval=30s --timeout=3s --start-period=10s --retries=3 \
    CMD ["python", "-c", "import urllib.request; urllib.request.urlopen('http://localhost:8000/api/health', timeout=2)"]

# Invoke the already-synced venv's uvicorn directly rather than `uv run`, so
# container start never re-resolves or re-syncs dependencies (no network
# access, no proxy/cert requirement, no startup delay at boot).
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]
