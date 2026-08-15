"""Pure SRT-generation core of the transcriber (no model, no network)."""

from __future__ import annotations

from types import SimpleNamespace

import pytest

from app.pipeline.transcriber import TranscriptionError, format_timestamp, segments_to_srt


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


# --- transcribe(): model wrapper, progress, error paths (model always mocked) ---


def test_transcribe_writes_srt_and_reports_progress(tmp_path, monkeypatch) -> None:
    from app.pipeline import transcriber

    fake_model = SimpleNamespace(
        transcribe=lambda _path, **_: (iter([_seg(0.0, 1.0, "hi"), _seg(1.0, 2.0, "there")]), None)
    )
    monkeypatch.setattr(transcriber, "_get_model", lambda: fake_model)
    monkeypatch.setattr(
        transcriber, "probe",
        lambda _p: SimpleNamespace(has_audio=True, duration_s=2.0),
    )

    srt = tmp_path / "out.srt"
    progress: list[int] = []
    count = transcriber.transcribe(tmp_path / "in.mp4", srt, on_progress=progress.append)

    assert count == 2
    text = srt.read_text()
    assert "hi" in text.lower() and "there" in text.lower()
    assert progress[-1] == 100
    assert progress == sorted(progress)  # monotonic


def test_transcribe_no_audio_raises(tmp_path, monkeypatch) -> None:
    from app.pipeline import transcriber

    monkeypatch.setattr(transcriber, "probe", lambda _p: SimpleNamespace(has_audio=False, duration_s=0))
    with pytest.raises(TranscriptionError, match="No audio track"):
        transcriber.transcribe(tmp_path / "in.mp4", tmp_path / "out.srt")


def test_transcribe_no_speech_raises(tmp_path, monkeypatch) -> None:
    from app.pipeline import transcriber

    fake_model = SimpleNamespace(transcribe=lambda _path, **_: (iter([]), None))
    monkeypatch.setattr(transcriber, "_get_model", lambda: fake_model)
    monkeypatch.setattr(
        transcriber, "probe",
        lambda _p: SimpleNamespace(has_audio=True, duration_s=5.0),
    )
    with pytest.raises(TranscriptionError, match="No speech detected"):
        transcriber.transcribe(tmp_path / "in.mp4", tmp_path / "out.srt")


def test_stack_available_false_when_whisper_missing(monkeypatch) -> None:
    import importlib.util

    from app.pipeline import transcriber

    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: None)
    assert transcriber.stack_available() is False


def test_stack_available_true_when_whisper_importable(monkeypatch) -> None:
    import importlib.util

    from app.pipeline import transcriber

    monkeypatch.setattr(importlib.util, "find_spec", lambda _name: object())
    assert transcriber.stack_available() is True
