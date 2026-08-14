"""ffmpeg render command builder + runner (PRD 6.3).

Runs with a hard timeout (2x expected duration), captures stderr for error
reporting, and reports 0-100 progress from ffmpeg's -progress output (FR-2.3).
"""

from __future__ import annotations

import shutil
import subprocess
from functools import lru_cache
from pathlib import Path

from .. import config
from .rules import CropWindow


class RenderError(RuntimeError):
    """Render failed; message carries the stderr tail."""


@lru_cache(maxsize=1)
def _ffmpeg_path() -> str | None:
    """Memoize the PATH lookup — shutil.which() walks every PATH entry per call."""
    return shutil.which("ffmpeg")


def escape_filter_path(path: Path) -> str:
    """Escape a path for use inside an ffmpeg filter graph argument."""
    s = str(path)
    s = s.replace("\\", "\\\\")
    s = s.replace(":", "\\:")
    s = s.replace("'", "\\'")
    return f"'{s}'"


def build_vf(crop: CropWindow | None, ass_path: Path, fonts_dir: Path) -> str:
    """Video filter chain: optional crop -> scale to 1080x1920 -> burn captions."""
    parts: list[str] = []
    if crop is not None:
        parts.append(f"crop=w={crop.w}:h={crop.h}:x={crop.x}:y={crop.y}")
    parts.append("scale=1080:1920:flags=lanczos")
    parts.append(f"subtitles={escape_filter_path(ass_path)}:fontsdir={escape_filter_path(fonts_dir)}")
    return ",".join(parts)


def render(
    job_dir: Path,
    platform: str,
    vf: str,
    duration_s: float,
    on_progress: callable | None = None,
) -> None:
    """Render in.mp4 -> versions/{platform}.mp4. Raises RenderError on failure."""
    ffmpeg = _ffmpeg_path()
    if ffmpeg is None:
        raise RenderError("ffmpeg not found on PATH")

    versions_dir = job_dir / "versions"
    versions_dir.mkdir(parents=True, exist_ok=True)
    output = versions_dir / f"{platform}.mp4"

    cmd = [
        ffmpeg, "-y",
        "-i", str(job_dir / "in.mp4"),
        "-vf", vf,
        "-c:v", "libx264", "-preset", config.RENDER_PRESET, "-crf", str(config.RENDER_CRF),
        "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-map", "0:v", "-map", "0:a?",  # video required; audio optional (PRD 6.3)
        "-movflags", "+faststart",
        "-map_metadata", "-1",
        "-progress", "pipe:1",
        "-nostats",
        str(output),
    ]
    timeout = max(60.0, duration_s * config.FFMPEG_TIMEOUT_FACTOR) + 30.0

    try:
        proc = subprocess.Popen(
            cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, bufsize=1
        )
    except OSError as exc:
        raise RenderError(f"failed to launch ffmpeg: {exc}") from exc

    stderr_tail: list[str] = []
    assert proc.stdout is not None and proc.stderr is not None

    try:
        # Read progress lines (key=value) from stdout; keep last 30 stderr lines.
        for raw in proc.stdout:
            line = raw.strip()
            if on_progress is not None and line.startswith("out_time"):
                ms = _parse_progress_time(line)
                if ms is not None and duration_s > 0:
                    on_progress(min(99, int(ms / (duration_s * 1000.0) * 100)))
        proc.wait(timeout=timeout)
        stderr_tail = proc.stderr.read().strip().splitlines()[-30:]
    except subprocess.TimeoutExpired:
        proc.kill()
        proc.wait()
        raise RenderError(f"render timed out after {timeout:.0f}s") from None
    finally:
        proc.stderr.close()

    if proc.returncode != 0:
        tail = "\n".join(stderr_tail)[:500]
        raise RenderError(f"ffmpeg exited {proc.returncode}: {tail}")


def _parse_progress_time(line: str) -> int | None:
    """Parse a -progress line into milliseconds: out_time_ms=1234 or out_time=00:00:01.23."""
    key, _, value = line.partition("=")
    if key == "out_time_ms":
        try:
            return int(value)
        except ValueError:
            return None
    if key == "out_time":
        try:
            h, m, s = value.split(":")
            return int((int(h) * 3600 + int(m) * 60 + float(s)) * 1000)
        except ValueError:
            return None
    return None