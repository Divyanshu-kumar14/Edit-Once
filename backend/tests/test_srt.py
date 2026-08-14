"""SRT/VTT parser unit tests (FR-1.1, FR-1.2, NFR-6)."""

from __future__ import annotations

import pytest

from app.pipeline.ass import SrtParseError, parse_captions, parse_srt, parse_vtt


def test_basic_parse() -> None:
    srt = (
        "1\n"
        "00:00:01,000 --> 00:00:02,500\n"
        "Hello world\n"
        "\n"
        "2\n"
        "00:00:03,000 --> 00:00:04,000\n"
        "Line one\n"
        "Line two\n"
    )
    cues = parse_srt(srt)
    assert len(cues) == 2
    assert cues[0].start_ms == 1000
    assert cues[0].end_ms == 2500
    assert cues[0].text == "Hello world"
    assert cues[1].lines == ["Line one", "Line two"]


def test_crlf_and_bom() -> None:
    srt = "\ufeff1\r\n00:00:00,000 --> 00:00:01,000\r\nHi\r\n\r\n"
    cues = parse_srt(srt)
    assert len(cues) == 1
    assert cues[0].text == "Hi"


def test_bad_timestamp_reports_line() -> None:
    srt = "1\n00:00:00,000 --> 00:00:01,000\nok\n\n2\n00:0x:00,000 --> 00:00:01,000\nbad\n"
    with pytest.raises(SrtParseError) as exc:
        parse_srt(srt)
    assert exc.value.line == 6  # the broken timestamp lives on line 6


def test_end_before_start_rejected() -> None:
    with pytest.raises(SrtParseError) as exc:
        parse_srt("1\n00:00:05,000 --> 00:00:01,000\nnope\n")
    assert exc.value.line == 2


def test_missing_timestamp_line() -> None:
    with pytest.raises(SrtParseError) as exc:
        parse_srt("1\njust text\n")
    assert "timestamp" in exc.value.message


def test_empty_file_rejected() -> None:
    with pytest.raises(SrtParseError) as exc:
        parse_srt("")
    assert "no caption cues" in exc.value.message


def test_too_many_cues_rejected() -> None:
    blocks = []
    for i in range(2001):
        blocks.append(f"{i}\n00:00:00,000 --> 00:00:01,000\ncue {i}")
    with pytest.raises(SrtParseError) as exc:
        parse_srt("\n\n".join(blocks))
    assert "2000" in exc.value.message


def test_vtt_parse() -> None:
    vtt = (
        "WEBVTT\n"
        "\n"
        "NOTE this is a comment\n"
        "that spans lines\n"
        "\n"
        "00:00.500 --> 00:02.000 align:start position:0%\n"
        "VTT caption\n"
    )
    cues = parse_vtt(vtt)
    assert len(cues) == 1
    assert cues[0].start_ms == 500
    assert cues[0].end_ms == 2000
    assert cues[0].text == "VTT caption"


def test_dispatch_by_extension() -> None:
    vtt = "WEBVTT\n\n00:00.000 --> 00:01.000\nhi\n"
    assert len(parse_captions(vtt, "cap.vtt")) == 1
    with pytest.raises(SrtParseError):
        parse_captions("whatever", "cap.txt")