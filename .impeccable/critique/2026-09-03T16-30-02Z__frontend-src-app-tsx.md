---
target: frontend/src/App.tsx
total_score: 26
max_score: 40
na_heuristics: 
p0_count: 0
p1_count: 2
timestamp: 2026-09-03T16-30-02Z
slug: frontend-src-app-tsx
---
Method: dual-agent (A: ses_f97e73d70ffeQeStzkqjGOCVQU · B: ses_f97e73d3cffeBgcOrzLst7rSUp)

## Design Health Score — 26/40 (Acceptable)

| # | Heuristic | Score | Key Issue |
|---|---|---|---|
| 1 | Visibility of System Status | 3 | Phase copy + progressbar + skeletons good; no ETA / queue position for sequential renders |
| 2 | Match System / Real World | 3 | Safe-zone language matches creators; "Blur Pad" / "Fit" unexplained jargon |
| 3 | User Control and Freedom | 2 | No visible Cancel; drag-anchor fires irreversible re-render, no undo/preview |
| 4 | Consistency and Standards | 3 | Coherent system; `status-pill` class has no CSS definition (vs `.badge`) |
| 5 | Error Prevention | 3 | Accept filters + SRT preview help; no client pre-check 200MB/600s, 2nd MP4 silently ignored |
| 6 | Recognition Rather Than Recall | 2 | Anchor-drag, style effects, fit differences hidden; must guess |
| 7 | Flexibility and Efficiency | 2 | Keyboard nudge only; no batch download, one-at-a-time re-renders with full re-poll |
| 8 | Aesthetic and Minimalist Design | 3 | Upload clean; results + SEO (4 cards x controls + 4 SEO cards) heavy |
| 9 | Error Recovery | 3 | Per-platform Retry + stderr good; job failure bounces running→upload, loses context |
| 10 | Help and Documentation | 2 | Fineprint only; no safe-zone / clean-input / what-next guidance; Groq help is .env-speak |
| **Total** | | **26/40** | **Acceptable (50%+ band; most real UIs 20-32)** |

## Design Specificity Verdict

Grounded at the core, generic at the edges. The correctness guarantee is legible in the UI itself: interactive 9:16 safe-zone SVG with per-platform rects + caption baseline at MarginV 410/1920 + B%/R% legend, per-card Verification checklist with mono names, copy "captions re-rendered from your SRT, never OCR'd". Tokens support it: #0A0D13, single warm accent #F97316, solid surfaces (explicit no-glass), Jakarta + lucide only. No purple, no AI-cliche wash. Motion signals state, not presence. Not interchangeable at the center.

Edges dilute it: hero-split copy-left/visual-right is default SaaS; header/footer, file-pick cards, 4-up grid, and SeoSection ("viral hashtags") read as generic AI-SaaS upsell. Progress rows don't tell the real story (single sequential queue, anchored crop, burn-in). Missed: no 16:9→9:16 conversion visual, no "verified against spec" trust surfacing, face-anchor invisible until results, `ogl` unused in package.json signals unresolved identity temptation.

Deterministic scan: 4 findings, 1 actionable. `detect.mjs --json` exit 2: layout-transition x2, side-tab x1, codex-grid-background x1, zero errors. True positive: `index.css:288 .bar-fill transition: width` (progress-bar width animation — use transform instead). False positives: `:243` triggered by substring `width` inside `stroke-width` (SVG opacity/fill only); `:369` labeled side-stripe but is a 6px centered dot in 20px circular anchor marker. Advisory-true but intentional: `:76 body::before` technical grid (0.022 alpha, static, masked, commented as brand-tied). Detector agreed with LLM that no aurora/gradient wash exists; LLM caught what detector cannot (missing `status-pill` CSS, 11.5px verify-detail projector washout, uncontrolled SEO textareas).

Visual overlays: no reliable user-visible overlay available. No dev server on 5173/8000 (ss + curl 000), live-server not started for isolation, injection not attempted. Fallback = static file review (tokens, focus, aria, touch sizes below).

