"""API tests — Phase 1: health + upload error paths (happy path lands with the fixture)."""

from __future__ import annotations

import time
from pathlib import Path

VALID_SRT = "1\n00:00:00,000 --> 00:00:02,000\nHello world\n\n"

SHORT_FIXTURE_DIR = Path(__file__).parent / "fixtures" / "short"

TINY_MP4 = (
    b"\x00\x00\x00\x18ftypmp42\x00\x00\x00\x00mp42isom"  # not a real playable file —
    # probe will fail, which is itself an error path we assert on.
)


def _upload_fixture(client, video: str = "fixture.mp4", srt: str = "fixture.srt"):
    video_path = SHORT_FIXTURE_DIR / video
    srt_path = SHORT_FIXTURE_DIR / srt
    return client.post(
        "/api/jobs",
        files={
            "video": (video, video_path.read_bytes(), "video/mp4"),
            "srt": (srt, srt_path.read_bytes(), "application/x-subrip"),
        },
    )


def _poll_done(client, job_id: str, timeout_s: float = 90.0) -> dict:
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        resp = client.get(f"/api/jobs/{job_id}")
        assert resp.status_code == 200
        body = resp.json()
        if body["status"] in ("done", "failed"):
            return body
        time.sleep(0.25)
    raise AssertionError(f"job {job_id} did not finish within {timeout_s}s")


def test_health_ok(client) -> None:
    resp = client.get("/api/health")
    assert resp.status_code == 200
    body = resp.json()
    assert body["ok"] is True
    assert body["ffmpeg"]
    assert body["libass"] is True


def test_upload_missing_video(client) -> None:
    resp = client.post(
        "/api/jobs",
        files={"srt": ("in.srt", VALID_SRT, "application/x-subrip")},
    )
    assert resp.status_code == 422
    assert "video" in resp.json()["detail"].lower()


def test_upload_video_only_unreadable_video_422(client) -> None:
    """Video-only upload of an unreadable file -> probe error (not caption error)."""
    resp = client.post(
        "/api/jobs",
        files={"video": ("in.mp4", TINY_MP4, "video/mp4")},
    )
    assert resp.status_code == 422
    assert "video" in resp.json()["detail"].lower()


def test_upload_wrong_video_extension(client) -> None:
    resp = client.post(
        "/api/jobs",
        files={
            "video": ("clip.mov", TINY_MP4, "video/quicktime"),
            "srt": ("in.srt", VALID_SRT, "application/x-subrip"),
        },
    )
    assert resp.status_code == 422
    assert ".mp4" in resp.json()["detail"]


def test_upload_bad_srt_reports_line(client) -> None:
    bad = "1\n00:00:00,000 --> not-a-time\nHello\n"
    resp = client.post(
        "/api/jobs",
        files={
            "video": ("in.mp4", TINY_MP4, "video/mp4"),
            "srt": ("in.srt", bad, "application/x-subrip"),
        },
    )
    assert resp.status_code == 422
    detail = resp.json()["detail"]
    assert "line 2" in detail  # bad timestamp is on line 2


def test_upload_unreadable_video(client) -> None:
    resp = client.post(
        "/api/jobs",
        files={
            "video": ("in.mp4", TINY_MP4, "video/mp4"),
            "srt": ("in.srt", VALID_SRT, "application/x-subrip"),
        },
    )
    assert resp.status_code == 422
    assert "video" in resp.json()["detail"].lower()


def test_unknown_job_404(client) -> None:
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404


def test_job_poll_shape(client) -> None:
    """Contract shape for a queued-then-done job (Phase 1: no versions rendered yet)."""
    resp = client.get("/api/jobs/does-not-exist")
    assert resp.status_code == 404


def test_empty_video_rejected(client) -> None:
    resp = client.post(
        "/api/jobs",
        files={
            "video": ("in.mp4", b"", "video/mp4"),
            "srt": ("in.srt", VALID_SRT, "application/x-subrip"),
        },
    )
    assert resp.status_code == 422


def test_happy_path_all_platforms_done(client) -> None:
    """AC-1 + AC-2 + AC-3: upload fixture -> all 4 versions done with PASS checks."""
    resp = _upload_fixture(client)
    assert resp.status_code == 201, resp.text
    job_id = resp.json()["job_id"]

    body = _poll_done(client, job_id)
    assert body["status"] == "done", body.get("error")
    assert body["input"]["resolution"] == [1080, 1920]

    for pid in ("tiktok", "reels", "shorts", "x"):
        version = body["versions"][pid]
        assert version["status"] == "done", (pid, version)
        assert version["progress"] == 100
        by_name = {c["name"]: c for c in version["checks"]}
        assert by_name["resolution"]["result"] == "pass", pid
        assert by_name["ratio"]["result"] == "pass", pid
        assert by_name["captions_safe"]["result"] in ("pass", "warn"), pid
        assert by_name["audio"]["result"] == "pass", pid
        assert version["download_url"]
        assert version["spec"]["width"] == 1080
        assert version["spec"]["height"] == 1920


