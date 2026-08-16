# Edit Once — Publish Everywhere

A platform-correct short-form video repacker for the Social Media Automation Hackathon.

Upload **one** finished short (clean, no burned-in captions) + an optional SRT caption file.
The app re-renders captions into each platform's safe zone, converts any input ratio to
9:16 @ 1080×1920 with smart anchored cropping (auto face-detected, manual override), and
shows all four versions in a single-row results grid — play any preview fullscreen or
download each MP4. Every version is verified against its platform spec before it's marked
Ready; failed versions surface the renderer stderr instead.

**Make captions yours.** Each rendered version has a caption-style selector — Default,
Karaoke (word-by-word), Pop Red, or Bold Outline — re-rendered per platform through libass.
Long caption cues are split into sequential timed chunks instead of truncated, so no text
is ever silently dropped.

**No SRT? No problem.** Captions are optional — upload a video alone and captions are
transcribed locally from the audio (faster-whisper, no API keys); upload an SRT to keep
full control. Either way, captions are re-rendered from an SRT file — never OCR'd.

**Ready to post? Generate an SEO pack.** Once your versions render, one click asks Groq
for platform-optimized titles, descriptions, and viral hashtags for all four platforms —
grounded in what your video actually says (its transcript), editable, and copyable per
field or as a full pack. Optional: set `EDITONCE_GROQ_API_KEY` in `.env` to enable it.

**The product is a correctness guarantee, not an auto-clipper.** Captions are re-rendered
from the SRT — never OCR'd. Automation by default; a manual crop-anchor override is the
only human input (escape hatch, not the workflow).

## Screenshots

| Upload | Running | Results |
|---|---|---|
| ![Upload screen](screenshots/upload.png) | ![Job progress](screenshots/running.png) | ![Results grid](screenshots/results-top.png) |

| Caption-aware upload | Full results (incl. SEO pack) | Fullscreen preview |
|---|---|---|
| ![Upload with parsed captions](screenshots/upload-with-captions.png) | ![Full results page](screenshots/results.png) | ![Fullscreen 9:16 preview modal](screenshots/preview-modal.png) |

Screenshots captured from the app running its deterministic fixture (video + SRT, no
external services).

## Why this exists

Creators edit one short for TikTok, then discover Reels needs captions higher (heavier
bottom UI), Shorts has a like/comment rail on the right, X has different limits — so they
re-edit 3–4 times. Repurpose.io/Opus Clip/Klap *re-cut* your video (you lose control);
this product **repacks your edit and verifies platform-correctness**. Control + verification
is unserved for solo creators.

## Platform rules (the engine)

| Platform | Bottom safe margin | Right safe margin | Caption offset (MarginV) | Duration limit |
|---|---|---|---|---|
| TikTok | 18% | 15% | 410 px | 600 s |
| Instagram Reels | 30% | 15% | 640 px | 180 s |
| YouTube Shorts | 20% | 25% | 448 px | 180 s |
| X | 15% | 10% | 352 px | 140 s |

All values live in [`backend/platforms.json`](backend/platforms.json) — the single source of
truth (PRD FR-3.1). Adding a platform = adding one config entry, nothing else. These are
tunable presets, not law: Reels' bottom UI is the heaviest (caption bar + icons → largest
bottom margin), Shorts has the right-side rail (largest right margin), X has the lightest UI.

## Architecture

```mermaid
flowchart LR
    U[Upload video + optional SRT] --> API[FastAPI /api/jobs]
    API --> Q[JobManager · 1 worker thread]
    Q --> P[probe · ffprobe]
    P --> T[transcribe · whisper, only when no SRT]
    T --> A[analyze · scene crop anchors]
    A --> R1[render tiktok]
    A --> R2[render reels]
    A --> R3[render shorts]
    A --> R4[render x]
    R1 --> V[verify · 5 checks]
    R2 --> V
    R3 --> V
    R4 --> V
    V --> S[stills · 3 per version]
    S --> J[state.json on disk]
    J --> FE[React frontend · 2 s polling]
    FE --> D[Downloads · MP4]
    J --> G[SEO pack · Groq, on demand]
```

- **Backend** — Python 3.11+ / FastAPI, ffmpeg (libass) + OpenCV as subprocesses, no
  database; fully offline by default — the optional Groq key is the only external API.
- **Frontend** — Vite + React + TypeScript, dark aurora-glass design (hand-rolled design
  tokens, Inter Variable, lucide icons), Framer Motion for state transitions — motion
  signals state (progress, skeletons, modal), not presence; focus-trapped fullscreen 9:16
  video modal, responsive 4-up results grid.
- **Accessibility** — WCAG-AA contrast (secondary text ≈7.4:1), `aria-busy`/`role=alert`
  live regions, `:focus-visible` rings so keyboard focus never relies on color alone, and
  `prefers-reduced-motion` support that collapses all animations.
- **Pipeline** — `probe → analyze → render → verify → stills`, one render at a time
  globally, per-version state persisted to `data/jobs/{id}/state.json`.

Key modules (clean boundaries, unit-tested):

| Module | Responsibility |
|---|---|
| `backend/app/pipeline/ass.py` | SRT/VTT parser (line-numbered errors) + per-platform ASS generator (caption templates, long-cue splitting) |
| `backend/app/pipeline/rules.py` | `platforms.json` loader + margin/crop/wrap math |
| `backend/app/pipeline/renderer.py` | ffmpeg command builder/runner (timeout, progress, stderr) |
| `backend/app/pipeline/verifier.py` | resolution/ratio/captions_safe/audio/duration checks |
| `backend/app/queue.py` | JobManager: queue, worker, state persistence |

## Run it

```bash
./scripts/setup.sh    # system deps (ffmpeg+libass), venv, npm build, fixtures
./scripts/run.sh      # uvicorn on http://localhost:8000 (serves the built frontend)
```

For development: `cd frontend && npm run dev` (Vite on :5173, proxies /api → :8000).

## Verify it

```bash
cd backend && ../.venv/bin/pytest          # unit + API tests (117 tests)
cd frontend && npx tsc --noEmit && npm run build   # typecheck + production build
```

The deterministic fixture (`backend/tests/fixtures/make_fixture.py`) generates a 30 s
1080×1920 clip with a moving subject + sine audio and an 8-cue SRT — no internet needed.
Caption transcription uses faster-whisper (`base` model) entirely offline; `scripts/setup.sh`
pre-downloads it once so transcription never touches the network.

## The verification checklist (the differentiator)

Verification runs in the engine after every render; a version only shows as Ready once its
checks pass. A failed platform render never fails the job — that platform's card shows a
collapsible stderr tail while the others continue. Every error surfaces in the UI with
specifics (SRT errors name the line).

| Check | PASS | WARN | FAIL |
|---|---|---|---|
| resolution | exactly 1080×1920 | ≥ 720×1280 | below min |
| ratio | ≈ 9:16 | — | off-ratio |
| captions_safe | caption box inside platform safe rect | over-long single word truncated with "…" (multi-word cues are split into timed chunks) | box outside safe rect |
| audio | stream present | — | no audio in source |
| duration | ≤ platform limit | exceeds limit (shows number) | — |

## License

MIT — see [LICENSE](LICENSE). Bundled font: Inter (SIL Open Font License).