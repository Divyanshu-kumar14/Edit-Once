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


def test_long_cue_split_into_chunks_no_truncation() -> None:
    """Auto-transcribed long cues split into sequential dialogues — never '…'."""
    text = (
        "So today we're going to show you how to edit your videos for "
        "TikTok and Instagram Reels in just a few minutes with no experience needed"
    )
    cue = Cue(start_ms=0, end_ms=8000, lines=[text], index=1)
    ass_text, wrapped = build_ass(load_platforms()["tiktok"], [cue], 30.0)

    assert len(wrapped) > 1  # split, not truncated
    assert "…" not in ass_text
    for word in text.split():  # every word survives
        assert word in ass_text
    for w in wrapped:
        assert w.line_count <= 3  # each chunk fits the platform line cap

    # chunks partition the cue's time window, non-overlapping, gap-free,
    # and every chunk gets positive screen time
    assert wrapped[0].start_ms == 0
    assert wrapped[-1].end_ms == 8000
    for prev, cur in zip(wrapped, wrapped[1:]):
        assert prev.end_ms == cur.start_ms
        assert prev.start_ms < prev.end_ms
    assert wrapped[-1].start_ms < wrapped[-1].end_ms


def test_split_chunks_keep_all_words_with_two_line_chunks() -> None:
    """A cue that wraps past max_lines still shows its final words."""
    text = (
        "alpha beta gamma delta epsilon zeta eta theta iota kappa "
        "lambda mu nu xi omicron pi rho sigma tau upsilon phi chi psi omega"
    )
    cue = Cue(start_ms=500, end_ms=6500, lines=[text], index=1)
    ass_text, _ = build_ass(load_platforms()["reels"], [cue], 30.0)
    assert "omega" in ass_text  # last word must not be cut
    assert "…" not in ass_text


def test_short_cue_stays_single_timed_dialogue() -> None:
    """Short cues keep one dialogue with their exact original timing."""
    _, wrapped = build_ass(load_platforms()["tiktok"], [CUE], 30.0)
    assert len(wrapped) == 1
    assert wrapped[0].start_ms == 1000
    assert wrapped[0].end_ms == 2500


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