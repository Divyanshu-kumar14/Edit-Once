# Design — AI Caption Transcription (local Whisper)

**Date:** 2026-08-15
**Project:** Edit Once, Publish Everywhere (Social Media Automation Hackathon)
**Status:** Approved by user — ready for implementation

## 1. Problem

Edit-Once currently requires the creator to upload an SRT caption file. Most solo
creators don't have one — they'd have to export captions from CapCut or type them.
This precondition is the biggest workflow friction in the product.

## 2. Decisions (brainstormed & approved)

| # | Decision | Choice |
|---|---|---|
| 1 | Motivation | Remove the "bring your own SRT" friction (not AI-for-AI's-sake) |
| 2 | Runtime | **Fully local** faster-whisper (no API keys, demo-proof, consistent with NFR-2) |
| 3 | Caption flow | **Straight-through + copy-out** — transcribe → render automatically; generated SRT downloadable, no caption editor UI |
| 4 | Upload semantics | **SRT optional** — video-only uploads auto-transcribe; uploaded SRT path byte-identical to today |

Verified: `ctranslate2 4.8.1` ships cp314 Linux wheels; `faster-whisper 1.2.1`
accepts it (`>=4.0,<5`). Stack is installable on the project's Python 3.14 venv.

## 3. Architecture

Transcription is a **new front stage in the existing pipeline**:

```
queued → transcribing (new, only when no SRT) → analyzing → render×4 → verify → stills → done
```

Key mechanism — **the zero-touch trick**: the transcriber writes generated
captions to `in.srt` — the exact file `_prepare()` already reads. Therefore
`_prepare()`, the analysis memo cache, render, verify, stills, and FR-4.3
re-renders are **unchanged**. One code path, one file convention; provenance is
tracked in state only.

### Backend

- **`backend/app/pipeline/transcriber.py`** (new)
  - `transcribe(audio_path, srt_path, on_progress)` — wraps faster-whisper.
    Process-wide lazy model singleton (`config.WHISPER_MODEL`, default `"base"`,
    `device="cpu"`, `compute_type="int8"`), VAD filter enabled.
  - `segments_to_srt(segments) -> str` — pure function: Whisper segments →
    standard SRT cue blocks (unit-testable, no model/network).
  - **Lazy import of faster-whisper** (graceful degradation): if the stack is
    missing, the app still boots; SRT path works; video-only uploads get a
    clear 422 naming the fix.
- **`backend/app/config.py`**: `WHISPER_MODEL` (env `EDITONCE_WHISPER_MODEL`,
  default `"base"`), `WHISPER_DEVICE="cpu"`, `WHISPER_COMPUTE_TYPE="int8"`.
- **`backend/app/queue.py`**:
  - `create_job(video_path, srt_bytes | None, filename)` — srt optional.
  - Worker: when no SRT, set `state.status = "transcribing"`, run
    `transcriber.transcribe(in.mp4 → in.srt, on_progress)` **before**
    `_prepare()`. Progress approximated from last segment end / total duration,
    persisted to `state.transcribe_progress`.
- **`backend/app/models.py`**: additive fields — `JobState.captions:
  {source: "uploaded"|"transcribed", cue_count: int}` (default None) and new
  status `"transcribing"`. Old state.json files load unchanged.
- **`backend/app/main.py`**:
  - `POST /api/jobs`: `srt` optional; validation identical when provided.
    Response gains `"captions": "uploaded"|"auto"`.
  - **New** `GET /api/jobs/{id}/captions` → `FileResponse` of the job's SRT as
    `captions.srt` (works for uploaded and transcribed).
  - `/api/health` gains `"whisper": bool` (model available).

### Error paths (clear messages, no 500s)

| Condition | Result |
|---|---|
| No audio track + no SRT | Job fails: "No audio track found — can't auto-generate captions. Upload an SRT." |
| No speech detected (VAD empty) | Job fails: "No speech detected in audio." |
| Whisper stack missing | 422 on video-only upload: "Auto-captioning unavailable — install faster-whisper or upload an SRT." App still serves SRT path |
| Model not downloaded | Error names setup.sh; setup.sh pre-downloads model (offline demo safety) |

### Frontend

- **UploadDropzone**: SRT field becomes optional; copy: "Captions optional — we
  transcribe them automatically."
- **JobProgress**: handle `"transcribing"` status with a transcription phase row
  (progress bar from `transcribe_progress`).
- **Results**: captions panel — source badge ("auto-transcribed" | "uploaded"),
  cue count, **Download SRT** button (copy-out).
- **types.ts / api.ts**: JobState additions + captions download helper.

### Testing

- Unit: `segments_to_srt` (format, timestamps, whitespace, empty);
  `transcribe()` with mocked model (SRT written, progress called, both error
  paths).
- API: video-only + mocked transcriber → done + captions endpoint; video+SRT →
  behavior identical to today.
- **One deliberate change**: existing "missing SRT → 422" test becomes
  "missing SRT → 201, auto-transcribe". All other tests stay green.
- E2E `demo.sh` unchanged (SRT path). AI flow shown manually in the demo video.
- Stretch (not required): espeak-ng speech fixture for a scripted no-SRT E2E.

### Docs

- README: captions optional; architecture diagram gains transcribe stage;
  status adds M7. PRD: FR-1/UC-1 updated; new FR for transcription.

## 4. Out of scope (documented, not built)

- Caption editor UI (decision 3 rejected it)
- Cloud transcription (decision 2 rejected it)
- Separate transcription worker/service — would be the scale move if the app
  outgrew one worker; not needed for a single-machine hackathon demo
- Batch upload / YouTube upload (pre-existing P2 cuts)

## 5. Risks

- **Model download size** (~145MB base) at setup — setup.sh pre-downloads;
  best-effort, app still boots.
- **CPU transcription speed**: 30s clip ≈ 10–15s (base/int8); 600s clip ≈ 3–5
  min — progress UI covers it; duration warning in results.
- **Whisper word/timing errors** — accepted tradeoff; copy-out SRT is the
  escape hatch.
