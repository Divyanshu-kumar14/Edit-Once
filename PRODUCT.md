# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Primary: solo short-form creators posting to 2+ platforms (TikTok, Reels, Shorts, X), already editing in CapCut / Premiere / Descript. Situation: finished short exported + SRT in hand, dreading 3-4 manual re-edits for safe zones / ratios / limits. Job: one click to 4 platform-correct exports.

Secondary (evaluator only, not a user to design for): hackathon judges verifying Functionality + Usefulness via runnable demo at `http://localhost:8000`.

Open: agencies / batch users (FR-9 Batch P2) — not confirmed as durable audience; recorded as undecided.

## Product Purpose

Upload one finished short (clean, no burned-in captions) + optional SRT → re-render captions into each platform's safe zone, convert any ratio to 9:16 1080×1920 via anchored crop, and verify every version against its spec before marking Ready. Downloads per MP4.

Success means: polling reaches `done`, all 4 versions `done` with `resolution PASS, ratio PASS, captions_safe PASS, audio PASS` for the fixture, playable in-browser + downloadable. Delegated assumption (user asked to proceed on recommendation): success definition stands as in PRD §5 AC-1..AC-6.

## Positioning

Correctness guarantee, not auto-clipper. Repacks *your* edit and proves platform-correctness (safe-zone rules engine + checklist); does not re-cut content like Repurpose.io / Opus Clip / Klap where creator loses control. Automation by default, manual crop-anchor override only as escape hatch.

## Operating Context

Single-page flow: upload dropzone (video + SRT with parse preview) → job progress (4 platform rows, 2s poll of `GET /api/jobs/{id}`) → results grid (4 cards: stills preview, safe-zone overlay toggle, checklist, download). Clicking a still plays full video (HTML5). Errors surface in UI with specifics (SRT line number, stderr tail); no blank screens.

Environments: laptop demo via `scripts/run.sh` (uvicorn serves `frontend/dist` on :8000); dev via `frontend npm run dev` (:5173 proxies /api → :8000). Must be readable on a projector. Fully offline core path — demo cannot break on network/auth.

## Capabilities and Constraints

Confirmed: FastAPI + Vite React 18 TS; probe → transcribe (only when no SRT) → analyze → render (sequential, 1 globally) → verify → stills; state persisted to `data/jobs/{job_id}/state.json`; no DB / Redis. Rules live in `backend/platforms.json` (single source of truth). Outputs 1080×1920 H.264 + AAC + faststart; fps passthrough (default 30 if invalid). ASS burned via libass (Alignment 2, WrapStyle 2, MarginV from bottom_margin). Long multi-word cues split into timed chunks (single-word over-long truncated with "…" as WARN). Limits: ≤200 MB, ≤600 s, SRT ≤2000 cues; VTT accepted → SRT. Face anchor P1 (OpenCV Haar, ~1 frame/2s, center fallback); manual anchor override FR-4.3 re-renders one platform. Stills: 3 per version snapped into caption cues when possible.

Transcription: faster-whisper `base` local CPU int8 + VAD, lazy import; status `transcribing`; video-only uploads fail clearly when model absent while SRT uploads keep working. Health reports ffmpeg / libass / fonts / whisper / groq.

SEO pack (Groq `llama-3.3-70b-versatile`, `EDITONCE_GROQ_API_KEY`): per-platform titles/descriptions/hashtags grounded in transcript, on-demand, editable/copyable. Recorded as confirmed-optional path, not core story — delegated assumption pending user correction.

Undecided / P2 cut-line: Batch N→4N, blur-pad for extreme ratios, YouTube upload — cut before sacrificing 4-platform core per PRD §10 rule.

## Brand Commitments

Name: Edit Once. Tagline: "One source edit · four platform-correct videos". Voice: direct, control-preserving ("Automation by default, control when it's wrong", "No re-editing", "captions re-rendered from your SRT, never OCR'd"). Volunteered constraints carried verbatim: dark, video-first; No purple; No AI-cliché gradients; clean typography, high contrast. Assets: `frontend/public/logo.jpg`, Plus Jakarta Sans variable font, lucide-react icons. Input must be caption-free (README + UI state this).

## Evidence on Hand

`PRD.md` (approved spec, §§6-7 exact values + API contract); `README.md` + mermaid architecture; deterministic fixture via `backend/tests/fixtures/make_fixture.py` (30s 1080×1920 + moving subject + sine audio, 8-cue SRT, plus 16:9 variant); `screenshots/` (upload, running, results-top, results, preview-modal, upload-with-captions); demo script PRD §11 (0:00-2:00). No invented testimonials / customers / benchmarks — absences future work must not fabricate.

## Product Principles

1. Correctness is the product — every version proves itself with checks before Ready.
2. Preserve the edit — automation repacks, never re-cuts; human override is escape hatch, not workflow.
3. Offline-first reliability — core path runs without network, keys, or accounts.
4. One source, four truths — single upload fans out via tunable `platforms.json`, not per-platform projects.
5. Fail in the open — per-platform failure never fails the job; errors name cause, line, and stderr.

## Accessibility & Inclusion

WCAG-AA secondary text (~7.4:1), `aria-busy` / `role=alert` live regions for poll + errors, `:focus-visible` rings (focus never color-alone), `prefers-reduced-motion` collapses animation; focus-trapped fullscreen 9:16 preview modal; responsive 4-up grid.
