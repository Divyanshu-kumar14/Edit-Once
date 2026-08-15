"""Analyzer tests — FR-4.2 face anchoring: grouping, fallback, AC-9 crop shift.

Grouping/fallback logic is pure and tested directly with synthetic samples;
the cv2 sampling path is exercised against the real fixture (no faces ->
center anchor, deterministic).
"""

from __future__ import annotations

from pathlib import Path

from app.pipeline import analyzer
from app.pipeline.probe import probe

SHORT_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "short"


def _samples(*centers):
    """Build [(t, center)] samples at 0.5, 2.5, 4.5… from a list of centers
    (None = no face in that sample)."""
    return [(0.5 + 2.0 * i, c) for i, c in enumerate(centers)]


def test_grouping_merges_consecutive_faces() -> None:
    samples = _samples(None, (0.2, 0.3), (0.25, 0.35), (0.21, 0.31), None, None)
    scenes = analyzer._group_into_scenes(samples, 10.0)
    face_scenes = [s for s in scenes if s.has_face]
    assert len(face_scenes) == 1
    # Mean of the three face centers.
    assert abs(face_scenes[0].anchor_x - (0.2 + 0.25 + 0.21) / 3) < 1e-9
    assert abs(face_scenes[0].anchor_y - (0.3 + 0.35 + 0.31) / 3) < 1e-9
    assert face_scenes[0].start_s == 2.5
    # The run closes at the first gap sample after the last face.
    assert face_scenes[0].end_s == 8.5


def test_grouping_two_runs_and_gap_never_overlap() -> None:
    samples = _samples((0.1, 0.1), None, None, None, (0.9, 0.9), None)
    scenes = analyzer._group_into_scenes(samples, 12.0)
    face_scenes = [s for s in scenes if s.has_face]
    assert len(face_scenes) == 2
    # Chronological, no overlapping boundaries.
    prev_end = 0.0
    for scene in scenes:
        assert scene.start_s >= prev_end - 1e-9
        prev_end = scene.end_s
    assert scenes[-1].end_s == 12.0  # tail covered


def test_no_faces_falls_back_to_center() -> None:
    scenes = analyzer._group_into_scenes(_samples(None, None, None), 6.0)
    assert scenes
    assert all(s.has_face is False for s in scenes)
    assert all(s.anchor_x == 0.5 and s.anchor_y == 0.5 for s in scenes)
    # Continuous coverage from 0 to the end of the video.
    assert scenes[0].start_s == 0.0
    assert scenes[-1].end_s == 6.0
    assert analyzer.first_face_anchor(scenes) is None


def test_first_face_anchor_skips_leading_center_scene() -> None:
    # Faces only appear late; the renderer must still anchor on them.
    samples = _samples(None, None, (0.15, 0.45), (0.18, 0.48))
    scenes = analyzer._group_into_scenes(samples, 8.0)
    anchor = analyzer.first_face_anchor(scenes)
    assert anchor is not None
    assert abs(anchor[0] - 0.165) < 1e-9  # mean of the two face centers


def test_face_anchor_16x9_shifts_crop_window_left(monkeypatch) -> None:
    """AC-9 on a 16:9 source: face at x≈0.2 -> crop x left of the center crop."""
    from app.pipeline import rules

    # Face on the left third of every sampled frame.
    monkeypatch.setattr(analyzer, "face_center", lambda frame: (0.2, 0.5))
    samples = [(0.5, (0.2, 0.5)), (2.5, (0.2, 0.5))]
    scenes = analyzer._group_into_scenes(samples, 4.0)
    anchor = analyzer.first_face_anchor(scenes)
    assert anchor is not None and anchor[0] == 0.2

    # 16:9 input -> crop window has horizontal slack; anchor x=0.2 must pull
    # the window left versus the centered crop.
    cfg = rules.load_platforms()["tiktok"]
    face_crop = rules.crop_window(cfg, 1920, 1080, anchor[0], anchor[1])
    center_crop = rules.crop_window(cfg, 1920, 1080, 0.5, 0.5)
    assert face_crop.x < center_crop.x
    assert face_crop.w == center_crop.w


def test_real_fixture_no_faces_center(monkeypatch) -> None:
    """Real cv2 sampling on the fixture: no faces -> center anchor, no crash."""
    info = probe(SHORT_FIXTURE_DIR / "fixture.mp4")
    scenes = analyzer.analyze_scenes(SHORT_FIXTURE_DIR / "fixture.mp4", info)
    assert scenes
    assert analyzer.first_face_anchor(scenes) is None
    for scene in scenes:
        assert scene.has_face is False