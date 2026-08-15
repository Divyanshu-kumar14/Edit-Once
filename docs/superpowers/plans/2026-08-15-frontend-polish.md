# Frontend Polish (Aurora + Liquid Glass + Motion Kit) Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Turn the static Edit-Once frontend into a premium, animated dark UI: aurora background, liquid-glass platform cards, motion kit — without changing product behavior.

**Architecture:** Motion-kit approach — a `src/ui/` folder of reusable primitives (AuroraBackground, Reveal, Stagger, CountUp, Shine) composed by each screen. CSS design tokens extended (glass, platform accents, easings). No API/type changes; a11y and reduced-motion preserved.

**Tech Stack:** React 18.3.1, Vite 6, TypeScript 5.6. New deps: `motion@^13` (peer react ^18 ✓), `animejs@^4.5` (three peers are OPTIONAL — no three.js), `ogl@^1.0.11` (WebGL lib for Aurora shader). Aurora component vendored from DavidHDev/react-bits (MIT) — **Silk is Pro-only; Aurora is the free equivalent** of the approved aesthetic.

## Global Constraints

- React 18.3.1 only — no React 19 APIs.
- `prefers-reduced-motion: reduce` → everything static (libs + CSS). Existing global CSS override stays as safety net.
- Preserve ALL a11y: focus-visible, aria labels, keyboard paths (anchor drag, modal Escape, play button), `.visually-hidden` inputs.
- No API/type changes. Presentation only.
- Aurora: DPR cap ≤ 1.25, pause when tab hidden, static CSS fallback when WebGL2 unavailable.
- Perf: transform/opacity-only animations where possible.
- Platform accents (user-approved): TikTok `#25F4EE`, Reels `#E1306C→#833AB4` (purple exception OK), Shorts `#FF0033`, X `#E7E9EA`.
- Commit per task: `feat(ui): ...` style, on branch `Divyanshu-kumar14/feat/frontend-polish-aurora-glass`.

---

### Task 1: Add dependencies

**Files:**
- Modify: `frontend/package.json`

- [ ] **Step 1:** `npm install motion animejs ogl` in `frontend/`
- [ ] **Step 2:** Verify `npm run build` passes
- [ ] **Step 3:** Commit `build(ui): add motion, animejs, ogl deps`

### Task 2: Design tokens + glass CSS foundation

**Files:**
- Modify: `frontend/src/index.css`

- [ ] **Step 1:** Add to `:root`: glass tokens (`--glass-bg`, `--glass-bg-strong`, `--glass-border`, `--glass-highlight`, `--glass-blur`), platform accents (`--plat-tiktok`, `--plat-reels-a/b`, `--plat-shorts`, `--plat-x`), shine gradient, `--ease-spring`.
- [ ] **Step 2:** Add `.glass`, `.glass::before` highlight, `.gradient-text`, `.shine-sweep`, `.plat-dot`, `.plat-wash`, `.summary-chip` utilities.
- [ ] **Step 3:** Add `.aurora-bg`, `.aurora-vignette`, `.aurora-fallback` fixed layers; give `.app` `position: relative; z-index: 2`.
- [ ] **Step 4:** Build check + commit `style(ui): add glass and aurora design tokens`

### Task 3: AuroraBackground component

**Files:**
- Create: `frontend/src/ui/AuroraBackground.tsx`

**Interfaces:**
- Exports: `AuroraBackground` (default export, no props) → renders `<div className="aurora-bg">` (WebGL canvas or `.aurora-fallback`) + `<div className="aurora-vignette">`.
- Consumed by: App.tsx.

- [ ] **Step 1:** Vendor the react-bits Aurora shader (VERT/FRAG, ogl Renderer/Program/Mesh/Triangle/Color) with: MIT attribution comment, `colorStops = ['#ff6b35', '#2dd4bf', '#ffb347']`, container opacity 0.6, `dpr: Math.min(devicePixelRatio, 1.25)` in Renderer options, rAF loop gated on `document.hidden`, full cleanup (cancel rAF, remove canvas, lose context).
- [ ] **Step 2:** If `!window.WebGL2RenderingContext` or `prefers-reduced-motion: reduce` → render `.aurora-fallback` (static CSS gradient blobs) instead of canvas.
- [ ] **Step 3:** Build check + commit `feat(ui): add aurora background component`

### Task 4: Motion kit primitives

**Files:**
- Create: `frontend/src/ui/Reveal.tsx`, `frontend/src/ui/Stagger.tsx`, `frontend/src/ui/CountUp.tsx`, `frontend/src/ui/Shine.tsx`

