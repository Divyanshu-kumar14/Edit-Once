"""SRT/VTT parsing (pure functions) and per-platform ASS generation.

Parser contract (FR-1.2 / NFR-6):
- accepts SRT (LF or CRLF, optional BOM) and VTT (header + optional NOTE blocks)
- raises SrtParseError carrying the offending line number
- rejects files with more than MAX_CUES cues
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from pathlib import Path

from .. import config
from .rules import PlatformConfig, max_line_units, text_units

_TIMESTAMP_RE = re.compile(
    r"^(?:(?P<h>\d{1,2}):)?(?P<m>\d{2}):(?P<s>\d{2})[,\.](?P<ms>\d{3})$"
)


class SrtParseError(ValueError):
    def __init__(self, line: int, message: str) -> None:
        super().__init__(f"line {line}: {message}")
        self.line = line
        self.message = message


@dataclass(slots=True)
class Cue:
    start_ms: int
    end_ms: int
    lines: list[str]  # raw text lines (may contain <i>/<b> tags from SRT)
    index: int = 0

    @property
    def text(self) -> str:
        return "\n".join(self.lines)


def _parse_timestamp(raw: str) -> int:
    """'00:01:02,500' or '01:02.500' (VTT) -> milliseconds. Raises ValueError."""
    match = _TIMESTAMP_RE.match(raw.strip())
    if match is None:
        raise ValueError(f"invalid timestamp '{raw.strip()}'")
    h = int(match.group("h") or 0)
    m = int(match.group("m"))
    s = int(match.group("s"))
    ms = int(match.group("ms"))
    return ((h * 60 + m) * 60 + s) * 1000 + ms


def _parse_block(block: str, first_line_no: int, expect_index: bool) -> Cue:
    """Parse one caption block; first_line_no is the 1-based line of block start."""
    lines = block.split("\n")
    cursor = 0

    # Optional numeric index (SRT has it; VTT does not).
    if expect_index:
        if not lines or not lines[0].strip().isdigit():
            raise SrtParseError(first_line_no, "expected caption index number")
        cursor = 1

    # Find the timing line.
    while cursor < len(lines) and "-->" not in lines[cursor]:
        cursor += 1
    if cursor >= len(lines):
        raise SrtParseError(first_line_no + cursor, "missing timestamp line (-->)")
    timing_line = cursor
    parts = lines[cursor].split("-->")
    if len(parts) != 2:
        raise SrtParseError(first_line_no + timing_line, "malformed timestamp line")
    try:
        start_ms = _parse_timestamp(parts[0])
        end_ms = _parse_timestamp(parts[1].split()[0])  # VTT may have cue settings after
    except ValueError as exc:
        raise SrtParseError(first_line_no + timing_line, str(exc)) from exc
    if end_ms <= start_ms:
        raise SrtParseError(first_line_no + timing_line, "end timestamp must be after start")

    text_lines = [ln for ln in lines[timing_line + 1 :] if ln.strip() != ""]
    return Cue(start_ms=start_ms, end_ms=end_ms, lines=text_lines)


def parse_srt(text: str) -> list[Cue]:
    """Parse SRT text into cues. Raises SrtParseError with line numbers."""
    text = text.lstrip("\ufeff")  # strip BOM (FR-1.1)
    text = text.replace("\r\n", "\n").replace("\r", "\n")
    blocks = text.split("\n\n")

    cues: list[Cue] = []
    line_no = 1
    for block in blocks:
        block = block.strip("\n")
        if block.strip() == "":
            line_no += 1  # preserve line numbering across empty separators
            continue
        cue = _parse_block(block, line_no, expect_index=True)
        cue.index = len(cues) + 1
        cues.append(cue)
        line_no += block.count("\n") + 2  # block lines + blank separator

    if len(cues) > config.MAX_CUES:
        raise SrtParseError(0, f"too many cues ({len(cues)} > {config.MAX_CUES} limit)")
    if not cues:
        raise SrtParseError(0, "no caption cues found")
    return cues


def parse_vtt(text: str) -> list[Cue]:
    """Parse VTT text into cues (header + NOTE blocks skipped)."""
    text = text.lstrip("\ufeff").replace("\r\n", "\n").replace("\r", "\n")
    if not text.startswith("WEBVTT"):
        raise SrtParseError(1, "not a VTT file (missing WEBVTT header)")

    lines = text.split("\n")
    # Skip the WEBVTT header + any NOTE blocks (multi-line comments).
    body: list[str] = []
    i = 0
    header_done = False
    while i < len(lines):
        line = lines[i]
        if not header_done:
            if line.strip() == "":
                header_done = True
            i += 1
            continue
        if line.strip().startswith("NOTE"):
            while i < len(lines) and lines[i].strip() != "":
                i += 1
        else:
            body.append(line)
            i += 1

    blocks = "\n".join(body).split("\n\n")
    cues: list[Cue] = []
    line_no = 1
    for block in blocks:
        block = block.strip("\n")
        if block.strip() == "":
            line_no += 1
            continue
        cue = _parse_block(block, line_no, expect_index=False)
        cue.index = len(cues) + 1
        cues.append(cue)
        line_no += block.count("\n") + 2

    if len(cues) > config.MAX_CUES:
        raise SrtParseError(0, f"too many cues ({len(cues)} > {config.MAX_CUES} limit)")
    if not cues:
        raise SrtParseError(0, "no caption cues found")
    return cues


def parse_captions(text: str, filename: str) -> list[Cue]:
    """Dispatch on extension: .srt -> SRT parser, .vtt -> VTT parser."""
    ext = Path(filename).suffix.lower()
    if ext == ".vtt":
        return parse_vtt(text)
    if ext == ".srt":
        return parse_srt(text)
    raise SrtParseError(0, f"unsupported caption format '{ext}'")


# ---------------------------------------------------------------------------
# ASS generation (FR-3.4, PRD 6.2)


@dataclass(slots=True)
class WrappedCue:
    cue_index: int
    lines: list[str]
    truncated: bool  # line truncated with "…" -> checklist WARN, not FAIL

    @property
    def line_count(self) -> int:
        return len(self.lines)


def ms_to_ass_time(ms: int) -> str:
    """Milliseconds -> ASS timecode h:mm:ss.cc (centiseconds)."""
    ms = max(0, int(ms))
    total_cs = ms // 10
    cs = total_cs % 100
    total_s = total_cs // 100
    s = total_s % 60
    m = (total_s // 60) % 60
    h = total_s // 3600
    return f"{h}:{m:02d}:{s:02d}.{cs:02d}"


def _strip_inline_tags(text: str) -> str:
    """Remove SRT/VTT inline markup (<i>, <b>, <font …>) — libass uses ASS tags."""
    return re.sub(r"<[^>]+>", "", text)


def wrap_text(text: str, max_units: int, max_lines: int) -> tuple[list[str], bool]:
    """Word-wrap text into lines of at most max_units (latin/CJK units, PRD 6.2).

    Returns (lines, truncated) — when the wrapped text exceeds max_lines the
    last line is cut and marked with '…' (PRD 6.2: never silently drop).

    Complexity: O(n) — unit counts are accumulated, never recomputed (the naive
    "units(current + ' ' + word)" per word is O(n²) on long captions).
    """
    words = text.split()
    lines: list[str] = []
    current = ""
    current_units = 0

    for word in words:
        word_units = text_units(word)
        if word_units > max_units:
            # Hard-split a single over-long word, walking chars exactly once.
            buffer = ""
            buffer_units = 0
            for ch in word:
                w = 2 if ord(ch) > 0x2E80 else 1
                if buffer and buffer_units + w > max_units:
                    lines.append(buffer)
                    buffer = ""
                    buffer_units = 0
                buffer += ch
                buffer_units += w
            word = buffer
            word_units = buffer_units
        sep = 1 if current else 0  # single space between words
        if current_units + sep + word_units <= max_units:
            current = f"{current} {word}" if current else word
            current_units += sep + word_units
        else:
            if current:
                lines.append(current)
            current = word
            current_units = word_units

    if current:
        lines.append(current)

    truncated = len(lines) > max_lines
    if truncated:
        lines = lines[:max_lines]
        last = lines[-1]
        while text_units(last) + 1 > max_units and last:
            last = last[:-1]
        lines[-1] = last + "…"
    return lines, truncated


def wrap_cue(cue: Cue, max_units: int, max_lines: int) -> WrappedCue:
    text = _strip_inline_tags(cue.text).replace("\n", " ")
    lines, truncated = wrap_text(text, max_units, max_lines)
    return WrappedCue(cue_index=cue.index, lines=lines, truncated=truncated)


def _dialogue_line(cue: Cue, wrapped: WrappedCue, duration_ms: int) -> str:
    end_ms = min(cue.end_ms, duration_ms)  # clamp cue end to video duration (PRD 6.2)
    text = "\\N".join(wrapped.lines)
    text = text.replace("{", "\\{").replace("}", "\\}")
    return (
        f"Dialogue: 0,{ms_to_ass_time(cue.start_ms)},{ms_to_ass_time(end_ms)},"
        f"Caption,,0,0,0,,{text}"
    )


def build_ass(
    cfg: PlatformConfig, cues: list[Cue], duration_s: float
) -> tuple[str, list[WrappedCue]]:
    """Generate the full ASS document for one platform (PRD 6.2).

    Returns (ass_text, wrapped_cues) — wrapped cues feed the verifier.
    """
    max_units = max_line_units(cfg)
    duration_ms = int(duration_s * 1000)
    wrapped = [wrap_cue(cue, max_units, cfg.max_lines) for cue in cues]

    header = (
        "[Script Info]\n"
        "ScriptType: v4.00+\n"
        f"PlayResX: {cfg.width}\n"
        f"PlayResY: {cfg.height}\n"
        "WrapStyle: 2\n"
        "\n"
        "[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Caption,{config.FONT_NAME},{cfg.font_size},&H00FFFFFF,&H00FFFFFF,"
        f"&H00000000,&H00000000,0,0,0,0,100,100,0,0,1,{cfg.outline},{cfg.shadow},"
        f"2,{cfg.margin_lr},{cfg.margin_lr},{cfg.margin_v},1\n"
        "\n"
        "[Events]\n"
        "Format: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )
    dialogues = "\n".join(
        _dialogue_line(cue, w, duration_ms) for cue, w in zip(cues, wrapped)
    )
    return header + dialogues + "\n", wrapped