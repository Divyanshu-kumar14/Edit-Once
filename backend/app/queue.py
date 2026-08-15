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
from .models import InputInfo, JobState, SpecInfo, VersionState
from .pipeline import analyzer, ass, renderer, rules, stills, verifier
from .pipeline.probe import MediaInfo, ProbeError, probe


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
        # Memoized per-job analysis (probe + SRT parse + scene/face anchors).
        # Re-renders (FR-4.3) call _prepare(); without this cache every drag
        # or fit toggle would re-decode the WHOLE video — Haar on every 2 s
        # sample, ~0.5 s/frame on 1080p — even though the inputs (in.mp4,
        # in.srt) are immutable once the job is created. Keyed by job_id;
        # entries are tiny (<a few KB), jobs are never deleted in this app.
        self._analysis_cache: dict[str, tuple[MediaInfo, list, tuple[float, float] | None]] = {}
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, name="job-worker", daemon=True)

    # -- lifecycle ----------------------------------------------------------
    def start(self) -> None:
        self._jobs_dir.mkdir(parents=True, exist_ok=True)
        if self._thread.is_alive():
            # A previous stop() may still be draining the last render. Wait
            # (bounded) for it to exit so a fresh worker can spawn — tests
            # re-enter the lifespan and would otherwise lose their worker.
            self._thread.join(timeout=10)
            if self._thread.is_alive():
                return  # long render in flight; it will drain queued work
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
        self._queue.put(("job", job_id))
        return state

    def update_version_options(
        self,
        job_id: str,
        platform: str,
        fit: str,
        anchor: tuple[float, float] | None,
    ) -> JobState | None:
        """Apply per-version options and re-render ONLY that platform (FR-4.3).

        The other three versions are untouched — re-renders must never
        invalidate work the user already approved.
        """
        state = self._load(job_id)
        if state is None or platform not in state.versions:
            return None
        version = state.versions[platform]
        version.fit = fit
        # Clamp to 0..1: drag coordinates can drift a pixel outside.
        if anchor is not None:
            anchor = (min(1.0, max(0.0, anchor[0])), min(1.0, max(0.0, anchor[1])))
        version.anchor_override = anchor
        # Clear results BEFORE flipping the status: readers deep-copy the
        # live state non-atomically, so flipping first would let a poll pair
        # status="rendering" with stale checks/downloads from the old render.
        version.error = None
        version.checks = []
        version.stills = []
        version.download_url = None  # stale until the re-render finishes
        version.spec = None
        version.status = "rendering"
        version.progress = 0
        self._persist(state)
        self._queue.put(("render", job_id, platform))
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
                msg = self._queue.get(timeout=0.5)
            except queue.Empty:
                continue
            if msg == "__stop__":
                if self._stop.is_set():
                    break
                continue  # stale sentinel from a previous lifecycle — drain it
            if msg[0] == "job":
                try:
                    self._run_job(msg[1])
                except Exception as exc:  # whole-job failure (FR-2.4)
                    state = self._load(msg[1])
                    if state is not None:
                        state.status = "failed"
                        state.error = str(exc)[:500]
                        self._persist(state)
            elif msg[0] == "render":
                # Single-platform re-render (FR-4.3) — failure stays local.
                _, job_id, platform = msg
                try:
                    self._render_one(job_id, platform)
                except Exception as exc:
                    state = self._load(job_id)
                    if state is not None and platform in state.versions:
                        version = state.versions[platform]
                        version.status = "failed"
                        version.error = str(exc)[:500]
                        self._persist(state)

    def _run_job(self, job_id: str) -> None:
        # _load (not get): the worker must mutate the LIVE object so cache +
        # disk stay consistent; get() would hand it a throwaway copy.
        state = self._load(job_id)
        if state is None:
            return

        # --- analyze: probe input + SRT + scene/face anchors ---
        # _prepare() is memoized per job, so this initial pass fills the
        # cache that later FR-4.3 re-renders hit — one analysis per job.
        state.status = "analyzing"
        self._persist(state)
        job_dir = self.job_path(job_id)
        try:
            info, cues, face_anchor = self._prepare(job_id)
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
        state.status = "rendering"
        self._persist(state)

        for pid in list(state.versions):
            self._render_one(job_id, pid, info=info, cues=cues, face_anchor=face_anchor)

        state = self._load(job_id)
        state.status = "done"
        self._persist(state)

    def _prepare(self, job_id: str) -> tuple[MediaInfo, list, tuple[float, float] | None]:
        """Pipeline inputs for (re-)rendering: probe + SRT + scene anchors.

        Memoized per job: the inputs depend only on in.mp4/in.srt, which the
        API never mutates after create_job, so the result is stable for the
        job's lifetime. Re-renders then skip the O(samples x Haar-detect)
        video analysis entirely — a 60 s clip costs ~15 s of CPU per
        re-render otherwise.
        """
        cached = self._analysis_cache.get(job_id)
        if cached is not None:
            return cached
        job_dir = self.job_path(job_id)
        info = probe(job_dir / "in.mp4")
        cues = ass.parse_captions(
            (job_dir / "in.srt").read_text(encoding="utf-8"), "in.srt"
        )
        scenes = analyzer.analyze_scenes(job_dir / "in.mp4", info)
        result = (info, cues, analyzer.first_face_anchor(scenes))
        self._analysis_cache[job_id] = result
        return result

    def _render_one(
        self,
        job_id: str,
        platform: str,
        info: MediaInfo | None = None,
        cues: list | None = None,
        face_anchor: tuple[float, float] | None = None,
    ) -> None:
        """Render + verify ONE platform version (FR-2.3, FR-2.4).

        Used by both the initial pass and single-platform re-renders. A failed
        render does NOT fail the job — the version shows 'failed' + stderr tail.
        """
        state = self._load(job_id)
        if state is None or platform not in state.versions:
            return
        version = state.versions[platform]

        if info is None:  # re-render path: recompute pipeline inputs
            info, cues, face_anchor = self._prepare(job_id)

        version.status = "rendering"
        version.progress = 5
        version.error = None
        version.checks = []
        version.stills = []
        self._persist(state)

        def progress(pct: int) -> None:
            version.progress = pct
            self._persist(state)

        try:
            cfg = rules.load_platforms()[platform]
            ass_text, wrapped = ass.build_ass(cfg, cues, info.duration_s)
            job_dir = self.job_path(job_id)
            ass_path = job_dir / f"{platform}.ass"
            ass_path.write_text(ass_text)

            # Anchor priority: manual override (FR-4.3) > face anchor (FR-4.2)
            # > center. Blur-pad ignores the anchor entirely (FR-3.3).
            anchor = version.anchor_override or face_anchor or (0.5, 0.5)
            crop = None
            if version.fit == "crop":
                crop = rules.crop_window(cfg, info.width, info.height, anchor[0], anchor[1])
            vf = renderer.build_vf(crop, ass_path, config.FONTS_DIR, version.fit)
            renderer.render(job_dir, platform, vf, info.duration_s, on_progress=progress)

            version.progress = 100
            output_path = job_dir / "versions" / f"{platform}.mp4"
            output = probe(output_path)
            version.checks = verifier.verify(
                cfg,
                wrapped,
                output,
                info.has_audio,
                face_expected=face_anchor is not None,
                output_path=output_path,
            )
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
            version.download_url = f"/api/jobs/{state.job_id}/versions/{platform}"
            # Stills are non-fatal (FR-6.1): a failure only leaves fewer previews.
            try:
                still_paths = stills.extract_stills(
                    job_dir, platform, output.duration_s, [cue.start_ms for cue in cues]
                )
                version.stills = [
                    f"/api/jobs/{state.job_id}/stills/{platform}/{i}"
                    for i in range(len(still_paths))
                ]
            except Exception:
                version.stills = []
            # Flip to done LAST. probe()+verify() take hundreds of ms; setting
            # status="done" first lets a concurrent reader (API poll) tear a
            # snapshot pairing done with the still-empty checks list. Ordering
            # the writes makes "done" imply fully-verified output.
            version.status = "done"
            self._persist(state)
        except Exception as exc:  # platform-level failure only (FR-2.4)
            version.status = "failed"
            version.error = str(exc)[:500]
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