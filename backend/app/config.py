"""Central configuration: paths, upload limits, render concurrency.

All paths are derived from this file's location so the app works from any CWD.
The data directory can be overridden with the EDITONCE_DATA_DIR env var
(used by tests to avoid polluting real job data).
"""

from __future__ import annotations

import os
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
APP_DIR = Path(__file__).resolve().parent

# --- Paths ---
DATA_DIR = Path(os.environ.get("EDITONCE_DATA_DIR", BACKEND_DIR / "data"))
JOBS_DIR = DATA_DIR / "jobs"
FONTS_DIR = BACKEND_DIR / "fonts"
PLATFORMS_JSON = BACKEND_DIR / "platforms.json"
FRONTEND_DIST = APP_DIR / "static"  # vite build output (served at /)

# --- Upload limits (NFR-6) ---
MAX_UPLOAD_BYTES = 200 * 1024 * 1024  # 200 MB
MAX_DURATION_S = 600.0  # 600 s
MAX_CUES = 2000
ALLOWED_VIDEO_EXTS = {".mp4"}
ALLOWED_CAPTION_EXTS = {".srt", ".vtt"}

# --- Pipeline ---
RENDER_CONCURRENCY = 1  # one render at a time globally (NFR-3)
FFMPEG_TIMEOUT_FACTOR = 2.0  # hard timeout = 2x expected duration
RENDER_PRESET = "veryfast"
RENDER_CRF = 20

# --- Fonts ---
FONT_NAME = "Inter SemiBold"
FONT_FILENAME = "Inter-SemiBold.ttf"

# --- Frontend ---
POLL_INTERVAL_S = 2.0  # FR-8.4