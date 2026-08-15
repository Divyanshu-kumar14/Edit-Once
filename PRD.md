# PRD — "Edit Once, Publish Everywhere"

**Product:** Platform-correct short-form video repacker (web app)
**Hackathon:** Social Media Automation Hackathon (Devpost) — "Build tools that Automate Content Creation"
**Deadline:** Aug 16, 2026 @ 7:00 PM EDT
**Team:** Solo builder + AI coding agent
**Status:** Approved design — ready for implementation

---

## 0. TL;DR (what the agent must build)

A web app. The user uploads a finished short-form video (clean, no burned-in captions) plus an SRT caption file. The app re-renders the captions correctly positioned for each of 4 platforms (TikTok, Instagram Reels, YouTube Shorts, X), converts any input ratio to 9:16 1080×1920 with smart-ish cropping, and shows a side-by-side results grid with a per-platform rule checklist (PASS/FAIL) proving each version is platform-correct. Downloads of each MP4.

**Non-negotiable framing:** the product is a *correctness guarantee*, not an auto-clipper. Captions are re-rendered from the SRT into each platform's safe zone. Everything is automated by default; a manual crop-anchor override is the only human input, and it is an escape hatch, not the workflow.

---

## 1. Problem & Context

### 1.1 Problem statement
Creators edit one short for TikTok, then discover Reels needs captions higher (UI safe zone), Shorts has a like/comment rail on the right, X has different limits — so they re-edit the same video 3–4 times. That re-editing is manual, error-prone, and is a real, named burden: "video editing feels like a burden for short-form content."

### 1.2 Why not existing tools
Repurpose.io / Opus Clip / Klap *re-cut* videos automatically — the creator loses control of their edit. This product repacks *your* edit and *verifies* platform-correctness (safe zones, ratios, limits). Automation by default, human override when it's wrong. That control + verification combination is unserved for solo creators.

### 1.3 Judging rubric (how this PRD maps to winning)
| Rubric | Weight | How the product delivers |
|---|---|---|
| Functionality | 30% | Every feature must actually run: upload → 4 correct MP4s → downloads. Verification checklist proves it. |
| Real-world usefulness | 30% | Solves the exact "re-edit for every platform" burden; works with the creator's existing CapCut/Premiere export (video + SRT). |
| Creativity | 20% | Platform-safe-zone rules engine + correctness verification — a pain point that is NOT already well-solved. |
| Technical execution | 20% | Clean module boundaries, unit-tested pipeline, documented rules engine, fixture-driven E2E. |

---

## 2. Users & Use Cases

**Primary user:** solo short-form creator (faceless or personality) posting to 2+ platforms, already editing in CapCut/Premiere/Descript.

| # | Use case | Priority |
|---|---|---|
| UC1 | Upload video + optional SRT → get 4 platform-correct MP4s in one click (no SRT → captions auto-transcribed on-device) | P0 |
| UC2 | See side-by-side versions with safe-zone overlays and PASS/FAIL rule checks | P0 |
| UC3 | Download any version; download generated SRT | P0 |
| UC4 | Adjust crop anchor when auto-detection is wrong, re-render | P1 |
| UC5 | Batch: N videos → 4N versions in one run | P2 |
| UC6 | Direct upload to YouTube (Shorts) | P2 |

---

## 3. Functional Requirements

### FR-1 Upload (P0)
- FR-1.1: `POST /api/jobs` accepts multipart: `video` (mp4, ≤200 MB, ≤600 s) and optional `srt` (UTF-8, CRLF or LF, optional BOM). VTT accepted and converted to SRT.
- FR-1.2: Reject with clear error message (not 500): missing file, wrong extension, file too large, unparseable SRT (report first bad line number).
- FR-1.3: On success return `job_id`; job enters `queued`. If no SRT was uploaded, captions are transcribed later in the pipeline (see FR-2.6); the response reports `captions: "uploaded" | "auto"` and the initial cue count.

