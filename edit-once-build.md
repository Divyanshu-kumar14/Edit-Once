# Edit-Once Build Plan

## Goal
Build the PRD-approved app (backend + frontend): upload video+SRT → 4 platform-correct MP4s with PASS/FAIL verification checklists, per PRD §7 tree.

## Phases (each ends with a GATE → human checkpoint)

### Phase 0 — Environment (≈5 min)
- [ ] Create venv, pip install fastapi uvicorn opencv-python-headless pydantic pytest httpx
- [ ] Download Inter-SemiBold.ttf (OFL) into `backend/fonts/`  *(needs internet)*
- [ ] Verify `ffmpeg -filters | grep subtitles` + ffprobe works
- → **GATE:** imports work, font present, ffprobe reads fixture after Phase 2

### Phase 1 — M1: Backend skeleton
- [ ] Project tree per PRD §7.2 (backend/app/{config,models,queue}, platforms.json, tests/)
- [ ] `config.py` (paths, limits: 200MB/600s/2000 cues, 1 worker)
- [ ] `platforms.json` exact values from PRD §6.1
- [ ] `models.py` (JobState/VersionState/CheckResult pydantic)
- [ ] `queue.py` JobManager: enqueue, state.json persistence, 1-worker thread
- [ ] `pipeline/probe.py` ffprobe wrapper → MediaInfo
- [ ] `main.py`: `POST /api/jobs` (FR-1 validation: missing/wrong ext/too large/bad SRT w/ line no), `GET /api/jobs/{id}`, `GET /api/health`
- → **GATE:** `pytest tests/test_api.py` error paths + health pass

### Phase 2 — M2: Single platform (tiktok) end-to-end
- [ ] `pipeline/ass.py`: SRT/VTT parser (BOM, CRLF, bad timestamp → line no, >2000 cues reject) + ASS generator per §6.2 (MarginV/MarginL/R, \N wrap, truncate w/ "…")
- [ ] `pipeline/rules.py`: margin px math, latin/CJK max_chars math
- [ ] `pipeline/renderer.py`: ffmpeg cmd builder (crop→scale→subtitles, veryfast, timeout 2×dur, stderr capture)
- [ ] `pipeline/verifier.py`: resolution/ratio/captions_safe/audio/duration (PASS/WARN/FAIL)
- [ ] `tests/fixtures/make_fixture.py` + generate fixture.mp4 (1080×1920, 30s) + fixture.srt (8 cues, >18 chars)
- → **GATE:** tiktok version renders, checklist all PASS, download works

### Phase 3 — M3: All 4 platforms + stills
- [ ] Render loop over all platforms (sequential, per-version failed ≠ job failed), progress 0–100 in state
- [ ] `pipeline/stills.py`: 3 stills per version (cue start, 40%, 80% snapped into cues)
- [ ] Full checklist + `GET /versions/{platform}` + `GET /stills/{platform}/{n}`
- → **GATE:** AC-1..AC-6 pass via TestClient + curl

### Phase 4 — M4: Frontend + scripts
- [ ] Vite+React+TS scaffold, `api.ts` (typed fetch + 2s poll)
- [ ] UploadDropzone (video+SRT, parse preview) → JobProgress (4 rows) → ResultGrid/PlatformCard/Checklist/SafeZoneOverlay (SVG)
- [ ] Dark video-first design, no purple/gradients, projector-readable
- [ ] `scripts/setup.sh` + `scripts/run.sh` + `scripts/demo.sh`
- → **GATE:** AC-8 — clean-ish E2E at localhost:8000, demo.sh prints PASS table

### Phase 5 — Day 2 options (USER PICKS, cut anything below line)
- [x] A: Face anchor FR-4.2 (OpenCV Haar, ~1/2s samples) → AC-9
- [x] B: Manual crop override FR-4.3 + re-render
- [x] C: Blur-pad FR-3.3 (extreme ratios)
- [ ] D: Batch FR-9 (P2)
- [ ] E: YouTube upload FR-10 (P2 — cut if any auth friction)
- [ ] F: Polish: README arch diagram, demo script, real demo clip
- → **GATE:** chosen items done; core still green

## Human checkpoints
- **C0 (now):** approve plan + OK to install deps / download font (internet)
- **C1:** after Phase 1 tests green
- **C2:** after Phase 2 tiktok renders + checklist PASS
- **C3:** after Phase 3 AC-1..6
- **C4:** after Phase 4 E2E green
- **C5:** Day 2 feature pick (A–F)

## Done When
- `scripts/setup.sh && scripts/run.sh` → localhost:8000 works end-to-end with fixture
- All 4 checklists PASS; downloads return correct MP4s; pytest ≥80% pure-logic coverage