"""Local speech-to-text caption generation (faster-whisper).

Transcription is a front stage in the job pipeline: probe -> transcribe ->
analyze -> render -> verify. The generated captions are written to the same
in.srt file the rest of the pipeline already reads, so nothing downstream
changes. faster-whisper is imported lazily so the app boots (and the
SRT-upload path works) even when the whisper stack is missing.
"""

from __future__ import annotations

from pathlib import Path


class TranscriptionError(RuntimeError):
    """User-facing failure for auto-captioning (no audio / no speech / stack missing)."""


def format_timestamp(ms: float) -> str:
    """Milliseconds -> SRT timestamp `HH:MM:SS,mmm` (clamped at zero)."""
    ms = max(0, round(ms))
    h, rem = divmod(ms, 3_600_000)
    m, rem = divmod(rem, 60_000)
    s, ms = divmod(rem, 1000)
    return f"{h:02d}:{m:02d}:{s:02d},{ms:03d}"


def segments_to_srt(segments) -> str:
    """Whisper segments -> SRT text. Pure function: any iterable of objects
    with .start/.end (seconds) and .text works. Blank segments are dropped;
    text is whitespace-collapsed and first-letter-capitalized."""
    blocks: list[str] = []
    n = 0
    for seg in segments:
        text = " ".join((seg.text or "").split())
        if not text:
            continue
        n += 1
        text = text[0].upper() + text[1:]
        blocks.append(
            f"{n}\n{format_timestamp(seg.start * 1000)} --> "
            f"{format_timestamp(seg.end * 1000)}\n{text}"
        )
    return "\n\n".join(blocks) + ("\n" if blocks else "")