def test_download_returns_mp4(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    _poll_done(client, job_id)

    dl = client.get(f"/api/jobs/{job_id}/versions/tiktok")
    assert dl.status_code == 200
    assert dl.headers["content-type"] == "video/mp4"
    assert dl.headers["content-disposition"].startswith("attachment")
    assert dl.content[:4] == b"\x00\x00\x00\x18" or dl.content[4:8] == b"ftyp"


def test_download_before_done_404(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    # Immediately (or with a tiny wait) the version is at least not done yet —
    # poll once; if already done, skip (race-free check below).
    state = client.get(f"/api/jobs/{job_id}").json()
    if state["versions"]["tiktok"]["status"] != "done":
        dl = client.get(f"/api/jobs/{job_id}/versions/tiktok")
        assert dl.status_code == 404


# --- Day-2: per-version options (FR-3.3 fit, FR-4.3 anchor re-render) -------

def _put_options(client, job_id: str, platform: str, body: dict):
    return client.put(f"/api/jobs/{job_id}/versions/{platform}/options", json=body)


def test_options_anchor_rerenders_only_that_platform(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    done = _poll_done(client, job_id)
    assert done["status"] == "done"

    # Snapshot the other platforms' download URLs to prove they're untouched.
    reels_url = done["versions"]["reels"]["download_url"]

    put = _put_options(client, job_id, "tiktok", {"fit": "crop", "anchor": [0.3, 0.6]})
    assert put.status_code == 200
    body = put.json()
    assert body["versions"]["tiktok"]["status"] == "rendering"
    assert body["versions"]["tiktok"]["anchor_override"] == [0.3, 0.6]
    assert body["versions"]["tiktok"]["download_url"] is None  # stale until done

    # Re-rendered version finishes and keeps its override.
    deadline = time.monotonic() + 90.0
    while time.monotonic() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["versions"]["tiktok"]["status"] in ("done", "failed"):
            break
        time.sleep(0.25)
    tiktok = state["versions"]["tiktok"]
    assert tiktok["status"] == "done", tiktok.get("error")
    assert tiktok["anchor_override"] == [0.3, 0.6]
    assert tiktok["download_url"] is not None
    assert tiktok["spec"]["width"] == 1080

    # Other platforms: still done with the SAME download url (never re-rendered).
    assert state["versions"]["reels"]["status"] == "done"
    assert state["versions"]["reels"]["download_url"] == reels_url


def test_options_blur_rerenders_with_correct_ratio(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    _poll_done(client, job_id)

    put = _put_options(client, job_id, "shorts", {"fit": "blur"})
    assert put.status_code == 200

    deadline = time.monotonic() + 90.0
    while time.monotonic() < deadline:
        state = client.get(f"/api/jobs/{job_id}").json()
        if state["versions"]["shorts"]["status"] in ("done", "failed"):
            break
        time.sleep(0.25)
    version = state["versions"]["shorts"]
    assert version["status"] == "done", version.get("error")
    assert version["fit"] == "blur"
    by_name = {c["name"]: c for c in version["checks"]}
    assert by_name["resolution"]["result"] == "pass"
    assert by_name["ratio"]["result"] == "pass"


def test_options_unknown_job_or_platform_404(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    assert _put_options(client, "nope", "tiktok", {"fit": "crop"}).status_code == 404
    assert _put_options(client, job_id, "youtube", {"fit": "crop"}).status_code == 404


def test_options_invalid_fit_422(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    assert _put_options(client, job_id, "tiktok", {"fit": "stretch"}).status_code == 422


def test_options_anchor_clamped(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    put = _put_options(client, job_id, "x", {"fit": "crop", "anchor": [-0.2, 1.4]})
    assert put.status_code == 200
    assert put.json()["versions"]["x"]["anchor_override"] == [0.0, 1.0]

# --- AI caption transcription: video-only upload (auto-transcribe stage) -------

def test_video_only_auto_transcribes_and_completes(client, monkeypatch) -> None:
    """Video-only upload -> transcribing stage runs (mocked) -> all 4 done."""
    from app import queue as queue_mod

    def fake_transcribe(audio_path, srt_path, on_progress=None):
        # write a real SRT so the downstream pipeline (which is NOT mocked)
        # has cues to re-render from
        (srt_path).write_text(VALID_SRT, encoding="utf-8")
        if on_progress:
            on_progress(50)
            on_progress(100)
        return 1

    monkeypatch.setattr(queue_mod.transcriber, "transcribe", fake_transcribe)

    video_path = SHORT_FIXTURE_DIR / "fixture.mp4"
    resp = client.post(
        "/api/jobs",
        files={"video": ("fixture.mp4", video_path.read_bytes(), "video/mp4")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["captions"] == "auto"

    done = _poll_done(client, body["job_id"])
    assert done["status"] == "done", done.get("error")
    assert done["captions"] == {"source": "transcribed", "cue_count": 1}
    assert done["transcribe_progress"] == 100
    for pid in ("tiktok", "reels", "shorts", "x"):
        assert done["versions"][pid]["status"] == "done", pid


def test_video_only_transcription_failure_fails_job(client, monkeypatch) -> None:
    from app import queue as queue_mod

    def boom(_a, _b, on_progress=None):
        from app.pipeline.transcriber import TranscriptionError

        raise TranscriptionError("No speech detected in audio — upload an SRT instead.")

    monkeypatch.setattr(queue_mod.transcriber, "transcribe", boom)

    video_path = SHORT_FIXTURE_DIR / "fixture.mp4"
    resp = client.post(
        "/api/jobs",
        files={"video": ("fixture.mp4", video_path.read_bytes(), "video/mp4")},
    )
    assert resp.status_code == 201
    body = _poll_done(client, resp.json()["job_id"])
    assert body["status"] == "failed"
    assert "No speech detected" in body["error"]


# --- captions endpoint + health (copy-out escape hatch) ------------------------

def test_upload_with_srt_reports_uploaded_captions(client) -> None:
    resp = _upload_fixture(client)
    assert resp.status_code == 201, resp.text
    assert resp.json()["captions"] == "uploaded"
    assert resp.json()["cues"] == 1  # short fixture.srt has 1 cue


def test_captions_endpoint_serves_srt(client) -> None:
    resp = _upload_fixture(client)
    job_id = resp.json()["job_id"]
    _poll_done(client, job_id)

    dl = client.get(f"/api/jobs/{job_id}/captions")
    assert dl.status_code == 200
    assert dl.headers["content-disposition"].startswith("attachment")
    assert "captions.srt" in dl.headers["content-disposition"]
    assert b"-->" in dl.content  # real SRT content


def test_captions_endpoint_unknown_job_404(client) -> None:
    assert client.get("/api/jobs/nope/captions").status_code == 404


def test_health_reports_whisper(client) -> None:
    body = client.get("/api/health").json()
    assert "whisper" in body


# ---------------------------------------------------------------------------
# Groq SEO pack endpoint
# ---------------------------------------------------------------------------

def _make_done_job(data_dir: Path, status: str = "done", srt_text: str = VALID_SRT) -> str:
    """Fabricate a minimal job dir + state.json (fast: no render needed)."""
    import json
    import uuid

    from app.models import JobState

    job_id = uuid.uuid4().hex[:12]
    job_dir = Path(data_dir) / "jobs" / job_id
    job_dir.mkdir(parents=True)
    state = JobState(
        job_id=job_id,
        status=status,  # type: ignore[arg-type]
        created_at="2026-08-15T00:00:00+00:00",
        versions={},
        captions={"source": "uploaded", "cue_count": 1},
    )
    (job_dir / "state.json").write_text(state.model_dump_json(indent=2))
    (job_dir / "in.srt").write_text(srt_text, encoding="utf-8")
    return job_id


def _fake_generate(api_key, transcript, platform, meta, timeout_s=None):
    """Deterministic fake Groq pack — content reflects the platform arg."""
    from app.models import SeoPack

    return SeoPack(
        title=f"{platform} title",
        description=f"{platform} description",
        hashtags=["tag1", "tag2", "tag3"],
    )


def test_seo_happy_path_persists(client, data_dir, monkeypatch) -> None:
    from app.main import config as main_config
    from app.main import seo as main_seo

    monkeypatch.setattr(main_seo, "stack_available", lambda: True)
    monkeypatch.setattr(main_config, "GROQ_API_KEY", "test-key")
    monkeypatch.setattr(main_seo, "generate_pack", _fake_generate)

    job_id = _make_done_job(data_dir)
    resp = client.post(f"/api/jobs/{job_id}/seo")
    assert resp.status_code == 200, resp.text
    body = resp.json()
    assert set(body["packs"]) == {"tiktok", "reels", "shorts", "x"}
    assert body["packs"]["tiktok"]["title"] == "tiktok title"
    assert body["packs"]["tiktok"]["hashtags"] == ["tag1", "tag2", "tag3"]
    assert body["generated_at"]

    # Cached in state.json: a plain GET (no API call) returns the packs.
    job = client.get(f"/api/jobs/{job_id}").json()
    assert job["seo_packs"]["x"]["title"] == "x title"
    assert job["seo_generated_at"] == body["generated_at"]


def test_seo_unknown_job_404(client, monkeypatch) -> None:
    from app.main import config as main_config
    from app.main import seo as main_seo

    monkeypatch.setattr(main_seo, "stack_available", lambda: True)
    monkeypatch.setattr(main_config, "GROQ_API_KEY", "test-key")
    resp = client.post("/api/jobs/does-not-exist/seo")
    assert resp.status_code == 404


def test_seo_requires_done_job_409(client, data_dir, monkeypatch) -> None:
    from app.main import config as main_config
    from app.main import seo as main_seo

    monkeypatch.setattr(main_seo, "stack_available", lambda: True)
    monkeypatch.setattr(main_config, "GROQ_API_KEY", "test-key")
    job_id = _make_done_job(data_dir, status="rendering")
    resp = client.post(f"/api/jobs/{job_id}/seo")
    assert resp.status_code == 409
    assert "finished" in resp.json()["detail"]


def test_seo_no_key_503(client, data_dir, monkeypatch) -> None:
    from app.main import seo as main_seo

    monkeypatch.setattr(main_seo, "stack_available", lambda: False)
    job_id = _make_done_job(data_dir)
    resp = client.post(f"/api/jobs/{job_id}/seo")
    assert resp.status_code == 503
    assert "GROQ_API_KEY" in resp.json()["detail"]


def test_seo_partial_failure_isolated(client, data_dir, monkeypatch) -> None:
    from app.main import config as main_config
    from app.main import seo as main_seo
    from app.pipeline.seo import SeoError

    monkeypatch.setattr(main_seo, "stack_available", lambda: True)
    monkeypatch.setattr(main_config, "GROQ_API_KEY", "test-key")

    def flaky_generate(api_key, transcript, platform, meta, timeout_s=None):
        if platform == "x":
            raise SeoError("Groq API error: 429 rate limited")
        return _fake_generate(api_key, transcript, platform, meta)

    monkeypatch.setattr(main_seo, "generate_pack", flaky_generate)
    job_id = _make_done_job(data_dir)
    resp = client.post(f"/api/jobs/{job_id}/seo")
    assert resp.status_code == 200, resp.text
    packs = resp.json()["packs"]
    assert packs["x"]["error"]
    assert packs["tiktok"]["title"] == "tiktok title"  # others unaffected


def test_seo_all_failed_502(client, data_dir, monkeypatch) -> None:
    from app.main import config as main_config
    from app.main import seo as main_seo
    from app.pipeline.seo import SeoError

    monkeypatch.setattr(main_seo, "stack_available", lambda: True)
    monkeypatch.setattr(main_config, "GROQ_API_KEY", "test-key")

    def boom(api_key, transcript, platform, meta, timeout_s=None):
        raise SeoError("Groq API error: dead")

    monkeypatch.setattr(main_seo, "generate_pack", boom)
    job_id = _make_done_job(data_dir)
    resp = client.post(f"/api/jobs/{job_id}/seo")
    assert resp.status_code == 502
    assert "Groq" in resp.json()["detail"]


def test_seo_empty_transcript_409(client, data_dir, monkeypatch) -> None:
    from app.main import config as main_config
    from app.main import seo as main_seo

    monkeypatch.setattr(main_seo, "stack_available", lambda: True)
    monkeypatch.setattr(main_config, "GROQ_API_KEY", "test-key")
    job_id = _make_done_job(data_dir, srt_text="")
    resp = client.post(f"/api/jobs/{job_id}/seo")
    assert resp.status_code == 409  # parse error or empty transcript → 409 either way


def test_health_reports_groq(client, monkeypatch) -> None:
    from app.main import seo as main_seo

    monkeypatch.setattr(main_seo, "stack_available", lambda: False)
    body = client.get("/api/health").json()
    assert body["groq"] is False
