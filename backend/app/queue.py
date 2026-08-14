"""JobManager: enqueue jobs, run the pipeline on a single worker thread,
persist state to data/jobs/{job_id}/state.json (FR-2.5, NFR-3)."""

from __future__ import annotations

import json
import queue
import shutil
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path

from . import config
from .models import InputInfo, JobState, VersionState
from .pipeline import rules
from .pipeline.probe import ProbeError, probe


def _platform_ids() -> list[str]:
    """Platform keys from platforms.json (single source of truth, FR-3.1)."""
    return list(rules.load_platforms())  # lru_cached: O(1) after first load


class JobError(RuntimeError):
    """Raised for user-facing job failures."""


class JobManager:
    def __init__(self, jobs_dir: Path | None = None) -> None:
        self._jobs_dir = jobs_dir or config.JOBS_DIR
        self._queue: queue.Queue[str] = queue.Queue()
        # In-memory job cache: the UI polls every 2s; disk read + JSON parse
        # per poll was wasteful. Disk stays the source of truth (restarts),
        # the cache makes get() an O(1) dict hit after the first load.
        self._cache: dict[str, JobState] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="job-worker", daemon=True)

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        if self._thread.is_alive():
            return  # already running (tests may re-enter lifespan)
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="job-worker", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        self._queue.put("__stop__")  # unblock the worker

    def is_running(self) -> bool:
        return self._thread.is_alive()

    # -- job creation / polling ---------------------------------------------
    def create_job(self, video_path: Path, srt_bytes: bytes, filename: str) -> JobState:
        job_id = str(uuid.uuid4())
        job_dir = self._jobs_dir / job_id
        job_dir.mkdir(parents=True, exist_ok=False)
        # shutil.copyfile streams in fixed-size chunks — no 200 MB byte string
        # in memory (uploads are already spooled to a temp file by the API).
        shutil.copyfile(video_path, job_dir / "in.mp4")
        (job_dir / "in.srt").write_bytes(srt_bytes)

        state = JobState(
            job_id=job_id,
            status="queued",
            created_at=datetime.now(timezone.utc).isoformat(),
            input=InputInfo(filename=filename, duration_s=0.0, resolution=(0, 0)),
            versions={
                platform: VersionState(status="queued")
                for platform in _platform_ids()
            },
        )
        self._persist(state)
        self._queue.put(job_id)
        return state

    def get(self, job_id: str) -> JobState | None:
        """Snapshot of job state for API responses.

        Returns a deep copy of the cached object so readers never observe a
        torn write from the worker thread (same atomicity the old disk reads
        gave via tmp+rename, without the I/O)."""
        live = self._load(job_id)
        return live.model_copy(deep=True) if live is not None else None

    def _load(self, job_id: str) -> JobState | None:
        """Live state object: cached copy (O(1)) or first load from disk —
        disk is the source of truth, survives restarts (FR-2.5)."""
        cached = self._cache.get(job_id)
        if cached is not None:
            return cached
        state_path = self._jobs_dir / job_id / "state.json"
        if not state_path.exists():
            return None
        try:
            state = JobState.model_validate_json(state_path.read_text())
        except (json.JSONDecodeError, ValueError):
            return None
        self._cache[job_id] = state
        return state

    def job_path(self, job_id: str) -> Path:
        return self._jobs_dir / job_id

    # -- persistence ---------------------------------------------------------
    def _persist(self, state: JobState) -> None:
        # Keep the cache in sync so get() stays O(1) (tmp+rename = atomic disk write)
        self._cache[state.job_id] = state
        path = self._jobs_dir / state.job_id / "state.json"
        tmp = path.with_suffix(".json.tmp")
        tmp.write_text(state.model_dump_json(indent=2))
        tmp.replace(path)

    # -- worker ---------------------------------------------------------------
    def _run(self) -> None:
        while not self._stop.is_set():
            try:
                job_id = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if job_id == "__stop__":
                break
            try:
                self._run_job(job_id)
            except Exception as exc:  # whole-job failure (FR-2.4)
                state = self._load(job_id)
                if state is not None:
                    state.status = "failed"
                    state.error = str(exc)[:500]
                    self._persist(state)

    def _run_job(self, job_id: str) -> None:
        # _load (not get): the worker must mutate the LIVE object so cache +
        # disk stay consistent; get() would hand it a throwaway copy.
        state = self._load(job_id)
        if state is None:
            return

        # --- analyze: probe input ---
        state.status = "analyzing"
        self._persist(state)
        job_dir = self.job_path(job_id)
        try:
            info = probe(job_dir / "in.mp4")
        except ProbeError as exc:
            state.status = "failed"
            state.error = str(exc)
            self._persist(state)
            return

        state.input = InputInfo(
            filename=state.input.filename if state.input else "",
            duration_s=info.duration_s,
            resolution=(info.width, info.height),
        )
        self._persist(state)

        # --- render + verify per platform (Phases 2-3) ---
        self._render_versions(state, info)

    def _render_versions(self, state: JobState, info) -> None:
        """Render + verify each platform sequentially (FR-2.3).

        A failed platform render does NOT fail the job — that platform shows
        'failed' + stderr tail; the others continue (FR-2.4).
        """
        from .models import SpecInfo, VersionState
        from .pipeline import analyzer, ass, renderer, rules, stills, verifier

        platforms = rules.load_platforms()
        state.status = "rendering"
        self._persist(state)

        job_dir = self.job_path(state.job_id)
        cues = ass.parse_captions(
            (job_dir / "in.srt").read_text(encoding="utf-8"), "in.srt"
        )
        scenes = analyzer.analyze_scenes(job_dir / "in.mp4", info)
        anchor = scenes[0] if scenes else None
        anchor_x = anchor.anchor_x if anchor else 0.5
        anchor_y = anchor.anchor_y if anchor else 0.5

        for pid, cfg in platforms.items():
            version = state.versions.get(pid) or VersionState(status="queued")
            state.versions[pid] = version
            version.status = "rendering"
            version.progress = 5
            self._persist(state)

            def progress(pct: int, version=version) -> None:
                version.progress = pct
                self._persist(state)

            try:
                ass_text, wrapped = ass.build_ass(cfg, cues, info.duration_s)
                ass_path = job_dir / f"{pid}.ass"
                ass_path.write_text(ass_text)

                crop = rules.crop_window(cfg, info.width, info.height, anchor_x, anchor_y)
                vf = renderer.build_vf(crop, ass_path, config.FONTS_DIR)
                renderer.render(job_dir, pid, vf, info.duration_s, on_progress=progress)

                version.progress = 100
                version.status = "done"
                output = probe(job_dir / "versions" / f"{pid}.mp4")
                version.checks = verifier.verify(cfg, wrapped, output, info.has_audio)
                version.spec = SpecInfo(
                    width=output.width,
                    height=output.height,
                    duration_s=output.duration_s,
                    margins={
                        "bottom": cfg.bottom_margin,
                        "right": cfg.right_margin,
                        "top": cfg.top_margin,
                    },
                )
                version.download_url = f"/api/jobs/{state.job_id}/versions/{pid}"
                # Stills are non-fatal (FR-6.1): a failure only leaves fewer previews.
                try:
                    still_paths = stills.extract_stills(
                        job_dir, pid, output.duration_s, [cue.start_ms for cue in cues]
                    )
                    version.stills = [
                        f"/api/jobs/{state.job_id}/stills/{pid}/{i}"
                        for i in range(len(still_paths))
                    ]
                except Exception:
                    version.stills = []
                self._persist(state)
            except Exception as exc:  # platform-level failure only (FR-2.4)
                version.status = "failed"
                version.error = str(exc)[:500]
                self._persist(state)

        state.status = "done"
        self._persist(state)


def ffmpeg_available() -> tuple[str | None, bool]:
    """Return (ffmpeg version string | None, libass subtitles filter present)."""
    ffmpeg = shutil.which("ffmpeg")
    if ffmpeg is None:
        return None, False
    try:
        version = shutil.os.popen(f"{ffmpeg} -version").read().splitlines()[0].split()[2]
    except Exception:
        version = "unknown"
    try:
        filters = shutil.os.popen(f"{ffmpeg} -filters").read()
        return version, "subtitles" in filters
    except Exception:
        return version, False