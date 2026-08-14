"""Scene analysis: per-scene crop anchors (FR-4).

P0: center anchor for the entire video. Face detection (FR-4.2, P1) will be
implemented inside analyze_scenes in a later phase — the pipeline only depends
on the SceneAnchor list it returns.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from .probe import MediaInfo


@dataclass(slots=True)
class SceneAnchor:
    start_s: float
    end_s: float
    anchor_x: float  # 0..1 fraction within the crop slack
    anchor_y: float  # 0..1 fraction within the crop slack


def analyze_scenes(path: Path, info: MediaInfo) -> list[SceneAnchor]:
    """Return one anchor per scene. P0: single centered anchor."""
    del path  # face detection (P1) will read frames from the video here
    return [SceneAnchor(start_s=0.0, end_s=info.duration_s, anchor_x=0.5, anchor_y=0.5)]