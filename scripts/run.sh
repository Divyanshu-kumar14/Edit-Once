#!/usr/bin/env bash
# Edit Once — run the app (NFR-4): FastAPI on :8000 serving the frontend build.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT/backend"

if [ ! -d "$ROOT/.venv" ]; then
  echo "No .venv — run scripts/setup.sh first." >&2
  exit 1
fi

exec "$ROOT/.venv/bin/uvicorn" app.main:app --host 0.0.0.0 --port 8000