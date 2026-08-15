"""Job state persistence: concurrent writers must never crash.

Regression: `_persist()` wrote every save to one fixed tmp path
(state.json.tmp). When the worker thread and an API thread persisted the
same job at the same moment, the first os.replace() moved the shared tmp
file away and the second crashed with FileNotFoundError — surfaced as a
500 in production and as a flaky full-suite run.
"""

from __future__ import annotations

import json
import threading
from datetime import datetime, timezone
from pathlib import Path

from app.models import JobState
from app.queue import JobManager


def _job(job_id: str) -> JobState:
    return JobState(
        job_id=job_id,
        status="rendering",
        created_at=datetime.now(timezone.utc).isoformat(),
    )


def test_concurrent_persist_writers_never_crash(data_dir: Path) -> None:
    """Two threads persisting the same job must both complete and leave
    valid JSON on disk — the fixed-tmp-path race used to raise
    FileNotFoundError inside os.replace."""
    manager = JobManager(jobs_dir=data_dir)
    state = _job("race-job")
    (data_dir / "race-job").mkdir()  # create_job() does this in production
    errors: list[BaseException] = []

    def writer() -> None:
        for _ in range(200):
            try:
                manager._persist(state)
            except BaseException as exc:  # noqa: BLE001 - collect any race failure
                errors.append(exc)
                return

    threads = [threading.Thread(target=writer) for _ in range(2)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()

    assert errors == [], f"concurrent _persist crashed: {errors[0]!r}"
    on_disk = json.loads((data_dir / "race-job" / "state.json").read_text())
    assert on_disk["job_id"] == "race-job"
