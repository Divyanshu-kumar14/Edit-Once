"""Verifier tests: geometry inside/outside safe rect, ratio, audio, duration (FR-5)."""

from __future__ import annotations

from pathlib import Path

from app.pipeline.ass import WrappedCue
from app.pipeline.probe import MediaInfo
from app.pipeline.rules import load_platforms
from app.pipeline.verifier import (
    check_audio,
    check_captions_safe,
    check_duration,
    check_face,
    check_ratio,
    check_resolution,
    verify,
)


def _info(width=1080, height=1920, duration=30.0, has_audio=True) -> MediaInfo:
    return MediaInfo(
        width=width, height=height, duration_s=duration, fps=30.0,
        has_audio=has_audio, video_codec="h264", audio_codec="aac",
    )


def _wrapped(lines: int = 1, truncated: bool = False) -> list[WrappedCue]:
    return [WrappedCue(cue_index=1, lines=["x"] * lines, truncated=truncated)]


def test_resolution_pass_exact() -> None:
    assert check_resolution(1080, 1920, (720, 1280)).result == "pass"


def test_resolution_warn_above_min() -> None:
    assert check_resolution(720, 1280, (720, 1280)).result == "warn"


def test_resolution_fail_below_min() -> None:
    assert check_resolution(640, 1136, (720, 1280)).result == "fail"


def test_ratio_pass_and_fail() -> None:
    assert check_ratio(1080, 1920).result == "pass"
    assert check_ratio(1920, 1080).result == "fail"


def test_audio() -> None:
    assert check_audio(True).result == "pass"
    assert check_audio(False).result == "fail"


def test_duration_pass_and_warn() -> None:
    assert check_duration(30.0, 180).result == "pass"
    assert check_duration(200.0, 180).result == "warn"


def test_captions_safe_pass_for_all_platforms() -> None:
    """Default style: 3 lines max; box must sit inside every platform's safe rect."""
    for pid in ("tiktok", "reels", "shorts", "x"):
        cfg = load_platforms()[pid]
        result = check_captions_safe(cfg, _wrapped(lines=3))
        assert result.result == "pass", (pid, result.detail)


def test_captions_safe_warn_on_truncation() -> None:
    cfg = load_platforms()["tiktok"]
    result = check_captions_safe(cfg, _wrapped(truncated=True))
    assert result.result == "warn"
    assert "truncated" in result.detail


def test_captions_safe_fail_when_outside_rect() -> None:
    cfg = load_platforms()["tiktok"]
    # Box: bottom at 1920-410=1510; safe top = 96 -> need height > 1414px.
    # 20 lines * 64 * 1.2 = 1536 -> top = -26, outside the safe rect.
    result = check_captions_safe(cfg, _wrapped(lines=20))
    assert result.result == "fail"
    assert "outside" in result.detail


def test_verify_bundle_all_pass() -> None:
    cfg = load_platforms()["tiktok"]
    checks = verify(cfg, _wrapped(lines=3), _info(), source_has_audio=True)
    assert [c.name for c in checks] == ["resolution", "ratio", "captions_safe", "audio", "duration"]
    assert all(c.result == "pass" for c in checks)


# --- Day-2: face check (AC-9) ----------------------------------------------

SHORT_MP4 = Path(__file__).parent / "fixtures" / "short" / "fixture.mp4"


def test_verify_skips_face_check_when_not_expected() -> None:
    cfg = load_platforms()["tiktok"]
    checks = verify(
        cfg, _wrapped(lines=3), _info(), source_has_audio=True,
        face_expected=False, output_path=SHORT_MP4,
    )
    assert [c.name for c in checks] == ["resolution", "ratio", "captions_safe", "audio", "duration"]


def test_check_face_pass_when_centered(monkeypatch) -> None:
    # A face box whose center is inside the central region (AC-9).
    monkeypatch.setattr(
        "app.pipeline.verifier.detect_faces",
        lambda frame: [(400, 800, 200, 200)],  # center ≈ (0.46, 0.47) on 1080x1920
    )
    result = check_face(SHORT_MP4)
    assert result.name == "face"
    assert result.result == "pass"


def test_check_face_fail_when_no_face(monkeypatch) -> None:
    monkeypatch.setattr("app.pipeline.verifier.detect_faces", lambda frame: [])
    result = check_face(SHORT_MP4)
    assert result.result == "fail"


def test_check_face_fail_when_off_center(monkeypatch) -> None:
    # Box hugging the left edge: cx≈0.05 -> not in the central region.
    monkeypatch.setattr(
        "app.pipeline.verifier.detect_faces", lambda frame: [(10, 900, 100, 100)]
    )
    result = check_face(SHORT_MP4)
    assert result.result == "fail"


def test_verify_bundle_includes_face_when_expected(monkeypatch) -> None:
    monkeypatch.setattr("app.pipeline.verifier.detect_faces", lambda frame: [(400, 800, 200, 200)])
    cfg = load_platforms()["tiktok"]
    checks = verify(
        cfg, _wrapped(lines=3), _info(), source_has_audio=True,
        face_expected=True, output_path=SHORT_MP4,
    )
    names = [c.name for c in checks]
    assert names == ["resolution", "ratio", "captions_safe", "audio", "duration", "face"]
    assert checks[-1].result == "pass"