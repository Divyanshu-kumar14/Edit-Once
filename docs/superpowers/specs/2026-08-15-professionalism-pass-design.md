# Professionalism Pass — Type, Icons, Voice, Structure, Tone

**Date:** 2026-08-15
**Status:** Approved by user (design presented in chat, approach 1 of 3)
**Scope:** 100% frontend presentation. No API, type, or behavior changes.

## 1. Context

The aurora/glass polish is functionally done, but the user reports the site "does not
feel professional" on five axes: (A) dev-tool copy, (B) generic typography, (C) glyph
icons (`▶`, `↓`, `🎬`), (D) missing product context on the upload screen, (E) overly
playful motion/glow. This pass professionalizes all five while **keeping the approved
aurora/glass identity** (approach 1 of 3 — user chose it over "studio calm" and
"narrative first").

Key discovery from audit: `--font: "Inter"` is declared but **never loaded** — no
fontsource import, no Google Fonts link — so every user currently renders `system-ui`.
This is the single largest professionalism gap.

## 2. Approach

One focused refactor across 6 presentation files + 2 deps. No new screens, no new
components beyond small inline additions (hero block, how-it-works strip).

**New dependencies:**
- `@fontsource/inter` — actually load Inter (weights 400/500/600/700/800)
- `lucide-react` — tree-shakeable inline SVG icons; replaces all ASCII/emoji glyphs

## 3. Typography (B)

- Import `@fontsource/inter/400.css`, `500.css`, `600.css`, `700.css`, `800.css` in
  `main.tsx` (before `index.css`).
- Type scale tokens (extend `:root`):
  - `--fs-display: 30px` / weight 600 — upload hero headline
  - `--fs-h2: 24px` / weight 650 — screen section headings ("Your versions are ready")
  - `--fs-h3: 16px` / weight 600 — card titles
  - `--fs-body: 15px` — default
  - `--fs-label: 11px` / uppercase / `letter-spacing: 0.08em` — badges, file labels
- Remove the `+0.3px` letter-spacing on `h1`/`h2` (logo-sticker feel); keep tight
  tracking only on labels. `h1` brand stays 22px (18px mobile).

## 4. Icons (C) — every glyph replaced

| Where | Before | After |
|---|---|---|
| Card play action | `▶ Play` | Play icon (filled) + "Play" |
| Card download | `↓ Download MP4` | Download icon + "Download MP4" |
| File picker chips | `🎬 Video` / `💬 Captions` | Film / Captions icons + "Video file" / "Caption file" |
| Header action | "New job" | Upload icon + "New project" |
| Card secondary | "Copy spec" | Copy icon + "Copy details" |
| Modal close | "Close" | X icon button (ghost, same behavior) |

Icons: `lucide-react` `Play`, `Download`, `Film`, `Captions`, `Upload`, `Copy`, `X`.
Sizing: 14px inline (stroke buttons), 16px for icon-only buttons; aligned with
`display: inline-flex; gap: 8px` (existing `.btn` already supports this).

## 5. Copy (A) — product voice

| Where | Before | After |
|---|---|---|
| Header tagline | "Publish Everywhere — platform-correct shorts, verified." | "One edit. Four platform-perfect videos." |
| Hero headline (new, above dropzone) | — | "One edit. Four platforms. Zero re-editing." |
| Dropzone heading | "Repack one edit for all four platforms" | "Upload your video and captions" |
| Dropzone sub | (none) | "Upload your MP4 and caption file — we re-render captions into each platform's safe zone." |
| File labels | "🎬 Video" / "💬 Captions" | "Video file" / "Caption file" |
| Status badges | `done` / `rendering` / `queued` / `failed` | "Ready" / "Processing" / "Queued" / "Failed" (title case; CSS classes unchanged) |
| Check badge rows | `pass` / `warn` / `fail` | "Passed" / "Review" / "Failed" |
| Progress label | "Rendering…" | "Rendering your video…" |
| Failed card | "Render failed" + raw `pre.stderr` | "This version failed to render" + stderr moved into `<details><summary>Technical details</summary>` |
| Fit toggle | "Blur-pad" / hint "Blur-pad letterbox — no crop anchor" | "Blur fill" / "Letterboxes with a blurred background" |
| Safe zone toggle | "Show safe zone" / "Hide safe zone" | "Show safe areas" / "Hide safe areas" |
| Summary chip | "{n} / {m} checks PASS" | "{n} of {m} checks passed" |
| Results h2 | "Results" | "Your versions are ready" + sub-line "Verified against each platform's spec." |
| Network error | "Network error — is the server running?" | "We couldn't reach the render server. Check your connection and try again." |
| Footer | "Upload one clean edit + SRT → 4 platform-correct MP4s. Captions are re-rendered into each platform's safe zone — your source must be caption-free." | "One source edit, four platform-correct videos — captions re-rendered into each platform's safe zone. Built for creators who post everywhere." |

