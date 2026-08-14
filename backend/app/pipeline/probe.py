"""ffprobe wrapper -> MediaInfo dataclass."""

from __future__ import annotations

import json
import shutil
import subprocess
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


class ProbeError(RuntimeError):
    """Raised when ffprobe is missing, fails, or returns unparseable data."""


@lru_cache(maxsize=1)
def _ffprobe_path() -> str | None:
    """Memoize the PATH lookup (shutil.which walks PATH per call; probe runs
    once per upload + once per rendered version)."""
    return shutil.which("ffprobe")


@dataclass(slots=True)
class MediaInfo:
    width: int
    height: int
    duration_s: float
    fps: float | None  # None when absent/invalid (renderer then defaults to 30)
    has_audio: bool
    video_codec: str | None
    audio_codec: str | None


def _parse_fps(rate: str | None) -> float | None:
    """Parse ffprobe's r_frame_rate ('30000/1001') -> float; None if invalid."""
    if not rate or "/" not in rate:
        return None
    try:
        num, den = rate.split("/", 1)
        fps = float(num) / float(den)
        return fps if 0 < fps < 240 else None  # sanitize absurd values (FR-3.2)
    except (ValueError, ZeroDivisionError):
        return None


def _parse_duration(raw: str | None) -> float | None:
    if raw is None:
        return None
    try:
        value = float(raw)
        return value if value > 0 else None
    except ValueError:
        return None


def probe(path: Path) -> MediaInfo:
    """Probe a media file with ffprobe and return structured info."""
    ffprobe = _ffprobe_path()
    if ffprobe is None:
        raise ProbeError("ffprobe not found on PATH — install ffmpeg")

    cmd = [
        ffprobe,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]
    try:
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired as exc:
        raise ProbeError("ffprobe timed out") from exc
    if result.returncode != 0:
        raise ProbeError(f"ffprobe failed: {result.stderr.strip()[:300]}")

    try:
        data = json.loads(result.stdout)
    except json.JSONDecodeError as exc:
        raise ProbeError("ffprobe returned unparseable output") from exc

    video_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "video"), None)
    audio_stream = next((s for s in data.get("streams", []) if s.get("codec_type") == "audio"), None)
    if video_stream is None:
        raise ProbeError("no video stream found in file")

    duration = _parse_duration(data.get("format", {}).get("duration")) or _parse_duration(
        video_stream.get("duration")
    )

    return MediaInfo(
        width=int(video_stream.get("width", 0)),
        height=int(video_stream.get("height", 0)),
        duration_s=duration or 0.0,
        fps=_parse_fps(video_stream.get("r_frame_rate")),
        has_audio=audio_stream is not None,
        video_codec=video_stream.get("codec_name"),
        audio_codec=audio_stream.get("codec_name") if audio_stream else None,
    )