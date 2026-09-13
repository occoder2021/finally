#!/usr/bin/env bash
# Build and start the FinAlly container (macOS/Linux).
#
# Idempotent — safe to run multiple times. All port/volume/env configuration
# lives in docker-compose.yml; this script only wraps `docker compose`.
set -euo pipefail
cd "$(dirname "${BASH_SOURCE[0]}")/.."

if [ ! -f .env ]; then
  if [ -f .env.example ]; then
    cp .env.example .env
    echo "Created .env from .env.example."
    echo "Edit .env and add your OPENROUTER_API_KEY (optional but needed for AI chat), then re-run this script."
    exit 1
  else
    echo "Missing .env and .env.example — cannot start. See planning/PLAN.md §5 for required variables." >&2
    exit 1
  fi
fi

docker compose up -d --build

echo "FinAlly is starting — waiting for it to become healthy..."

for _ in $(seq 1 30); do
  if curl -sf http://localhost:8000/api/health > /dev/null 2>&1; then
    echo "FinAlly is ready: http://localhost:8000"
    if command -v open > /dev/null 2>&1; then
      open http://localhost:8000
    elif command -v xdg-open > /dev/null 2>&1; then
      xdg-open http://localhost:8000
    fi
    exit 0
  fi
  sleep 1
done

echo "FinAlly did not report healthy within 30s — check 'docker compose logs' for details." >&2
exit 1
