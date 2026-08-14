"""Rules engine tests: config load, margin/crop math, char-fit math (PRD 6)."""

from __future__ import annotations

from app.pipeline.rules import (
    PlatformConfig,
    crop_window,
    load_platforms,
    max_chars_fit,
    max_line_units,
    text_units,
    usable_width_px,
)


def test_loads_all_four_platforms() -> None:
    platforms = load_platforms()
    assert set(platforms) == {"tiktok", "reels", "shorts", "x"}


def test_margin_values_exact_per_platform() -> None:
    """PRD 6.2: MarginV = round(bottom*1920) + 64; MarginL/R = round(right*1080)."""
    expected = {
        "tiktok": (410, 162),   # round(0.18*1920)=346 +64; round(0.15*1080)=162
        "reels": (640, 162),    # round(0.30*1920)=576 +64
        "shorts": (448, 270),   # round(0.20*1920)=384 +64; round(0.25*1080)=270
        "x": (352, 108),        # round(0.15*1920)=288 +64; round(0.10*1080)=108
    }
    platforms = load_platforms()
    for pid, (margin_v, margin_lr) in expected.items():
        cfg = platforms[pid]
        assert cfg.margin_v == margin_v, pid
        assert cfg.margin_lr == margin_lr, pid


def test_usable_width_and_char_fit() -> None:
    tiktok = load_platforms()["tiktok"]
    assert usable_width_px(tiktok) == 1080 - 2 * 162
    # latin ≈ 0.5 * 64 = 32 px/char -> 756/32 = 23.6 -> 23, capped at 18 by config
    assert max_chars_fit(tiktok) == 23
    assert max_line_units(tiktok) == 18

    shorts = load_platforms()["shorts"]
    # usable 1080 - 540 = 540 -> 540/32 = 16.875 -> 16 (config cap 18 not binding)
    assert max_line_units(shorts) == 16


def test_text_units_latin_vs_cjk() -> None:
    assert text_units("abc") == 3
    assert text_units("你好") == 4  # CJK chars are 2 units each
    assert text_units("a你") == 3


def test_crop_9x16_input_returns_none() -> None:
    cfg = load_platforms()["tiktok"]
    assert crop_window(cfg, 1080, 1920) is None
    assert crop_window(cfg, 1350, 2400) is None  # same ratio, bigger


def test_crop_16x9_input_center() -> None:
    cfg = load_platforms()["tiktok"]
    win = crop_window(cfg, 1920, 1080)
    assert win is not None
    assert win.w == 606  # floor(1080*9/16)=607.5 -> even 606
    assert win.h == 1080
    assert win.y == 0
    assert win.x == (1920 - 606) // 2  # 657
    assert win.w % 2 == 0 and win.h % 2 == 0


def test_crop_anchor_offsets_window() -> None:
    cfg = load_platforms()["tiktok"]
    left = crop_window(cfg, 1920, 1080, anchor_x=0.0)
    right = crop_window(cfg, 1920, 1080, anchor_x=1.0)
    assert left is not None and right is not None
    assert left.x == 0
    assert right.x == 1920 - 606
    assert left.x < right.x


def test_crop_square_input() -> None:
    cfg = load_platforms()["tiktok"]
    win = crop_window(cfg, 1080, 1080)  # square is WIDER than 9:16 -> crop width
    assert win is not None
    assert win.w == 606  # floor(1080*9/16)=607.5 -> even 606
    assert win.h == 1080
    assert win.x == (1080 - 606) // 2  # 237
    assert win.y == 0


def test_min_resolution_and_limits() -> None:
    platforms = load_platforms()
    assert platforms["reels"].duration_limit_s == 180
    assert platforms["x"].duration_limit_s == 140
    assert platforms["tiktok"].duration_limit_s == 600
    assert platforms["shorts"].min_resolution == (720, 1280)


def test_platform_config_frozen() -> None:
    cfg = PlatformConfig(
        id="t", width=1080, height=1920, bottom_margin=0.18, right_margin=0.15,
        top_margin=0.05, font_size=64, outline=3, shadow=1, max_lines=3,
        max_chars_per_line=18, duration_limit_s=600, min_resolution=(720, 1280),
    )
    assert cfg.margin_v == 410
    assert cfg.safe_rect == (96.0, 1574.4, 162.0, 918.0)