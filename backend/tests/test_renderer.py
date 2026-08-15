"""Renderer filter-chain tests — anchored crop vs blur-pad (FR-3.3, FR-4)."""

from __future__ import annotations

from pathlib import Path

from app.pipeline.renderer import build_vf
from app.pipeline.rules import CropWindow, load_platforms

ASS = Path("/tmp/example.ass")
FONTS = Path("/tmp/fonts")


def test_crop_vf_unchanged_default() -> None:
    crop = CropWindow(w=608, h=1080, x=100, y=0)
    vf = build_vf(crop, ASS, FONTS)
    assert "crop=w=608:h=1080:x=100:y=0" in vf
    assert "scale=1080:1920" in vf
    assert "subtitles=" in vf
    assert "gblur" not in vf and "overlay" not in vf


def test_blur_vf_pads_without_crop() -> None:
    vf = build_vf(None, ASS, FONTS, fit="blur")
    assert "split=2[a][b]" in vf
    assert "gblur=sigma=24" in vf
    assert "overlay=(W-w)/2:(H-h)/2" in vf
    # The only crop is the background fill; no anchored content crop.
    assert "crop=w=" not in vf
    assert "subtitles=" in vf


def test_blur_ignores_crop_argument() -> None:
    crop = CropWindow(w=608, h=1080, x=100, y=0)
    vf = build_vf(crop, ASS, FONTS, fit="blur")
    assert "crop=w=" not in vf  # blur-pad never hard-crops (FR-3.3)


def test_blur_and_crop_share_subtitles() -> None:
    assert "subtitles=" in build_vf(None, ASS, FONTS, fit="blur")
    assert "subtitles=" in build_vf(None, ASS, FONTS, fit="crop")