### FR-2 Job pipeline (P0)
- FR-2.1: Per job, run pipeline: `analyze` → per-platform `render` → `verify` → `stills`. When the upload had no SRT, a `transcribe` stage runs first (whisper, local).
- FR-2.2: Analyzer computes per-scene crop anchors (see FR-4). If no face found anywhere, use center anchor for all scenes (log note, do not fail).
- FR-2.3: Renders run sequentially per job (1 render at a time globally). Each platform reports progress 0–100.
- FR-2.4: A failed platform render does NOT fail the job — that platform shows `failed` + stderr tail; others continue.
- FR-2.5: Job state persisted to `data/jobs/{job_id}/state.json` so restarts don't lose jobs.
- FR-2.6: **Transcribe stage (AI captions, P0):** if the upload had no SRT, transcribe the audio with faster-whisper (local, `base` model, CPU int8, VAD filter) and write the result as `in.srt` — the exact file the renderer already reads — then continue downstream unchanged. Status `transcribing` with `transcribe_progress` 0–100. On failure (e.g., model not installed), job fails with a clear message; the whisper import is lazy so the app boots and runs SRT uploads without the model. No cloud, no API keys.

### FR-3 Platform rules engine (P0 — the product spec)
- FR-3.1: All rules live in a single `platforms.json` (see §6 for exact values). Adding a platform = adding a config entry + nothing else.
- FR-3.2: Outputs are 1080×1920 (9:16) H.264 MP4, AAC audio, `+faststart`. Frame rate is passed through from the source (do not re-encode fps; only sanitize if ffprobe reports an invalid/absent fps, then default to 30).
- FR-3.3: Input of any ratio is converted to 9:16 by anchored crop (see FR-4); blur-pad is a P1 alternative for extreme ratios (e.g., input wider than 4:3 or taller than 9:16 in unusual ways).
- FR-3.4: Captions are **re-rendered** from the SRT as burned-in ASS subtitles, positioned per platform safe zone (see §6.2). No OCR, no pixel-moving. The input video must be caption-free; README and UI must state this.

### FR-4 Crop anchor (P0 center fallback / P1 face detection)
- FR-4.1 (P0): Center anchor by default. Crop window = largest centered 9:16 window inside the input frame.
- FR-4.2 (P1): Per-scene face anchor — sample frames at ~1 per 2 s (`ffmpeg -vf fps=0.5`), run OpenCV Haar frontal-face on each, group consecutive detections into scenes, anchor each scene at the mean face-center. No per-frame tracking, no smoothing loops — deterministic and simple. If a scene has no face, center anchor.
- FR-4.3 (P1): Manual override — UI slider/drag to move the crop anchor; re-render that platform on demand.

### FR-5 Verification (P0 — the differentiator)
- FR-5.1: After each render, run checks and store results:
  - `resolution`: output is exactly 1080×1920 → PASS; ≥720×1280 → WARN; else FAIL
  - `ratio`: output aspect ≈ 9:16 → PASS/FAIL
  - `captions_safe`: ASS geometry (computed caption box from style + wrapped text) fits fully inside the platform safe rect → PASS/FAIL (report the actual margins used)
  - `audio`: stream present → PASS/FAIL
  - `duration`: ≤ platform limit → PASS; > limit → WARN with the number
- FR-5.2: Checks are shown in the UI as rows with green/red/amber badges + one-line detail.

