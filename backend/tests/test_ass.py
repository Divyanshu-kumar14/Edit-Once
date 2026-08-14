"""ASS generation golden tests (PRD 6.2): exact style lines, dialogues, wrapping."""

from __future__ import annotations

from app.pipeline.ass import (
    Cue,
    build_ass,
    ms_to_ass_time,
    wrap_text,
)
from app.pipeline.rules import load_platforms

CUE = Cue(start_ms=1000, end_ms=2500, lines=["Hello world"], index=1)


def _ass_for(pid: str, cues: list[Cue], duration_s: float = 30.0) -> str:
    cfg = load_platforms()[pid]
    text, _ = build_ass(cfg, cues, duration_s)
    return text


def test_header_and_playres() -> None:
    text = _ass_for("tiktok", [CUE])
    assert "ScriptType: v4.00+" in text
    assert "PlayResX: 1080" in text
    assert "PlayResY: 1920" in text
    assert "WrapStyle: 2" in text


def test_style_line_exact_per_platform() -> None:
    """Golden Style line — MarginV differs per platform (the visible differentiator)."""
    expected = {
        "tiktok": "Style: Caption,Inter SemiBold,64,&H00FFFFFF,&H00FFFFFF,&H00000000,"
                  "&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,162,162,410,1",
        "reels": "Style: Caption,Inter SemiBold,64,&H00FFFFFF,&H00FFFFFF,&H00000000,"
                 "&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,162,162,640,1",
        "shorts": "Style: Caption,Inter SemiBold,64,&H00FFFFFF,&H00FFFFFF,&H00000000,"
                  "&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,270,270,448,1",
        "x": "Style: Caption,Inter SemiBold,64,&H00FFFFFF,&H00FFFFFF,&H00000000,"
             "&H00000000,0,0,0,0,100,100,0,0,1,3,1,2,108,108,352,1",
    }
    for pid, style in expected.items():
        assert style in _ass_for(pid, [CUE]), pid


def test_dialogue_line_exact() -> None:
    text = _ass_for("tiktok", [CUE])
    assert "Dialogue: 0,0:00:01.00,0:00:02.50,Caption,,0,0,0,,Hello world" in text


def test_dialogue_multiline_uses_hard_break() -> None:
    cue = Cue(start_ms=0, end_ms=1000, lines=["alpha beta gamma delta"], index=1)
    text = _ass_for("tiktok", [cue])
    assert "\\N" in text  # wrapping must use \N (WrapStyle 2 respects it)


def test_wrap_at_max_chars() -> None:
    lines, truncated = wrap_text("This is a very long caption line", 18, 3)
    assert lines == ["This is a very", "long caption line"]
    assert truncated is False


def test_truncation_with_ellipsis() -> None:
    lines, truncated = wrap_text(
        "This is a very long caption line that definitely wraps into many lines", 18, 3
    )
    assert truncated is True
    assert len(lines) == 3
    assert lines[-1].endswith("…")


def test_cue_end_clamped_to_duration() -> None:
    cue = Cue(start_ms=0, end_ms=5000, lines=["x"], index=1)
    text = _ass_for("tiktok", [cue], duration_s=2.0)
    assert "0:00:05.00" not in text
    assert "0:00:02.00" in text


def test_inline_tags_stripped() -> None:
    cue = Cue(start_ms=0, end_ms=1000, lines=["<i>italic</i> plain"], index=1)
    text = _ass_for("tiktok", [cue])
    assert "<i>" not in text
    assert "italic plain" in text


def test_ass_braces_escaped() -> None:
    cue = Cue(start_ms=0, end_ms=1000, lines=["curly {brace}"], index=1)
    text = _ass_for("tiktok", [cue])
    assert "\\{brace\\}" in text


def test_timecode_format() -> None:
    assert ms_to_ass_time(0) == "0:00:00.00"
    assert ms_to_ass_time(1000) == "0:00:01.00"
    assert ms_to_ass_time(6123456) == "1:42:03.45"  # h > 0
    assert ms_to_ass_time(59_999) == "0:00:59.99"