#!/usr/bin/env python3
"""Deterministic fixture generation (PRD 9.2) — no internet required.

Generates:
  fixture.mp4   30 s, 1080x1920, moving gradient + moving orange box, sine audio
  fixture.srt   8 cues, some >18 chars (forces wrapping), last cue ends at 28 s
  fixture_16x9.mp4   same content at 1920x1080 (crop-path tests)

Usage:
  python tests/fixtures/make_fixture.py [--outdir tests/fixtures] [--dur 30]
"""

from __future__ import annotations

import argparse
import subprocess
import shutil
import sys
from pathlib import Path

DEFAULT_DUR = 30
SRT_CUES = [
    (1000, 4000, "This is the very first caption line and it is long"),
    (4500, 8000, "Second caption also quite long to force wrapping"),
    (8500, 12000, "Short one"),
    (12500, 16000, "Another really long caption line that will wrap into several lines"),
    (16500, 20000, "Bottom-anchored text near the edge"),
    (20500, 23000, "TikTok safe zone bottom"),
    (23500, 26000, "Instagram Reels needs captions higher up"),
    (26500, 28000, "Final caption for the checklist"),
]


def srt_text(duration_ms: int = DEFAULT_DUR * 1000) -> str:
    blocks = []
    for i, (start, end, text) in enumerate(SRT_CUES, start=1):
        if start >= duration_ms:
            continue  # cue starts after video end — drop (short fixtures)
        end = min(end, duration_ms)  # clamp to video duration
        blocks.append(f"{i}\n{_ts(start)} --> {_ts(end)}\n{text}")
    return "\n\n".join(blocks) + "\n"


def _ts(ms: int) -> str:
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def make_video(out: Path, width: int, height: int, dur: int) -> None:
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        sys.exit("ffmpeg not found — run scripts/setup.sh first")
    cmd = [
        ffmpeg, "-y",
        "-f", "lavfi", "-i",
        f"gradients=s={width}x{height}:c0=0x1b1b3a:c1=0x111125:r=30:d={dur}:speed=0.05",
        "-f", "lavfi", "-i",
        f"sine=frequency=440:sample_rate=48000:duration={dur}",
        "-filter_complex",
        f"[0:v]drawbox=x='min(mod(t*280,{width}),{width}-220)':"
        f"y='({height}/2-110)':w=220:h=220:color=0xE05A3C@0.95:t=fill[v]",
        "-map", "[v]", "-map", "1:a",
        "-c:v", "libx264", "-preset", "veryfast", "-crf", "20", "-pix_fmt", "yuv420p",
        "-c:a", "aac", "-b:a", "128k",
        "-movflags", "+faststart",
        "-metadata", "comment=EditOnce deterministic fixture",
        str(out),
    ]
    result = subprocess.run(cmd, capture_output=True, text=True)
    if result.returncode != 0:
        sys.exit(f"fixture generation failed:\n{result.stderr[-500:]}")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outdir", type=Path, default=Path(__file__).parent)
    parser.add_argument("--dur", type=int, default=DEFAULT_DUR)
    args = parser.parse_args()

    args.outdir.mkdir(parents=True, exist_ok=True)
    make_video(args.outdir / "fixture.mp4", 1080, 1920, args.dur)
    make_video(args.outdir / "fixture_16x9.mp4", 1920, 1080, args.dur)
    (args.outdir / "fixture.srt").write_text(srt_text(args.dur * 1000))
    print(f"wrote {args.outdir/'fixture.mp4'}, fixture_16x9.mp4, fixture.srt")


if __name__ == "__main__":
    main()