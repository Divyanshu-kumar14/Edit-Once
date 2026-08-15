"""FastAPI app: upload, job polling, health, static frontend (PRD 7.3)."""

from __future__ import annotations

import asyncio
from contextlib import asynccontextmanager
from pathlib import Path

# Load .env files BEFORE importing config (which reads env vars once).
# uvicorn runs from backend/, so both repo-root and backend/.env are honored.
try:
    from dotenv import load_dotenv

    load_dotenv(Path(__file__).resolve().parent.parent.parent / ".env")
    load_dotenv(Path(__file__).resolve().parent.parent / ".env")
except ImportError:  # pragma: no cover - dotenv is a hard dep
    pass

from fastapi import FastAPI, File, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles

from . import config
from .models import JobState, SeoPack, VersionOptions
from .pipeline import seo, transcriber
from .pipeline.ass import SrtParseError, parse_captions
from .pipeline.probe import ProbeError, probe
from .queue import JobManager, ffmpeg_available, platform_ids

manager = JobManager()


@asynccontextmanager
async def lifespan(_app: FastAPI):
    manager.start()
    yield
    manager.stop()


app = FastAPI(title="Edit Once, Publish Everywhere", lifespan=lifespan)

# Dev convenience: allow the Vite dev server to call the API (prod is same-origin).
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


def _ensure_toolchain() -> None:
    """Raise 503 when ffmpeg/libass is unavailable (error matrix)."""
    version, libass = ffmpeg_available()
    if version is None:
        raise HTTPException(status_code=503, detail="ffmpeg not found — run scripts/setup.sh")
    if not libass:
        raise HTTPException(
            status_code=503, detail="ffmpeg lacks libass (subtitles filter) — reinstall ffmpeg"
        )


@app.get("/api/health")
def health() -> dict[str, object]:
    version, libass = ffmpeg_available()
    fonts_ok = (config.FONTS_DIR / config.FONT_FILENAME).exists()
    return {
        "ok": version is not None and libass and fonts_ok,
        "ffmpeg": version,
        "libass": libass,
        "fonts": fonts_ok,
        "whisper": transcriber.stack_available(),
        "groq": seo.stack_available(),
    }


@app.post("/api/jobs", status_code=201)
async def create_job(
    video: UploadFile | None = File(default=None),
    srt: UploadFile | None = File(default=None),
) -> JSONResponse:
    _ensure_toolchain()

    # --- video validation (FR-1.2) ---
    if video is None or video.filename is None:
        raise HTTPException(status_code=422, detail="Missing video file (MP4 required)")
    if Path(video.filename).suffix.lower() not in config.ALLOWED_VIDEO_EXTS:
        raise HTTPException(status_code=422, detail="Video must be an .mp4 file")

    # Stream to disk in 1 MB chunks instead of buffering up to 200 MB in RAM;
    # the byte budget check runs per chunk so oversized uploads fail early (413).
    video_path, _size = await _save_upload(video)
    try:
        # --- caption validation (FR-1.2, AC-6) — optional: absent SRTs are
        # auto-transcribed from the audio (AI caption stage) ---
        srt_bytes: bytes | None = None
        if srt is not None and srt.filename is not None:
            srt_ext = Path(srt.filename).suffix.lower()
            if srt_ext not in config.ALLOWED_CAPTION_EXTS:
                raise HTTPException(status_code=422, detail="Caption file must be .srt or .vtt")

            srt_text = (await srt.read()).decode("utf-8", errors="replace")
            try:
                cues = parse_captions(srt_text, srt.filename)
            except SrtParseError as exc:
                raise HTTPException(status_code=422, detail=f"Caption parse error: {exc}") from exc
            srt_bytes = srt_text.encode("utf-8")
        else:
            cues = []

        # --- video sanity (duration limit, readability) ---
        try:
            info = probe(video_path)
        except ProbeError as exc:
            raise HTTPException(status_code=422, detail=f"Could not read video: {exc}") from exc
        if info.duration_s > config.MAX_DURATION_S:
            raise HTTPException(
                status_code=422,
                detail=f"Video duration {info.duration_s:.1f}s exceeds the 600 s limit",
            )

        state = manager.create_job(video_path, srt_bytes, video.filename)
    finally:
        video_path.unlink(missing_ok=True)  # job dir holds the real copy
    return JSONResponse(
        status_code=201,
        content={
            "job_id": state.job_id,
            "cues": len(cues),
            "captions": "uploaded" if srt_bytes is not None else "auto",
        },
    )


async def _save_upload(video: UploadFile) -> tuple[Path, int]:
    """Spool the upload to a temp file in chunks; 413/422 on budget/empty."""
    import tempfile
    import uuid

    tmp = Path(tempfile.gettempdir()) / f"editonce_upload_{uuid.uuid4().hex}.mp4"
    size = 0
    try:
        with tmp.open("wb") as f:
            while chunk := await video.read(1024 * 1024):
                size += len(chunk)
                if size > config.MAX_UPLOAD_BYTES:
                    raise HTTPException(
                        status_code=413, detail="Video exceeds the 200 MB upload limit"
                    )
                f.write(chunk)
        if size == 0:
            raise HTTPException(status_code=422, detail="Video file is empty")
        return tmp, size
    except Exception:
        tmp.unlink(missing_ok=True)
        raise


