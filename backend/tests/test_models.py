"""State model additions — additive fields must keep old state.json loadable."""

from __future__ import annotations

import json

from app.models import CaptionsInfo, JobState


def _old_state_json() -> dict:
    """A state.json exactly as persisted before the AI feature (no new fields)."""
    return {
        "job_id": "abc",
        "status": "done",
        "created_at": "2026-08-01T00:00:00+00:00",
        "input": {"filename": "x.mp4", "duration_s": 30.0, "resolution": [1080, 1920]},
        "versions": {},
        "error": None,
    }


def test_old_state_json_loads_with_defaults() -> None:
    state = JobState.model_validate_json(json.dumps(_old_state_json()))
    assert state.captions is None
    assert state.transcribe_progress == 0


def test_captions_info_roundtrip() -> None:
    state = JobState.model_validate_json(
        json.dumps(
            {**_old_state_json(), "captions": {"source": "transcribed", "cue_count": 3}}
        )
    )
    assert state.captions == CaptionsInfo(source="transcribed", cue_count=3)


def test_transcribing_status_is_valid() -> None:
    state = JobState.model_validate_json(
        json.dumps({**_old_state_json(), "status": "transcribing"})
    )
    assert state.status == "transcribing"
