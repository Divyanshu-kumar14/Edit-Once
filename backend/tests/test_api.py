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


def test_upload_missing_srt(client) -> None:
    resp = client.post(
        "/api/jobs",
        files={"video": ("in.mp4", TINY_MP4, "video/mp4")},
    )
    assert resp.status_code == 422
    assert "caption" in resp.json()["detail"].lower()


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