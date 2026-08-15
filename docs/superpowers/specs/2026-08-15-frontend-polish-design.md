# Frontend Polish — Aurora, Liquid Glass, Motion Kit

**Date:** 2026-08-15
**Status:** Approved by user (both design parts)
**Scope:** 100% frontend presentation. No API or type changes.

## 1. Context

"Edit Once, Publish Everywhere" repacks one video + SRT into 4 platform-correct MP4s
(TikTok, Reels, Shorts, X). The frontend (Vite + React 18 + TS, hand-rolled CSS) is
functional but static: flat background, plain cards, no motion personality.

Goal: make the app feel premium without changing its product or behavior. Dark
video-editor aesthetic (base `#0b0e14`, warm-orange accent `#ff6b35`, no-purple rule)
is preserved; the motion language is "expensive, calm, video-first."

## 2. Approach

**Motion-kit architecture** (user-approved): a small `src/ui/` folder of reusable,
typed, independently-testable primitives, composed by each screen. Design tokens are
extended, not rewritten. Libraries allowed (user chose "go wild" budget):
- `motion` (framer-motion successor) — spring entrances, stagger, AnimatePresence modal
- `anime.js` — count-up numbers and shine sweeps
- React Bits **Silk** WebGL shader (vendored copy-paste component) — background

All three must be verified for React 18.3.1 compatibility at implementation time.

## 3. Foundations

### 3.1 Aurora background system (`src/ui/AuroraBackground.tsx`)
- Fixed full-viewport layer behind all content (`position: fixed; inset: 0; z-index: -1`).
- Silk WebGL shader, palette-tuned: warm orange/amber (`#ff6b35`, `#ffb347`) with a
  teal counter-point (`#2dd4bf`) over the `#0b0e14` base.
- Readability: shader at ~50–65% opacity under a dark vignette layer so text keeps contrast.
- Performance/motion safety:
  - Cap devicePixelRatio at ~1.25.
  - Pause rendering when the tab is hidden (`document.visibilitychange`).
  - Freeze to a static gradient under `prefers-reduced-motion`.
  - CSS-only animated-blob fallback when WebGL is unavailable.

### 3.2 Design tokens + glass system (`src/index.css`)
Extend tokens (no rewrites of existing ones):
- Glass: `--glass-bg`, `--glass-border`, `--glass-blur`, `--glass-highlight`
  (top-edge light), shine gradient, motion easings.
- Platform accents:
  - TikTok `#25F4EE` (cyan)
  - Reels gradient `#E1306C → #833AB4` (pink→purple) — **user-approved purple exception**
    (it is Instagram's actual brand color, not AI-cliché purple)
  - Shorts `#FF0033` (red)
  - X `#E7E9EA` (white)
- Utility classes: `.glass`, `.glass-card`, `.gradient-text`, shine sweep hook.

### 3.3 Motion kit (`src/ui/`)
- `AuroraBackground.tsx` — Silk wrapper + CSS fallback + reduced-motion handling.
- `Reveal.tsx` / `Stagger.tsx` — motion spring entrances (fade + rise), stagger support,
  `useReducedMotion()`-aware.
- `CountUp.tsx` — anime.js number animation.
- `Shine.tsx` — anime.js light sweep for cards/buttons.
- Gradient-text is a CSS utility class (no component).

## 4. Screen-by-screen

### 4.1 Header
- Glass sticky header (backdrop blur + hairline border), slide-down entrance on load.
- Brand mark: soft pulsing glow (CSS, subtle).
- Tagline: gradient text (orange → amber → teal, subtle).
- "New job" button: ghost-glass styling.

### 4.2 Upload screen
- Dropzone: glass panel; drag-over adds animated accent border glow + gentle scale lift.
- File-pick chips: glass + spring hover lift.
- Parse preview: glass chip with animated count-up of caption cues.
- Submit button: shine sweep on hover, spring press feedback.

### 4.3 Progress screen — deliberately calm
- Staggered row entrance; gradient bar fill with soft glow pulse on the actively
  rendering platform; status badge pop on state transitions (rendering → done).
- No frantic animation: the user waits on ffmpeg; calm reads as "working, trust it."

### 4.4 Results screen — the hero
- Summary header: glass chip with CountUp ("4/4 versions · 20/20 checks PASS"), springs in.
- Cards: liquid-glass per platform, brand-accent tint (border glow + header wash),
  staggered spring reveal on arrival.
- Stills: shine sweep across the frame on load; safe-zone overlay and drag-anchor
  interactions preserved exactly as-is (behavior, aria, keyboard paths unchanged).
- Checklist: rows animate in with a tiny stagger; PASS green draw-in, WARN amber, FAIL red.
- Download button: shine on hover + lift; "Copy spec": ghost-glass.
- Video modal: glass modal (backdrop blur), rounded glowing frame, spring open/close
  via AnimatePresence. Escape-to-close preserved.

### 4.5 Footer & errors
- Footer: hairline glass top border only.
- Error banner: gentle slide-in; otherwise unchanged (errors stay calm and readable).

## 5. Binding constraints

- **Reduced motion:** all three libs respect `prefers-reduced-motion`; the existing
  global CSS override stays as a safety net.
- **A11y:** all focus-visible, aria labels, keyboard paths (anchor drag, modal Escape,
  play button) preserved untouched.
- **No API/type changes** — presentation only.
- **Perf:** aurora DPR cap + tab-hidden pause; animations use transform/opacity where
  possible.

## 6. Verification

- `npm run build` (tsc + vite) must pass.
- Manual QA: upload fixture → progress → results; toggle reduced-motion in devtools and
  confirm graceful freeze.
- No frontend test suite exists — build + manual QA is the bar.

## 7. Out of scope (YAGNI)

- No new features, no API changes, no new screens.
- No Rive / Bklit / Limora / MagicUI assets (user referenced them as inspiration only).
- No changes to backend or fixtures.