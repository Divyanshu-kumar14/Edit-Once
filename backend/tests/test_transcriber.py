"""Pure SRT-generation core of the transcriber (no model, no network)."""

from __future__ import annotations

from types import SimpleNamespace

from app.pipeline.transcriber import format_timestamp, segments_to_srt


def _seg(start: float, end: float, text: str):
    return SimpleNamespace(start=start, end=end, text=text)


def test_format_timestamp() -> None:
    assert format_timestamp(0) == "00:00:00,000"
    assert format_timestamp(1250) == "00:00:01,250"
    assert format_timestamp(3_600_000 + 61_000 + 500) == "01:01:01,500"
    assert format_timestamp(-5) == "00:00:00,000"  # clamped


def test_segments_to_srt_basic_blocks() -> None:
    out = segments_to_srt([_seg(0.0, 2.0, " Hello  world "), _seg(2.5, 4.0, "second line")])
    assert out == (
        "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n"
        "2\n00:00:02,500 --> 00:00:04,000\nSecond line\n"
    )


def test_segments_to_srt_skips_blank_and_capitalizes() -> None:
    out = segments_to_srt([_seg(0.0, 1.0, "   "), _seg(1.0, 2.0, "i'M fine")])
    assert "1\n" in out and "I'M fine" in out
    assert "00:00:00,000" not in out  # blank segment dropped


def test_segments_to_srt_empty() -> None:
    assert segments_to_srt([]) == ""