**Interfaces:**
- `Reveal({ children, delay = 0, y = 14, className? })` — motion.div fade+rise spring (`type: "spring", stiffness: 260, damping: 26`); returns plain div under reduced motion.
- `Stagger({ children, gap = 0.08, startDelay = 0, className? })` — wraps each child in motion.div with `delay: startDelay + i * gap`; plain div under reduced motion.
- `CountUp({ value, duration = 900, className? })` — span; anime.js `animate(obj, { v: value, easing: "out(2)", onUpdate })` on mount, integer textContent; skip animation under reduced motion (render value immediately).
- `Shine({ delay = 0, className? })` — `<span className="shine-sweep">`; anime.js `animate(el, { translateX: ["-140%", "140%"], duration: 1100, easing: "inOut(3)", delay })` on mount; render nothing under reduced motion.
- All import from `motion/react` (`motion`, `useReducedMotion`) and `animejs` (`animate`).

- [ ] **Step 1:** Write all four files (typed, isolated, reduced-motion aware)
- [ ] **Step 2:** Build check + commit `feat(ui): add motion kit primitives`

### Task 5: App shell + header

**Files:**
- Modify: `frontend/src/App.tsx`

- [ ] **Step 1:** Render `<AuroraBackground />` once at app root (before `.app`).
- [ ] **Step 2:** Header: wrap in `Reveal` (slide-down), `.header` becomes glass sticky (`position: sticky; top: 0; backdrop-filter: blur(14px); background: rgba(11,14,20,0.55); border-bottom: 1px solid var(--glass-border)`; `.app` top padding → 0). Brand mark: pulsing glow animation. Tagline: `.gradient-text`. "New job" button: ghost-glass.
- [ ] **Step 3:** Error banner: slide-in animation class. Footer: glass hairline border.
- [ ] **Step 4:** Build check + commit `feat(ui): polish app shell and header`

### Task 6: UploadDropzone polish

**Files:**
- Modify: `frontend/src/components/UploadDropzone.tsx`

- [ ] **Step 1:** Dropzone → `.glass` panel (solid border; dragging: accent border + glow shadow + `scale(1.01)`).
- [ ] **Step 2:** File-pick chips → glass + hover lift (`translateY(-2px)`, accent border).
- [ ] **Step 3:** Parse preview → glass chip; cue count → `<CountUp value={preview.count} />`.
- [ ] **Step 4:** Submit button: CSS shine sweep on hover + existing press scale.
- [ ] **Step 5:** Build check + commit `feat(ui): polish upload screen`

### Task 7: JobProgress polish (calm)

**Files:**
- Modify: `frontend/src/components/JobProgress.tsx`

- [ ] **Step 1:** Wrap rows in `Stagger` (gap 0.07, startDelay 0.1).
- [ ] **Step 2:** `.bar-fill` gradient (orange→amber) + CSS sheen sweep; active platform (`v.status === "rendering"`) row gets `.active` glow class.
- [ ] **Step 3:** Badge pop animation on done/failed (CSS scale keyframe).
- [ ] **Step 4:** Build check + commit `feat(ui): polish progress screen`

### Task 8: ResultGrid summary + stagger

**Files:**
- Modify: `frontend/src/components/ResultGrid.tsx`

- [ ] **Step 1:** Summary chip above grid: `Reveal` + glass `.summary-chip` — "4/4 versions · X/20 checks PASS" with `<CountUp>` for versions done and checks passed (computed from job state; total checks = sum of per-version checks lengths).
- [ ] **Step 2:** Wrap grid in `Stagger` (gap 0.09, startDelay 0.15); add CSS so grid wrapper children stretch (`display: flex` + card `flex: 1`).
- [ ] **Step 3:** Build check + commit `feat(ui): add results summary and stagger`

### Task 9: PlatformCard liquid glass + checklist + modal

**Files:**
- Modify: `frontend/src/components/PlatformCard.tsx`, `frontend/src/components/Checklist.tsx`

- [ ] **Step 1:** Card: `data-platform={platform}` attr; `.card` → glass + `--plat` accent; add `.plat-wash` (top radial gradient in accent) + `.plat-dot` next to `<h3>`; hover: accent border tint + glow shadow + lift.
- [ ] **Step 2:** Still: keep ALL pointer/keyboard logic byte-identical; add `<Shine delay={i * 0.15} />` inside `.still-frame` (renders only after img load — gate by `imgLoaded`).
- [ ] **Step 3:** Checklist: `motion.li` rows, `initial={{ opacity: 0, x: -6 }}`, stagger `delay: 0.05 * i`, spring.
- [ ] **Step 4:** Modal: wrap in `<AnimatePresence>`; modal fade + body scale/y spring; exit animations; Escape behavior unchanged.
- [ ] **Step 5:** Download button: shine hover (CSS `::after` sweep) + lift; "Copy spec" ghost-glass.
- [ ] **Step 6:** Build check + commit `feat(ui): liquid-glass platform cards and modal`

### Task 10: Final verification

- [ ] **Step 1:** `npm run build` (tsc + vite) — must pass clean.
- [ ] **Step 2:** Start dev server (`npm run dev`), verify: aurora renders, glass visible on upload screen, drop file states work, reduced-motion toggle freezes animations (devtools emulation), no console errors.
- [ ] **Step 3:** `git status` clean review + final commit if anything outstanding.