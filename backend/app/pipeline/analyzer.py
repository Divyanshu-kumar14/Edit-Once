"""Scene analysis: per-scene crop anchors (FR-4).

FR-4.2 (P1): sample ~1 frame per 2 s (ffmpeg fps=0.5 semantics), run Haar
frontal-face detection, group CONSECUTIVE detections into scenes anchored at
the mean face-center; segments without faces fall back to the center anchor.
No per-frame tracking, no smoothing loops — deterministic (per PRD).

The renderer currently consumes the first FACE anchor (single crop window);
scene boundaries are kept for future segmented renders.
"""

from __future__ import annotations

import cv2
from dataclasses import dataclass
from pathlib import Path

from .face import face_center
from .probe import MediaInfo

SAMPLE_STEP_S = 2.0  # one sample every 2 s (fps=0.5)
MAX_SCENES = 24  # bound the scene list for pathological inputs


@dataclass(slots=True)
class SceneAnchor:
    start_s: float
    end_s: float
    anchor_x: float  # 0..1 fraction within the crop slack
    anchor_y: float  # 0..1 fraction within the crop slack
    has_face: bool = False  # True when this scene was anchored on a face


def analyze_scenes(path: Path, info: MediaInfo) -> list[SceneAnchor]:
    """One anchor per scene; center fallback when no faces (P0 behavior).

    Complexity: O(n x H x W) with n = duration/2 samples, each frame bounded
    to <=1280 px wide in face.py before the Haar scan (the dominant cost).
    Grouping afterwards is a single O(n) pass (see _group_into_scenes).
    """
    samples = _sample_anchors(path, info.duration_s)
    return _group_into_scenes(samples, info.duration_s)


def _sample_anchors(path: Path, duration_s: float) -> list[tuple[float, tuple[float, float] | None]]:
    """[(t_seconds, face_center | None)] — one sample every 2 s (FR-4.2).

    O(n) seeks+decodes, n = ceil(duration/2) — one cv2.VideoCapture rewind
    per sample (CAP_PROP_POS_MSEC). Rewinding per-sample is O(1) per call in
    ffmpeg-backed captures; NOT O(n^2) — frames are not re-decoded from 0.
    """
    cap = cv2.VideoCapture(str(path))
    samples: list[tuple[float, tuple[float, float] | None]] = []
    try:
        if not cap.isOpened():
            return samples
        t = 0.5  # skip frame 0 (often black/blank)
        while t < duration_s:
            cap.set(cv2.CAP_PROP_POS_MSEC, int(t * 1000))
            ok, frame = cap.read()
            if not ok or frame is None:
                t += SAMPLE_STEP_S
                continue
            samples.append((t, face_center(frame)))
            t += SAMPLE_STEP_S
    finally:
        cap.release()
    return samples


def _group_into_scenes(
    samples: list[tuple[float, tuple[float, float] | None]], duration_s: float
) -> list[SceneAnchor]:
    """Merge consecutive face detections into scenes; gaps become center anchors.

    Runs of face samples -> one scene at their mean center. Non-face segments
    -> center-anchored scenes so every second of video is covered. Boundaries
    never overlap: a gap scene ends exactly where the next face run begins.

    Complexity: one pass over the samples (O(n)); run means are accumulated
    incrementally (sum/len is O(1) per flush). The final sort is bounded by
    MAX_SCENES (truncation happens first), so it is O(MAX_SCENES log MAX) —
    constant for any input length.
    """
    scenes: list[SceneAnchor] = []
    t0 = 0.0
    pending_faces: list[tuple[float, float]] = []  # centers of the current run
    pending_start: float | None = None

    def flush_face_scene(end_s: float) -> None:
        nonlocal pending_start, pending_faces
        if pending_start is None:
            return
        mx = sum(c[0] for c in pending_faces) / len(pending_faces)
        my = sum(c[1] for c in pending_faces) / len(pending_faces)
        scenes.append(
            SceneAnchor(start_s=pending_start, end_s=end_s, anchor_x=mx, anchor_y=my, has_face=True)
        )
        pending_start = None
        pending_faces = []

    for t, center in samples:
        if center is not None:
            if pending_start is None:
                pending_start = t
            pending_faces.append(center)
        else:
            run_start = pending_start
            flush_face_scene(t)
            # Gap scene: from the previous boundary up to the face run (or t).
            gap_end = run_start if run_start is not None else t
            if gap_end > t0:
                scenes.append(SceneAnchor(start_s=t0, end_s=gap_end, anchor_x=0.5, anchor_y=0.5))
            t0 = t

    # Tail after the last sample: close an open face run, then cover the gap
    # before it (if any) or extend from the last boundary (t0) to the end.
    run_start = pending_start
    flush_face_scene(duration_s)
    if run_start is not None and t0 < run_start:
        scenes.append(SceneAnchor(start_s=t0, end_s=run_start, anchor_x=0.5, anchor_y=0.5))
    elif t0 < duration_s:
        scenes.append(SceneAnchor(start_s=t0, end_s=duration_s, anchor_x=0.5, anchor_y=0.5))

    if len(scenes) > MAX_SCENES:
        scenes = scenes[:MAX_SCENES]
    # Gap-before-run scenes are appended after their run; keep the list
    # chronologically sorted so consumers can rely on order.
    scenes.sort(key=lambda s: s.start_s)
    return scenes


def first_face_anchor(scenes: list[SceneAnchor]) -> tuple[float, float] | None:
    """The first face-anchored scene's center, or None (renderer uses this:
    if faces exist anywhere, the single crop window centers on them).

    O(k) worst case (k <= MAX_SCENES, i.e. constant), typically O(1) because
    face runs cluster near the start.
    """
    for scene in scenes:
        if scene.has_face:
            return scene.anchor_x, scene.anchor_y
    return None