@app.get("/api/jobs/{job_id}")
def get_job(job_id: str) -> JobState:
    state = manager.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return state


@app.put("/api/jobs/{job_id}/versions/{platform}/options")
def update_version_options(job_id: str, platform: str, body: VersionOptions) -> JobState:
    """Apply per-version fit/anchor and re-render that platform (FR-3.3, FR-4.3)."""
    state = manager.update_version_options(
        job_id, platform, body.fit, body.anchor
    )
    if state is None:
        raise HTTPException(status_code=404, detail="Job or platform not found")
    return state


@app.get("/api/jobs/{job_id}/versions/{platform}")
def download_version(job_id: str, platform: str) -> FileResponse:
    """Stream a rendered MP4 as an attachment (FR-7.1); 404 until done."""
    state = manager.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    version = state.versions.get(platform)
    if version is None or version.status != "done":
        raise HTTPException(status_code=404, detail="Version not available yet")
    path = manager.job_path(job_id) / "versions" / f"{platform}.mp4"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Version file missing")
    return FileResponse(
        path,
        media_type="video/mp4",
        filename=f"{job_id[:8]}_{platform}.mp4",
        headers={"Content-Disposition": "attachment"},
    )


@app.get("/api/jobs/{job_id}/captions")
def download_captions(job_id: str) -> FileResponse:
    """Serve the job's caption file (uploaded or auto-transcribed) as captions.srt."""
    state = manager.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = manager.job_path(job_id) / "in.srt"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Captions not available yet")
    return FileResponse(
        path,
        media_type="application/x-subrip",
        filename="captions.srt",
    )


@app.post("/api/jobs/{job_id}/seo")
async def generate_seo(job_id: str) -> JSONResponse:
    """Generate per-platform SEO packs (title/description/hashtags) via Groq.

    On-demand and cached: results persist in state.json (re-visits don't
    re-bill); a regenerate call overwrites them.
    """
    state = manager.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    if state.status != "done":
        raise HTTPException(
            status_code=409, detail="SEO pack requires a finished job (status done)"
        )
    if not seo.stack_available():
        raise HTTPException(
            status_code=503,
            detail="Groq API key not configured (set EDITONCE_GROQ_API_KEY in .env)",
        )
    if config.GROQ_API_KEY is None:
        raise HTTPException(status_code=503, detail="Groq API key not configured")

    srt_path = manager.job_path(job_id) / "in.srt"
    if not srt_path.exists():
        raise HTTPException(status_code=409, detail="No captions to ground the SEO pack")
    try:
        cues = parse_captions(srt_path.read_text(encoding="utf-8"), "in.srt")
    except SrtParseError as exc:  # pragma: no cover - in.srt is written by us
        raise HTTPException(status_code=409, detail=f"Caption parse error: {exc}") from exc
    transcript = " ".join(c.text.strip() for c in cues)[: seo.MAX_TRANSCRIPT_CHARS]
    if not transcript.strip():
        raise HTTPException(status_code=409, detail="No captions to ground the SEO pack")

    meta = {
        "duration_s": state.input.duration_s if state.input else 0,
    }
    api_key = config.GROQ_API_KEY
    results: dict[str, SeoPack] = {}
    errors = 0
    for platform in platform_ids():
        try:
            results[platform] = await asyncio.to_thread(
                seo.generate_pack, api_key, transcript, platform, meta
            )
        except seo.SeoError as exc:
            results[platform] = SeoPack(error=str(exc))
            errors += 1
    if errors == len(results):
        raise HTTPException(
            status_code=502,
            detail=next(r.error for r in results.values() if r.error),
        )
    generated_at = seo.now_iso()
    manager.update_seo(job_id, results, generated_at)
    return JSONResponse(
        content={"packs": {k: v.model_dump() for k, v in results.items()}, "generated_at": generated_at}
    )


@app.get("/api/jobs/{job_id}/stills/{platform}/{n}")
def get_still(job_id: str, platform: str, n: int) -> FileResponse:
    """Serve a still JPEG (FR-6.2); 404 when missing."""
    state = manager.get(job_id)
    if state is None:
        raise HTTPException(status_code=404, detail="Job not found")
    path = manager.job_path(job_id) / "stills" / f"{platform}_{n}.jpg"
    if not path.exists():
        raise HTTPException(status_code=404, detail="Still not found")
    return FileResponse(path, media_type="image/jpeg")


# Frontend build is served at / when present (mounted last so /api wins).
if config.FRONTEND_DIST.exists():
    app.mount("/", StaticFiles(directory=config.FRONTEND_DIST, html=True), name="static")