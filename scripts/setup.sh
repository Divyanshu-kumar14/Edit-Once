#!/usr/bin/env bash
# Edit Once — dependency setup (NFR-4). Linux/macOS.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
cd "$ROOT"

echo "==> [1/5] Checking ffmpeg + libass (subtitles filter)"
if ! command -v ffmpeg >/dev/null 2>&1; then
  echo "    ffmpeg missing — installing via package manager..."
  if command -v apt-get >/dev/null 2>&1; then
    sudo apt-get update && sudo apt-get install -y ffmpeg
  elif command -v brew >/dev/null 2>&1; then
    brew install ffmpeg
  else
    echo "    ERROR: no apt-get/brew found — install ffmpeg manually (with libass)." >&2
    exit 1
  fi
fi
if ! ffmpeg -filters 2>/dev/null | grep -q "subtitles"; then
  echo "    ERROR: ffmpeg lacks the subtitles filter (libass). Reinstall ffmpeg with libass." >&2
  exit 1
fi
echo "    ffmpeg OK ($(ffmpeg -version | head -1 | cut -d' ' -f3)) + libass OK"

echo "==> [2/5] Python venv + packages"
python3 -m venv .venv
.venv/bin/pip install --quiet --upgrade pip
.venv/bin/pip install --quiet -r backend/requirements.txt

echo "==> [3/5] Bundled font"
if [ ! -f backend/fonts/Inter-SemiBold.ttf ]; then
  echo "    ERROR: backend/fonts/Inter-SemiBold.ttf missing (must be committed)." >&2
  exit 1
fi

echo "==> [4/5] Frontend deps + build"
cd frontend
npm install --no-audit --no-fund
npm run build
cd "$ROOT"

echo "==> [5/5] Fixtures (deterministic, offline)"
.venv/bin/python backend/tests/fixtures/make_fixture.py --outdir backend/tests/fixtures

echo
echo "Setup complete. Run:  scripts/run.sh   →  http://localhost:8000"