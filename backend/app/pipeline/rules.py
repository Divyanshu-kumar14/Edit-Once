"""Platform rules engine: loads platforms.json and computes ASS/crop values.

Single source of truth for platform behavior (FR-3.1). Adding a platform =
adding a config entry in platforms.json — nothing else.
"""

from __future__ import annotations

import json
import math
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

from .. import config

TARGET_RATIO = 9.0 / 16.0
PLAY_WIDTH = 1080
PLAY_HEIGHT = 1920
LINE_HEIGHT_FACTOR = 1.2  # libass default line spacing approximation


@dataclass(frozen=True, slots=True)
class PlatformConfig:
    """Immutable per-platform rules. Frozen => hashable, safe to cache."""

    id: str
    width: int
    height: int
    bottom_margin: float
    right_margin: float
    top_margin: float
    font_size: int
    outline: int
    shadow: int
    max_lines: int
    max_chars_per_line: int
    duration_limit_s: float
    min_resolution: tuple[int, int]

    # -- computed values (PRD 6.2) ------------------------------------------
    @property
    def margin_v(self) -> int:
        """MarginV = round(bottom_margin * H) + font_size — caption bottom sits
        above the safe line by one font size."""
        return round(self.bottom_margin * self.height) + self.font_size

    @property
    def margin_lr(self) -> int:
        return round(self.right_margin * self.width)

    @property
    def safe_rect(self) -> tuple[float, float, float, float]:
        """(top, bottom, left, right) of the platform safe zone, in px."""
        return (
            self.top_margin * self.height,
            (1 - self.bottom_margin) * self.height,
            self.right_margin * self.width,
            (1 - self.right_margin) * self.width,
        )


@lru_cache(maxsize=1)
def load_platforms() -> dict[str, PlatformConfig]:
    """Memoized: platforms.json is static per process, but was re-read+parsed
    once per platform per job (4x per render). Cache turns that into O(1)."""
    data = json.loads(Path(config.PLATFORMS_JSON).read_text())
    return {pid: _parse_platform(pid, raw) for pid, raw in data.items()}


def load_platform(platform_id: str) -> PlatformConfig:
    return load_platforms()[platform_id]


def _parse_platform(pid: str, raw: dict[str, object]) -> PlatformConfig:
    output = raw["output"]
    safe = raw["safe_zone"]
    style = raw["caption_style"]
    min_res = raw["min_resolution"]
    return PlatformConfig(
        id=pid,
        width=int(output["width"]),
        height=int(output["height"]),
        bottom_margin=float(safe["bottom_margin"]),
        right_margin=float(safe["right_margin"]),
        top_margin=float(safe["top_margin"]),
        font_size=int(style["font_size"]),
        outline=int(style["outline"]),
        shadow=int(style["shadow"]),
        max_lines=int(style["max_lines"]),
        max_chars_per_line=int(style["max_chars_per_line"]),
        duration_limit_s=float(raw["duration_limit_s"]),
        min_resolution=(int(min_res[0]), int(min_res[1])),
    )


# --- crop math (FR-4.1) ------------------------------------------------------


@dataclass(frozen=True, slots=True)
class CropWindow:
    x: int
    y: int
    w: int
    h: int


def _even(value: float) -> int:
    """Round down to nearest even integer (yuv420p needs even dims)."""
    return int(value) & ~1


def crop_window(
    cfg: PlatformConfig,
    input_w: int,
    input_h: int,
    anchor_x: float = 0.5,
    anchor_y: float = 0.5,
) -> CropWindow | None:
    """Largest 9:16 window inside the input, positioned by anchor fractions.

    Returns None when the input is already (≈) 9:16 — no crop needed (PRD 6.3).
    """
    if input_w <= 0 or input_h <= 0:
        return None
    ratio = input_w / input_h
    if abs(ratio - TARGET_RATIO) < 1e-3:
        return None

    if ratio > TARGET_RATIO:  # wider than 9:16: crop width
        w = _even(input_h * TARGET_RATIO)
        h = input_h
        x = _clamp(round(anchor_x * (input_w - w)), 0, input_w - w)
        y = 0
    else:  # taller than 9:16: crop height
        w = input_w
        h = _even(input_w / TARGET_RATIO)
        x = 0
        y = _clamp(round(anchor_y * (input_h - h)), 0, input_h - h)
    return CropWindow(x=x, y=y, w=w, h=h)


def _clamp(value: int, lo: int, hi: int) -> int:
    return max(lo, min(hi, value))


# --- caption fit math (PRD 6.2) ----------------------------------------------


def usable_width_px(cfg: PlatformConfig) -> int:
    """Width available for text between the (symmetric) margins."""
    return cfg.width - 2 * cfg.margin_lr


def max_chars_fit(cfg: PlatformConfig) -> int:
    """Largest line (in latin-char units) that fits the usable width.
    Latin char ≈ 0.5 × font_size px; CJK ≈ 1.0 × font_size (PRD 6.2)."""
    if cfg.font_size <= 0:
        return cfg.max_chars_per_line
    return max(1, math.floor(usable_width_px(cfg) / (0.5 * cfg.font_size)))


def max_line_units(cfg: PlatformConfig) -> int:
    """Effective per-line cap: min(config cap, what actually fits)."""
    return min(cfg.max_chars_per_line, max_chars_fit(cfg))


def text_units(text: str) -> int:
    """Width of text in latin-char units: CJK chars count double."""
    return sum(2 if ord(ch) > 0x2E80 else 1 for ch in text)