## Overall Impression

Upload earns trust, verification delivers relief, everything between and after leaks it. Biggest opportunity: collapse the escape hatch and end on downloads, not SEO.

## What's Working

1. SafeZoneDiagram is a fingerprint. Margin rects in platform colors + dashed caption baseline + hover-linked legend turns platforms.json into a 5-second projector-readable explainer.
2. Verification as UI, not log. Icon + mono name + Passed/Review/Failed badge survives color-blindness and projector washout; differentiator visible at a glance.
3. State-aware craft. SRT skeleton, aria-busy/alert/progressbar with real values, focus-trapped 9:16 modal with restore, prefers-reduced-motion kill-switch, skeleton CLS guards.

## Priority Issues

- **[P1] What**: Results card exposes entire escape hatch as main workflow. **Why it matters**: PRODUCT says manual override is escape hatch; layout inverts it to 7+ affordances per card x4, burying verify→download. **Fix**: Collapse fit/anchor/template behind one "Adjust" disclosure; default = still + checks + Download + Play. **Suggested command**: $impeccable layout
- **[P1] What**: Long render valley has no agency. **Why it matters**: Highest-abandonment stretch (minutes) has no queue order, ETA/elapsed, Cancel (abort exists, no UI), or backgrounding note. **Fix**: "Reels 2 of 4" + elapsed + Cancel + "job persists, you can leave". **Suggested command**: $impeccable clarify
- **[P2] What**: Drag-to-anchor undiscoverable and unforgiving. **Why it matters**: Core control promise hinges on hover-only tooltip; slip costs minutes, fails touch/keyboard. **Fix**: Explicit "Move anchor" mode with confirm/cancel + always-visible marker when fit=crop. **Suggested command**: $impeccable onboard
- **[P2] What**: Failure routing destroys context. **Why it matters**: Job failure from running bounces to upload with top banner, losing which platform failed. Violates "fail in the open". **Fix**: Stay on running/results, render per-platform errors inline. **Suggested command**: $impeccable harden
- **[P2] What**: First-timer has no clean-input mental model. **Why it matters**: "No burned-in captions" lives in fineprint; Jordan uploads captioned export → double captions → blames tool. **Fix**: 2-state clean vs burned-in visual + one-line why at video picker. **Suggested command**: $impeccable clarify

## Persona Red Flags

**Jordan (First-Timer)**: Upload never explains clean input / safe zones / "4 versions"; "Analyzing scene crop anchors" opaque; PASS/Review + Crop/Blur + 4 styles assume spec literacy; 4 identical Downloads + SEO upsell confuses end.
**Riley (Stress / projector demo)**: Blind "Create 4 versions" leap; no cancel/ETA; New project mid-render invites accidental abort; raw stderr without plain-language next step; no Download-all zip for handoff.
**Sam (A11y)**: Upload passes (labeled, focusable, live preview). Wait risks verbose re-announcements (aria-live on whole section + 2s poll). Still overloads Enter/arrows with no mode distinction; anchors aria-hidden with no text alternative; modal autoPlay overrides reduced-motion/screen-reader context.

## Minor Observations

- `status-pill` undefined (falls back); `bar-fill` gradient is functional but uneasy with "No gradients" comment; PLATFORM_LABELS verbosity inconsistent; fineprint overpromises "on-device" vs faster-whisper CPU + model-absent path; dropzone multi-drop closure may drop one file; SEO textareas uncontrolled (copy-all reads stale); New-project uses Upload icon for destructive reset; running screen flashes empty before first poll; `verify-detail` 11.5px #69748A will wash out on projector.

## Questions to Consider

- If the checklist is the product, what would the hero look like with the checklist as headline instead of the diagram?
- What breaks with exactly one primary button (Download all verified) and adjustments hidden until Review?
- Do you trust users to discover crop anchor by hover, or fear they'll discover it by accident?
