"""OpenCV Haar frontal-face detection (FR-4.2).

The cascade XML is bundled in backend/assets because OpenCV's data package
no longer ships detectors in every release — bundling makes detection
deterministic with zero runtime downloads. The cascade is loaded once and
reused (Haar loading is the slow part, not detection).
"""

from __future__ import annotations

from functools import lru_cache

import cv2

from .. import config


class FaceDetectorError(RuntimeError):
    """Cascade file missing or unloadable."""


@lru_cache(maxsize=1)
def _cascade() -> cv2.CascadeClassifier:
    """Load the frontal-face cascade exactly once per process."""
    path = config.ASSETS_DIR / "haarcascade_frontalface_default.xml"
    if not path.exists():
        raise FaceDetectorError(f"face cascade missing: {path}")
    cascade = cv2.CascadeClassifier(str(path))
    if cascade.empty():
        raise FaceDetectorError(f"face cascade failed to load: {path}")
    return cascade


def detect_faces(frame_bgr) -> list[tuple[int, int, int, int]]:
    """Return [(x, y, w, h)] face boxes in pixel coords, empty when none.

    Deterministic: same frame in -> same boxes out (no tracking/smoothing,
    per FR-4.2). Scale the frame down when it is huge so detection cost stays
    bounded (~0.5 s per frame on 1080p).
    """
    gray = cv2.cvtColor(frame_bgr, cv2.COLOR_BGR2GRAY)
    h, w = gray.shape
    scale = 1.0
    if w > 1280:
        scale = 1280.0 / w
        gray = cv2.resize(gray, (1280, int(h * scale)), interpolation=cv2.INTER_AREA)
    faces = _cascade().detectMultiScale(gray, scaleFactor=1.1, minNeighbors=5, minSize=(40, 40))
    if scale != 1.0:
        inv = 1.0 / scale
        return [(int(x * inv), int(y * inv), int(w2 * inv), int(h2 * inv)) for x, y, w2, h2 in faces]
    return [tuple(map(int, f)) for f in faces]


def face_center(frame_bgr) -> tuple[float, float] | None:
    """Normalized (x, y) center of the LARGEST face, or None if none detected."""
    faces = detect_faces(frame_bgr)
    if not faces:
        return None
    largest = max(faces, key=lambda f: f[2] * f[3])
    x, y, w, h = largest
    return ((x + w / 2) / frame_bgr.shape[1], (y + h / 2) / frame_bgr.shape[0])