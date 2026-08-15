"""Local speech-to-text caption generation (faster-whisper).

Transcription is a front stage in the job pipeline: probe -> transcribe ->
analyze -> render -> verify. The generated captions are written to the same
in.srt file the rest of the pipeline already reads, so nothing downstream
changes. faster-whisper is imported lazily so the app boots (and the
SRT-upload path works) even when the whisper stack is missing.
"""

from __future__ import annotations

from pathlib import Path

from .. import config
from .probe import probe


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


_MODEL = None


def _get_model():
    """Lazy process-wide singleton. Raises TranscriptionError with setup
    guidance when the stack or the model file is missing."""
    global _MODEL
    if _MODEL is None:
        try:
            from faster_whisper import WhisperModel
        except ImportError as exc:
            raise TranscriptionError(
                "Auto-captioning unavailable — faster-whisper is not installed. "
                "Run scripts/setup.sh, or upload an SRT caption file instead."
            ) from exc
        try:
            _MODEL = WhisperModel(
                config.WHISPER_MODEL,
                device=config.WHISPER_DEVICE,
                compute_type=config.WHISPER_COMPUTE_TYPE,
            )
        except Exception as exc:  # noqa: BLE001 — any load failure gets the same guidance
            raise TranscriptionError(
                f"Could not load the caption model ({config.WHISPER_MODEL}). "
                "Run scripts/setup.sh to download it, or upload an SRT instead."
            ) from exc
    return _MODEL


def stack_available() -> bool:
    """True when faster-whisper is importable (health check).

    Deliberately does NOT load the model — loading can download ~150 MB and
    must not happen inside a health probe. A missing model is surfaced by
    the transcribe error path instead (setup.sh pre-downloads it)."""
    import importlib.util

    return importlib.util.find_spec("faster_whisper") is not None


def transcribe(audio_path: Path, srt_path: Path, on_progress=None) -> int:
    """Transcribe audio to SRT at srt_path; returns the cue count.

    Progress is approximated from the last segment end / total duration
    (Whisper reports no fractional progress on CPU); 100 is sent at the end.
    """
    info = probe(audio_path)
    if not info.has_audio:
        raise TranscriptionError(
            "No audio track found — can't auto-generate captions. Upload an SRT instead."
        )

    model = _get_model()
    segments, _seg_info = model.transcribe(str(audio_path), vad_filter=True)

    collected = []
    for seg in segments:
        collected.append(seg)
        if on_progress is not None and info.duration_s > 0:
            on_progress(min(99, int(seg.end / info.duration_s * 100)))

    text = segments_to_srt(collected)
    if not text:
        raise TranscriptionError("No speech detected in audio — upload an SRT instead.")

    srt_path.write_text(text, encoding="utf-8")
    if on_progress is not None:
        on_progress(100)
    return text.count("\n\n") + (1 if text.strip() else 0)
