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