Rule for all copy: headline states the outcome, not the mechanism. Technical detail is
available (details/collapse) but never front-and-center.

## 6. Structure (D) — product context

Upload screen (in `App.tsx`, only when `screen === "upload"`):
- Hero block above the dropzone: display headline ("One edit. Four platforms. Zero
  re-editing.") + sub-line + a row of four platform pills (TikTok · Reels · Shorts · X)
  — small glass pills with platform dot colors, purely presentational
  (`aria-hidden`-safe, visually lists the outputs).
- "How it works" strip below the dropzone: 3 compact steps with numbered icons —
  1 "Upload" (one clean edit + caption file), 2 "We render" (four platform-correct
  versions), 3 "Export" (replay or download each).
- Both wrapped in existing `Reveal`/`Stagger` primitives; hidden under reduced motion
  as usual.

Results screen: h2 + one sub-line only (no new content blocks).

## 7. Tone (E) — calmer

- Aurora (`AuroraBackground.tsx` props/`index.css`): opacity 0.6 → **0.4**; palette
  slightly desaturated (use softened hex values, e.g. `#ff6b35 → #f2713c`, teal
  `#2dd4bf → #34c8b8`); vignette strengthened (radial dark to ~0.7) so content stays
  the hero.
- Motion (`Stagger.tsx` / `PlatformCard.tsx` defaults): spring `stiffness 300 damping 28`
  → `stiffness 240 damping 30`, smaller travel (`y: 14 → 10`); card stills keep the
  shine sweep but at lower intensity (`--shine` alpha 0.14 → 0.10).
- Brand pulse (`@keyframes brand-pulse`): glow max blur 26px → **18px**.
- Everything else (dropzone drag glow, active progress bar glow) unchanged — calmer
  does not mean dead.

## 8. Files touched

- `frontend/package.json` / lock — `@fontsource/inter`, `lucide-react`
- `frontend/src/main.tsx` — fontsource imports
- `frontend/src/index.css` — type tokens, copy-related styles (badge text stays classed),
  aurora layer opacity/vignette, `--shine` alpha, brand-pulse
- `frontend/src/App.tsx` — tagline, hero block + platform pills, how-it-works strip
- `frontend/src/components/UploadDropzone.tsx` — heading/sub, file-chip icons + labels
- `frontend/src/components/ResultGrid.tsx` — h2 + sub-line, summary chip copy
- `frontend/src/components/PlatformCard.tsx` — icons, badge labels, failed-card
  details collapse, fit labels, safe-area labels, modal X
- `frontend/src/components/JobProgress.tsx` — progress label copy
- `frontend/src/ui/Stagger.tsx` / `PlatformCard.tsx` motion defaults — calmer springs

## 9. Verification

- `npm run build` passes (TS strict, no unused imports).
- Playwright QA re-run (existing `/tmp/opencode/qa` harness): upload → progress →
  results → modal at 1440×900 / 1024×768 / 390×844; zero console errors; modal
  fullscreen with exact 9:16 video (regression-guard the previous fix).
- Spot-check computed font-family resolves to "Inter" (no system-ui fallback).
- Badge/label text assertions match the After column (grep the DOM).
