"""Post-render verification (FR-5) — pure geometry/math, no I/O.

Each check returns a CheckResult; geometry checks use the ASS style + wrapped
text to compute the caption box and compare it against the platform safe rect.
"""

from __future__ import annotations

from ..models import CheckResult, CheckResultLevel
from .ass import WrappedCue
from .probe import MediaInfo
from .rules import LINE_HEIGHT_FACTOR, PlatformConfig


def check_resolution(width: int, height: int, min_resolution: tuple[int, int]) -> CheckResult:
    if (width, height) == (1080, 1920):
        return CheckResult(name="resolution", result="pass", detail=f"{width}x{height}")
    if width >= min_resolution[0] and height >= min_resolution[1]:
        return CheckResult(
            name="resolution", result="warn", detail=f"{width}x{height} (below 1080x1920)"
        )
    return CheckResult(name="resolution", result="fail", detail=f"{width}x{height}")


def check_ratio(width: int, height: int, tolerance: float = 0.005) -> CheckResult:
    if height == 0:
        return CheckResult(name="ratio", result="fail", detail="zero height")
    ratio = width / height
    target = 9.0 / 16.0
    if abs(ratio - target) <= tolerance:
        return CheckResult(name="ratio", result="pass", detail=f"{ratio:.4f} ≈ 9:16")
    return CheckResult(name="ratio", result="fail", detail=f"{ratio:.4f} ≠ 9:16")


def caption_box_geometry(cfg: PlatformConfig, wrapped: list[WrappedCue]) -> tuple[float, float]:
    """(top_edge, bottom_edge) of the tallest caption box, in play-res px.

    Box: bottom sits at H - MarginV; height = max_lines × font_size × 1.2.
    """
    max_lines = max((cue.line_count for cue in wrapped), default=1)
    height = max_lines * cfg.font_size * LINE_HEIGHT_FACTOR
    bottom_edge = cfg.height - cfg.margin_v
    return bottom_edge - height, bottom_edge


def check_captions_safe(cfg: PlatformConfig, wrapped: list[WrappedCue]) -> CheckResult:
    safe_top, safe_bottom, safe_left, safe_right = cfg.safe_rect
    top_edge, bottom_edge = caption_box_geometry(cfg, wrapped)

    truncated = [cue for cue in wrapped if cue.truncated]
    if truncated:
        names = ", ".join(f"cue {cue.cue_index}" for cue in truncated[:3])
        more = f" (+{len(truncated) - 3} more)" if len(truncated) > 3 else ""
        return CheckResult(
            name="captions_safe",
            result="warn",
            detail=f"line truncated with '…' in {names}{more}",
        )

    # Horizontal fit: symmetric margins define the box span (PRD 6.2).
    tolerance = 1.0  # px, for rounding
    horizontal_ok = (
        cfg.margin_lr + tolerance >= safe_left
        and cfg.width - cfg.margin_lr - tolerance <= safe_right
    )
    vertical_ok = top_edge + tolerance >= safe_top and bottom_edge - tolerance <= safe_bottom

    if horizontal_ok and vertical_ok:
        return CheckResult(
            name="captions_safe",
            result="pass",
            detail=f"margins L/R {cfg.margin_lr}px, V {cfg.margin_v}px; box {top_edge:.0f}–{bottom_edge:.0f}px",
        )
    return CheckResult(
        name="captions_safe",
        result="fail",
        detail=f"box {top_edge:.0f}–{bottom_edge:.0f}px outside safe rect "
        f"[{safe_top:.0f}–{safe_bottom:.0f}]",
    )


def check_audio(source_has_audio: bool) -> CheckResult:
    if source_has_audio:
        return CheckResult(name="audio", result="pass", detail="audio stream present")
    return CheckResult(name="audio", result="fail", detail="no audio stream in source")


def check_duration(duration_s: float, limit_s: float) -> CheckResult:
    if duration_s <= limit_s:
        return CheckResult(name="duration", result="pass", detail=f"{duration_s:.1f}s ≤ {limit_s:.0f}s")
    return CheckResult(
        name="duration", result="warn", detail=f"{duration_s:.1f}s exceeds {limit_s:.0f}s limit"
    )


def verify(
    cfg: PlatformConfig,
    wrapped: list[WrappedCue],
    output: MediaInfo,
    source_has_audio: bool,
) -> list[CheckResult]:
    return [
        check_resolution(output.width, output.height, cfg.min_resolution),
        check_ratio(output.width, output.height),
        check_captions_safe(cfg, wrapped),
        check_audio(source_has_audio),
        check_duration(output.duration_s, cfg.duration_limit_s),
    ]