"""Pydantic schemas for job/version state persisted to data/jobs/{id}/state.json."""

from __future__ import annotations

from typing import Literal

from pydantic import BaseModel

CheckResultName = Literal["resolution", "ratio", "captions_safe", "audio", "duration"]
CheckResultLevel = Literal["pass", "warn", "fail"]


class CheckResult(BaseModel):
    name: CheckResultName
    result: CheckResultLevel
    detail: str


class SpecInfo(BaseModel):
    """Per-version spec summary shown in the UI (FR-7.2)."""

    width: int
    height: int
    duration_s: float
    margins: dict[str, float]  # bottom/right/top margin fractions


class VersionState(BaseModel):
    status: Literal["queued", "rendering", "done", "failed"]
    progress: int = 0  # 0..100
    error: str | None = None  # stderr tail (500 chars) on failure
    checks: list[CheckResult] = []
    stills: list[str] = []  # api paths
    download_url: str | None = None
    spec: SpecInfo | None = None


class InputInfo(BaseModel):
    filename: str
    duration_s: float
    resolution: tuple[int, int]  # (width, height) of source


class JobState(BaseModel):
    job_id: str
    status: Literal["queued", "analyzing", "rendering", "done", "failed"]
    created_at: str  # ISO-8601
    input: InputInfo | None = None
    versions: dict[str, VersionState] = {}
    error: str | None = None  # whole-job failure (e.g. analysis crash)