### FR-6 Stills & preview (P0)
- FR-6.1: Extract 3 stills per platform version at timestamps where captions are visible (e.g., first caption start + 40% + 80% of duration, adjusted to land inside caption cues when possible).
- FR-6.2: UI shows a grid of 4 platform cards: stills preview, safe-zone overlay toggle (SVG showing the platform's safe rect over the still), checklist, download button. Clicking a still plays the full video (HTML5 video).

### FR-7 Results & downloads (P0)
- FR-7.1: `GET /api/jobs/{id}/versions/{platform}` streams the MP4 with correct Content-Type and `Content-Disposition: attachment`.
- FR-7.2: UI copy button for per-version specs (resolution, duration, margins used) — small, cheap, useful for judges.

### FR-8 UI (P0)
- FR-8.1: Single-page app: upload dropzone (video + SRT with parse preview showing caption count + first lines) → job progress (4 platform rows with progress bars) → results grid.
- FR-8.2: Dark, video-first aesthetic. No purple. No AI-cliché gradients. Clean typography, high contrast. Everything must be readable on a projector.
- FR-8.3: All errors surface in the UI (job failed, platform failed + stderr tail, SRT parse error with line number). No blank screens, no console-only errors.
- FR-8.4: Poll `GET /api/jobs/{id}` every 2 s while running.

### FR-9 Batch (P2 — only if Day 1 is fully green)
- FR-9.1: Drop N video+SRT pairs → queue N jobs → results page listing all jobs, each with the same 4-card grid.

### FR-10 YouTube upload (P2)
- FR-10.1: OAuth-less upload via YouTube Data API v3 with API key + refresh token flow; upload the Shorts version with `#Shorts` category flag. Requires user-provided credentials via env/config panel. If not feasible by Day 2 noon, cut it — it is NOT part of the core story.

---

## 4. Non-Functional Requirements

- **NFR-1 Performance:** 30 s / 1080×1920 clip / platform renders in ≤60 s on a laptop (libx264 `veryfast` preset; `faster` allowed if needed). 4 platforms ≈ ≤4 min per video.
- **NFR-2 Reliability:** No external APIs required for the core pipeline (fully offline stack — ffmpeg + OpenCV + libass). Zero secrets in repo. This is a feature: the demo cannot break on network/auth.
- **NFR-3 Concurrency:** 1 render at a time globally (configurable in `config.py`); queue everything else. No DB — job state on disk JSON.
- **NFR-4 Portability:** `scripts/setup.sh` installs deps on Linux/macOS (ffmpeg with libass — verify `ffmpeg -filters | grep subtitles`); `scripts/run.sh` starts backend + serves frontend build; app reachable at `http://localhost:8000`.
- **NFR-5 Code quality:** Type-hinted Python, typed TS. No `any` / `object` leaks. Module-per-concern (see §7). Unit tests for all pure logic. README with run instructions + architecture diagram (mermaid ok).
- **NFR-6 Limits:** upload ≤200 MB, duration ≤600 s, SRT ≤2000 cues (reject beyond with message).

---

## 5. User Stories → Acceptance Criteria (Definition of Done)

Every item below must be verifiable by running the app:

| ID | Acceptance criterion |
|---|---|
| AC-1 | `POST /api/jobs` with fixture video+SRT returns `job_id`; polling reaches `done`; all 4 versions `status: done`. |
| AC-2 | Each output MP4 is exactly 1080×1920, has an audio stream, plays in a browser. |
| AC-3 | All 4 checklists show `resolution PASS`, `ratio PASS`, `captions_safe PASS`, `audio PASS` for the fixture. |
| AC-4 | With the overlay toggle ON, captions in each still sit fully inside the platform safe rect (visual check, fixture has captions near the bottom edge so TikTok passes but would fail Reels if margins were wrong — i.e., the repositioning is *visible*). |
| AC-5 | Downloads return correct MP4 files. |
| AC-6 | Upload a video with *no* SRT → captions are auto-transcribed (faster-whisper, local): polling shows `transcribing`, then `done` with `captions: "auto"`; the generated SRT is served via `GET /api/jobs/{id}/captions`. Upload a broken SRT (bad timestamp) → error naming the line. |
| AC-6b | Health endpoint reports whisper availability; with faster-whisper absent, video-only uploads fail with a clear message while SRT uploads keep working. |
| AC-7 | `pytest` passes: test_srt, test_ass, test_rules, test_verifier, test_transcriber, test_api (≥80% coverage on pure-logic modules). |
| AC-8 | `scripts/setup.sh && scripts/run.sh` on a clean machine → app at localhost:8000 works end-to-end with the fixture. |
| AC-9 | (P1) Face anchor: fixture with a face on the left third → crop window is left-of-center, not centered. |

---

## 6. Platform Rules — EXACT VALUES (`platforms.json`)

### 6.1 Per-platform config schema
```json
{
  "tiktok": {
    "output": { "width": 1080, "height": 1920 },
    "safe_zone": { "bottom_margin": 0.18, "right_margin": 0.15, "top_margin": 0.05 },
    "caption_style": { "font_size": 64, "outline": 3, "shadow": 1, "max_lines": 3, "max_chars_per_line": 18 },
    "duration_limit_s": 600,
    "min_resolution": [720, 1280]
  },
  "reels": {
    "output": { "width": 1080, "height": 1920 },
    "safe_zone": { "bottom_margin": 0.30, "right_margin": 0.15, "top_margin": 0.05 },
    "caption_style": { "font_size": 64, "outline": 3, "shadow": 1, "max_lines": 3, "max_chars_per_line": 18 },
    "duration_limit_s": 180,
    "min_resolution": [720, 1280]
  },
  "shorts": {
    "output": { "width": 1080, "height": 1920 },
    "safe_zone": { "bottom_margin": 0.20, "right_margin": 0.25, "top_margin": 0.05 },
    "caption_style": { "font_size": 64, "outline": 3, "shadow": 1, "max_lines": 3, "max_chars_per_line": 18 },
    "duration_limit_s": 180,
    "min_resolution": [720, 1280]
  },
  "x": {
    "output": { "width": 1080, "height": 1920 },
    "safe_zone": { "bottom_margin": 0.15, "right_margin": 0.10, "top_margin": 0.05 },
    "caption_style": { "font_size": 64, "outline": 3, "shadow": 1, "max_lines": 3, "max_chars_per_line": 18 },
    "duration_limit_s": 140,
    "min_resolution": [720, 1280]
  }
}
```
Rationale (document this in README): Reels' bottom UI is the heaviest (caption bar + icons → largest bottom margin); Shorts has the like/comment rail on the right (largest right margin); X has the lightest UI (smallest margins). These are tunable presets, not law — the point is the *engine*, and the values are defensible and demonstrable.

### 6.2 ASS generation rules (per platform)
- PlayResX=1080, PlayResY=1920.
- Style: Fontname = bundled font (see §7 fonts), Fontsize = `caption_style.font_size`, PrimaryColour = `&H00FFFFFF`, OutlineColour = `&H00000000`, Outline = 3, Shadow = 1, Alignment = 2 (bottom-center), WrapStyle = 2, MarginV = `round(bottom_margin * 1920) + font_size` (so the caption's bottom edge sits above the safe line), MarginL/R = `round(right_margin * 1080)`.
- Long cues wrap at `max_chars_per_line` using `\N` (hard line break, WrapStyle 2 respects `\N`), max `max_lines`; cues longer than `max_lines * max_chars_per_line` are truncated with "…" (do not silently drop — truncation is a WARN in the checklist, not a FAIL).
- Timecodes converted from SRT (`hh:mm:ss,mmm`) to ASS (`h:mm:ss.cc`), clamp cue end to video duration.
- `chars_per_line` estimation: latin chars ≈ 0.5 × font_size px wide; CJK ≈ 1.0 × font_size. Compute per-cue wrap so the widest line fits inside `width - right_margin*width - left_margin*width` (left margin = right margin, symmetric).

### 6.3 ffmpeg render command (reference)
Probe first (`ffprobe -v error -select_streams v:0 -show_entries stream=width,height,duration,fps`).

If input is already 9:16:
```
ffmpeg -y -i in.mp4 -vf "scale=1080:1920:flags=lanczos,subtitles=<platform>.ass:fontsdir=fonts" \
  -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p \
  -c:a aac -b:a 128k -movflags +faststart -map_metadata -1 out_<platform>.mp4
```
If input ratio ≠ 9:16, compute the largest 9:16 window inside the input, then crop. Two cases (input_ratio = input_w / input_h; target = 9/16):
- **Input wider than 9:16** (input_ratio > 9/16): crop `w = ih*9/16`, `h = ih`, `x = anchor_x_fraction * (iw - w)` (clamped ≥0), `y = 0`.
- **Input taller than 9:16** (input_ratio < 9/16): crop `w = iw`, `h = iw*16/9`, `x = 0`, `y = anchor_y_fraction * (ih - h)` (clamped ≥0).
- Exactly 9:16: no crop.
Then scale to 1080×1920 and burn captions:
```
ffmpeg -y -i in.mp4 -vf "crop=w=<computed>:h=<computed>:x=<computed>:y=<computed>,scale=1080:1920:flags=lanczos,subtitles=<platform>.ass:fontsdir=fonts" ...
```
(`crop` accepts expressions with `iw`/`ih` — compute the window in a pre-step in Python and pass literal numbers; do not rely on ffmpeg expression math for the anchor.)
Blur-pad (P1, for extreme ratios):
```
ffmpeg -y -i in.mp4 -filter_complex \
  "[0:v]split=2[a][b];[b]scale=1080:1920:force_original_aspect_ratio=increase,crop=1080:1920,gblur=sigma=20[bg];\
   [a]scale=1080:1920:force_original_aspect_ratio=decrease[fg];\
   [bg][fg]overlay=(W-w)/2:(H-h)/2,subtitles=<platform>.ass:fontsdir=fonts[v]" \
  -map "[v]" -map 0:a? -c:v libx264 -preset veryfast -crf 20 -pix_fmt yuv420p -c:a aac -b:a 128k -movflags +faststart out.mp4
```
- `-map 0:a?` — optional audio (if source has none, render still succeeds; checklist marks `audio` accordingly).
- All ffmpeg calls must have a hard timeout (e.g., 2× expected duration) and capture stderr for error reporting.

### 6.4 Stills
```
ffmpeg -ss <t> -i out.mp4 -frames:v 1 -q:v 3 still_<platform>_<i>.jpg
```
Choose t: first caption cue start, 40% duration, 80% duration; snap each into the nearest caption cue if within 2 s.

---

## 7. Architecture & File Layout

### 7.1 Stack
- **Backend:** Python 3.11+, FastAPI, uvicorn, opencv-python-headless, pydantic. ffmpeg/ffprobe as subprocesses. Serves `frontend/dist` as static files.
- **Frontend:** Vite + React + TypeScript. Tailwind allowed (fast), but keep the design system tiny and hand-rolled tokens.
- **No database.** No Redis. No external APIs in the core path.

### 7.2 Project tree (create exactly this)
```
newIdea/
├─ PRD.md                      # this file
├─ README.md                   # what/how/why + architecture diagram + run instructions
├─ scripts/
│  ├─ setup.sh                 # apt/brew deps: ffmpeg(+libass), python venv, pip install, npm install, frontend build
│  └─ run.sh                   # uvicorn app.main:app --port 8000 (serves frontend build)
├─ backend/
│  ├─ app/
│  │  ├─ main.py               # FastAPI app + routes + static mount + upload handling
│  │  ├─ config.py             # paths, limits, render concurrency
│  │  ├─ models.py             # pydantic schemas: JobState, VersionState, CheckResult
│  │  ├─ queue.py              # JobManager: enqueue, poll, thread pool (1 worker), state persistence
│  │  └─ pipeline/
│  │     ├─ probe.py           # ffprobe wrapper → MediaInfo dataclass
│  │     ├─ analyzer.py        # scene sampling + face anchors (P1) → list[SceneAnchor]
│  │     ├─ rules.py           # loads platforms.json, computes ASS values + crop math helpers
│  │     ├─ ass.py             # SRT/VTT parser + per-platform ASS generator (pure functions)
│  │     ├─ renderer.py        # ffmpeg command builder + runner (timeout, stderr capture)
│  │     ├─ verifier.py        # post-render checks → list[CheckResult] (pure geometry math)
│  │     └─ stills.py          # still extraction
│  ├─ platforms.json           # §6.1 config (single source of truth)
│  ├─ fonts/                   # bundled font used by libass — MUST be committed: Inter SemiBold (OFL license, download once from rsms.me/inter into this dir as Inter-SemiBold.ttf). libass resolves Fontname "Inter SemiBold" via fontsdir.
│  ├─ data/jobs/               # per-job: in.mp4, in.srt, versions/, stills/, state.json
│  └─ tests/
│     ├─ conftest.py
│     ├─ test_srt.py           # parse: CRLF, BOM, multi-line, bad timestamp → error w/ line no.
│     ├─ test_ass.py           # golden outputs per platform (exact ASS text asserted)
│     ├─ test_rules.py         # config load + margin/max_chars math
│     ├─ test_verifier.py      # geometry in/out of safe zone, ratio, audio cases
│     ├─ test_api.py           # upload happy path + error paths (FastAPI TestClient)
│     └─ fixtures/
│        ├─ make_fixture.py    # generates fixture.mp4 + fixture.srt deterministically
│        ├─ fixture.mp4        # 30 s, 1080×1920, gradient bg + moving colored box ("subject"), sine audio
│        └─ fixture.srt        # 8 cues, bottom-anchored long lines (to prove repositioning)
└─ frontend/
   ├─ package.json
   ├─ vite.config.ts           # build → ../backend/app/static (or served path)
   └─ src/
      ├─ main.tsx / App.tsx    # page: upload → progress → results
      ├─ api.ts                # typed fetch wrappers + 2 s polling
      └─ components/
         ├─ UploadDropzone.tsx
         ├─ JobProgress.tsx
         ├─ ResultGrid.tsx     # 4 PlatformCards
         ├─ PlatformCard.tsx   # stills, video player, checklist, download
         ├─ Checklist.tsx      # PASS/WARN/FAIL rows
         └─ SafeZoneOverlay.tsx# SVG rects from platform config over a still
```

### 7.3 API contract
```
POST /api/jobs                     multipart: video=file, srt=file
  201 → { "job_id": "uuid" }
  4xx → { "detail": "human-readable, specific" }

GET  /api/jobs/{job_id}
  200 → {
    "job_id": "...", "status": "queued|analyzing|rendering|done|failed",
    "created_at": "...",
    "input": { "filename": "...", "duration_s": 30.0, "resolution": [1080, 1920] },
    "versions": {
      "tiktok": { "status": "queued|rendering|done|failed", "progress": 0-100,
                  "error": null | "stderr tail (500 chars)",
                  "checks": [ {"name": "resolution", "result": "pass|warn|fail", "detail": "..."} ],
                  "stills": ["/api/jobs/<id>/stills/tiktok/0", ...],
                  "download_url": "/api/jobs/<id>/versions/tiktok",
                  "spec": { "width": 1080, "height": 1920, "duration_s": 30.0, "margins": {...} } },
      "reels": {...}, "shorts": {...}, "x": {...}
    }
  }

GET  /api/jobs/{job_id}/versions/{platform}    → MP4 (attachment)  [404 until done]
GET  /api/jobs/{job_id}/stills/{platform}/{n}  → JPEG
GET  /api/health                               → { "ok": true, "ffmpeg": "7.x", "libass": true }
```
Status flow per version: `queued → rendering (progress) → done | failed`. Job status = `rendering` while any version renders; `done` when all terminal; `failed` only if the whole job dies (e.g., analysis crash).

### 7.4 Data flow (sequence)
1. Upload → JobManager creates job dir, writes `in.mp4` + `in.srt`, state `queued`.
2. Worker: probe → analyze (anchors) → for each platform (sequential): rules → ASS → render → verify → stills → update state.json (progress after each).
3. Frontend polls; on `done` renders grid from checks/stills/download URLs.

---

## 8. Error Handling Matrix

| Scenario | Behavior |
|---|---|
| ffmpeg missing / no libass | `/api/health` reports it; upload returns 503 with message; setup.sh verifies |
| Render fails (bad codec, corrupt file) | version `failed` + stderr tail in UI; job continues for other platforms |
| SRT unparseable | 422 with line number; no job created |
| Video without audio | renders; checklist `audio` = FAIL with detail "no audio stream in source" |
| Caption cue after video end | clamp to duration; no error |
| Cue too long (truncated) | truncate + checklist `captions_safe` = WARN "line truncated" |
| Upload >200 MB or >600 s | 413/422 with specific message |
| Job dir write failure | 500 with clear message |
| Frontend poll on unknown job | 404 → UI returns to upload with "job not found" |

---

## 9. Testing Plan

### 9.1 Unit (pytest, all pure logic)
- `test_srt.py`: CRLF/LF/BOM; multiline cues; bad timestamp → line number; >2000 cues → reject.
- `test_ass.py`: per-platform golden ASS — assert exact Dialogue lines for a known cue, exact Style line (MarginV per platform), wrapping at max chars, truncation.
- `test_rules.py`: config loads; margin math (px values for 1080×1920); max_chars math for latin and CJK.
- `test_verifier.py`: geometry inside/outside safe rect; ratio check; audio presence from fake ffprobe JSON.
- `test_api.py`: TestClient — happy path (fixture), missing file, bad SRT, unknown job 404.

### 9.2 Fixture
`make_fixture.py` (deterministic, no internet): 30 s, 1080×1920, gradient background, a solid-color box moving left→right (stands in for a subject; also exercises crop when a 16:9 variant is generated), sine-tone audio. SRT: 8 cues, some >18 chars (forces wrapping), last cue ending at 28 s. A 16:9 variant fixture (1920×1080) exists for crop-path tests.

### 9.3 E2E (scripted, part of AC-8)
`scripts/demo.sh`: starts app, POSTs fixture, polls to done, asserts 4 versions exist, prints checklist table. Must pass before Day 2 polish starts.

---

## 10. Build Order (milestones, each with a gate)

**Day 1 — core (must be green before Day 2):**
- M1: repo skeleton, config, platforms.json, probe, job queue + state.json, health endpoint → gate: API tests pass
- M2: SRT parser + ASS generator + renderer for ONE platform (tiktok) + verifier + download → gate: fixture renders, checklist PASS
- M3: all 4 platforms + stills + full checklist → gate: AC-1..AC-6 pass
- M4: frontend (upload, progress, results grid, overlay toggle, download) → gate: AC-8 E2E green

**Day 2 — in priority order (cut anything below the line before polish):**
1. Face anchor (FR-4.2) + manual override (FR-4.3) → AC-9
2. Batch mode (FR-9) if M1–M4 clean
3. Blur-pad (FR-3.3)
4. YouTube upload (FR-10) — cut if any auth friction
5. Polish: README architecture diagram, demo video script, empty-state design, real-world demo clip (user's own CapCut export if available)

**Rule:** nothing above the line gets sacrificed for anything below it. The 4-platform core with PASS checklists is the product; everything else is garnish.

---

## 11. Demo Script (for the 2–4 min submission video)

1. (0:00) One line: "I edit one short for TikTok — then I have to re-edit it for Reels, Shorts, and X. This repacks it for all four, correctly." Show the CapCut-style workflow (video + SRT).
2. (0:15) Upload → progress bars on 4 platform cards.
3. (0:45) Results: 4 versions side by side. Toggle safe-zone overlay → captions sit inside each platform's zone; on TikTok low, on Reels raised, on Shorts clear of the right rail.
4. (1:30) Checklist: all PASS. Show a caption-safe FAIL demo (optional: a version with wrong margins marked red) to prove the check is real, not cosmetic.
5. (2:00) Download one; close with: "Automation by default, control when it's wrong."

---

## 12. Risks & Mitigations

| Risk | Mitigation |
|---|---|
| ffmpeg build lacks libass (subtitles filter) | setup.sh verifies `subtitles` filter; fallback: render captions via drawtext (slower, worse) — do NOT ship without burned captions |
| Render time too slow for demo | preset `veryfast` (→`faster` if needed); demo clip ≤30 s; consider 720×1280 fallback toggle (still ≥min_resolution) |
| OpenCV install weight/edge cases | headless wheel; face detection is P1 — core never depends on it |
| SRT format edge cases | strict-but-friendly parser with line numbers; fuzz via test cases |
| Judge demo machine weak | all processing is server-side; frontend is static; demo runs on user's laptop |
| "Why not CapCut?" objection | README + demo line: CapCut is manual per-platform; this is one click + verification. Control vs auto-clippers (Opus Clip) is the wedge |

---

## 13. Out of Scope (explicitly NOT building)

- OCR / detecting burned-in captions from the source video (input must be clean)
- Per-frame face tracking, jitter smoothing, auto-reframe "magic"
- Auto-clipping, auto-generation of content from prompts (that's the *other* product category)
- Scheduling/publishing to TikTok/Reels/X (YouTube only, P2)
- User accounts, auth, multi-tenancy
- Thumbnail generation, analytics