"""Stills extraction (FR-6.1): 3 JPEGs per version at caption-visible times.

Times: first caption cue start, 40% of duration, 80% of duration — each
snapped into the nearest caption cue when within 2 s.
"""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

STILL_TIMES = (0.40, 0.80)  # fractions of duration, after the first cue start


def _snap_to_cue(target_s: float, cue_starts_ms: list[int]) -> float:
    if not cue_starts_ms:
        return target_s
    nearest = min(cue_starts_ms, key=lambda ms: abs(ms / 1000.0 - target_s))
    if abs(nearest / 1000.0 - target_s) <= 2.0:
        return nearest / 1000.0
    return target_s


def still_timestamps(duration_s: float, cue_starts_ms: list[int]) -> list[float]:
    """The 3 timestamps (seconds) for still extraction."""
    if duration_s <= 0:
        return []
    first_cue = min(cue_starts_ms) / 1000.0 if cue_starts_ms else 0.0
    targets = [first_cue, duration_s * STILL_TIMES[0], duration_s * STILL_TIMES[1]]
    snapped = [_snap_to_cue(t, cue_starts_ms) for t in targets]
    # de-duplicate near-identical timestamps, keep first 3
    unique: list[float] = []
    for t in snapped:
        if all(abs(t - u) > 0.1 for u in unique):
            unique.append(t)
    return unique[:3]


def extract_stills(
    job_dir: Path, platform: str, duration_s: float, cue_starts_ms: list[int]
) -> list[Path]:
    """Extract 3 stills from versions/{platform}.mp4 into stills/. Non-fatal."""
    ffmpeg = shutil.which("ffmpeg")
    source = job_dir / "versions" / f"{platform}.mp4"
    if ffmpeg is None or not source.exists():
        return []

    stills_dir = job_dir / "stills"
    stills_dir.mkdir(parents=True, exist_ok=True)

    paths: list[Path] = []
    for i, t in enumerate(still_timestamps(duration_s, cue_starts_ms)):
        out = stills_dir / f"{platform}_{i}.jpg"
        cmd = [
            ffmpeg, "-y", "-ss", f"{t:.3f}", "-i", str(source),
            "-frames:v", "1", "-q:v", "3", str(out),
        ]
        try:
            result = subprocess.run(cmd, capture_output=True, text=True, timeout=30)
            if result.returncode == 0 and out.exists():
                paths.append(out)
        except subprocess.TimeoutExpired:
            continue
    return paths