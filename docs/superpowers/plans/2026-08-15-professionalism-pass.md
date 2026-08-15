# Professionalism Pass Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Professionalize the Edit-Once frontend across typography, icons, copy, structure, and tone while keeping the aurora/glass identity and touching zero API/type/behavior logic.

**Architecture:** Presentation-only refactor over the existing motion-kit UI. Type tokens extend `:root` in `index.css`; status/result display labels live next to the existing `PLATFORM_LABELS` in `types.ts`; icons come from `lucide-react` (tree-shaken); Inter Variable is loaded via `@fontsource-variable/inter`. Copy follows one rule: headline states the outcome, technical detail lives behind `<details>`.

**Tech Stack:** Vite + React 18.3 + TypeScript (strict), motion (framer-motion successor), anime.js, ogl, hand-rolled CSS. New deps: `@fontsource-variable/inter`, `lucide-react`.

## Global Constraints

- **Zero behavior change**: no API calls, no state logic, no type-shape changes. Only presentation and display strings.
- **Keep all CSS class names and `data-platform` attributes** — existing QA scripts and styles depend on them. Only *text content* of badges changes, never their classes.
- **Copy is verbatim from the spec** (`docs/superpowers/specs/2026-08-15-professionalism-pass-design.md` §5 table). Do not reword.
- **Reduced motion must keep working**: all new motion uses existing `Reveal`/`Stagger` primitives or motion's `useReducedMotion`; the global `prefers-reduced-motion` override already exists.
- **Verification pattern** (no unit-test infra exists — established in the previous polish session):
  - Build gate: `cd frontend && npm run build` must pass with TS strict.
  - Browser gate: node scripts via `/tmp/opencode/qa` using `playwright-core` + executable `~/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome`.
  - Servers must be running for browser gates: Vite on :5173 and `app.main:app` on :8000 (start with `./scripts/run.sh` or the nohup commands from the previous session).
  - Every QA script asserts `errors.length === 0` (console + pageerror).
- Commit style: conventional, scope `(ui)` (or `build`/`docs` where fitting), one commit per task.

---

### Task 1: Load Inter Variable + add lucide-react

**Files:**
- Modify: `frontend/package.json` (+ `package-lock.json`)
- Modify: `frontend/src/main.tsx:1-4`
- Test: `/tmp/opencode/qa/t1-font.js` (create)

**Interfaces:**
- Consumes: nothing (first task).
- Produces: `Inter Variable` available as a real font (the `--font` token already lists `"Inter Variable"` first); `lucide-react` importable in later tasks.

- [ ] **Step 1: Install dependencies**

Run (in `frontend/`):
```bash
npm install @fontsource-variable/inter lucide-react
```
Expected: both appear in `package.json` dependencies; `npm ls @fontsource-variable/inter lucide-react` succeeds.

- [ ] **Step 2: Import the font before the stylesheet**

Edit `frontend/src/main.tsx` so the imports read:
```tsx
import React from "react";
import ReactDOM from "react-dom/client";
import App from "./App";
import "@fontsource-variable/inter";
import "./index.css";
```
The variable font's default `index.css` registers `Inter Variable` with a `wght` axis, so weights 400–800 (including the planned 650) render natively.

- [ ] **Step 3: Build gate**

Run: `cd frontend && npm run build`
Expected: builds clean (vite output to `../backend/app/static`), no TS errors.

- [ ] **Step 4: Browser gate — computed font-family resolves to Inter Variable**

Create `/tmp/opencode/qa/t1-font.js`:
```js
const { chromium } = require("playwright-core");
const EXEC = process.env.HOME + "/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
(async () => {
  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const family = await page.evaluate(() => {
    const el = document.querySelector(".header-inner h1") ?? document.querySelector("h1, h2");
    const cs = getComputedStyle(el ?? document.body);
    const doc = document.fonts.check('16px "Inter Variable"');
    return { family: cs.fontFamily, loaded: doc };
  });
  console.log(JSON.stringify(family));
  if (errors.length) throw new Error("console errors: " + JSON.stringify(errors));
  if (!family.loaded) throw new Error("Inter Variable not loaded — check the fontsource import");
  console.log("T1 OK — Inter Variable:", family.loaded);
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
```
Run: `node /tmp/opencode/qa/t1-font.js`
Expected: `family` lists `Inter Variable` first and `loaded: true`.

- [ ] **Step 5: Commit**

```bash
git add frontend/package.json frontend/package-lock.json frontend/src/main.tsx
git commit -m "build(ui): load Inter Variable font, add lucide-react"
```

---

### Task 2: Type scale + label tokens

**Files:**
- Modify: `frontend/src/index.css:10-33` (`:root` tokens), `frontend/src/index.css:164-169` (brand), `frontend/src/index.css:227` (dropzone h2), `frontend/src/index.css:295` (`.progress h2, .results h2`), `frontend/src/index.css:391` (`.card-head h3`), `frontend/src/index.css:246` (`.file-label`)
- Test: `/tmp/opencode/qa/t2-type.js` (create)

**Interfaces:**
- Consumes: Task 1 (Inter Variable font).
- Produces: CSS custom props `--fs-display`, `--fs-h2`, `--fs-h3`, `--fs-body`, `--fs-label`; `.label-caps` utility class used by later tasks.

- [ ] **Step 1: Add the type tokens**

In `:root` (after the `--shine`/`--ease-spring` lines), add:
```css
  /* Type scale (professional: outcome headlines, quiet labels). */
  --fs-display: 30px;   /* hero headline, weight 600 */
  --fs-h2: 24px;        /* section headings, weight 650 (variable font interpolates) */
  --fs-h3: 16px;        /* card titles, weight 600 */
  --fs-body: 15px;
  --fs-label: 11px;     /* badges, file labels — uppercase +0.08em */
```

- [ ] **Step 2: Apply the scale + kill the logo-sticker tracking**

Edits in `index.css`:
- `.brand h1` (line ~168): remove `letter-spacing: 0.3px;` (keep `font-size: 22px`).
- `.progress h2, .results h2` (line ~295): `font-size: 22px` → `font-size: var(--fs-h2);` and add `font-weight: 650;` — replace the line with:
```css
.progress h2, .results h2 { font-size: var(--fs-h2); font-weight: 650; margin: 0 0 6px; }
```
- `.dropzone h2` (line ~227): `font-size: 24px` → `font-size: var(--fs-h2);` (keep weight; `font-weight: 650` for consistency):
```css
.dropzone h2 { margin: 0 0 8px; font-size: var(--fs-h2); font-weight: 650; }
```
- `.card-head h3` (line ~391): `font-size: 16px` → `font-size: var(--fs-h3);` and `font-weight: 600` (already 600 via tag or add it).
- Add a reusable caps-label utility next to `.file-label`:
```css
.label-caps { font-size: var(--fs-label); font-weight: 700; text-transform: uppercase; letter-spacing: 0.08em; }
```
- `.file-label` (line ~246): keep existing look, add inline-flex for upcoming icons:
```css
.file-label { display: inline-flex; align-items: center; gap: 6px; font-weight: 700; font-size: 14px; letter-spacing: 0.4px; }
```

- [ ] **Step 3: Build gate**

Run: `cd frontend && npm run build` — clean.

- [ ] **Step 4: Browser gate — headings use the new scale**

Create `/tmp/opencode/qa/t2-type.js` (upload screen only, no render needed):
```js
const { chromium } = require("playwright-core");
const EXEC = process.env.HOME + "/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
(async () => {
  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const out = await page.evaluate(() => {
    const fs = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el).fontSize : null; };
    const ls = (sel) => { const el = document.querySelector(sel); return el ? getComputedStyle(el).letterSpacing : null; };
    return {
      dropzoneH2: fs(".dropzone h2"),
      brandH1: fs(".brand h1"), brandH1Tracking: ls(".brand h1"),
      labelCaps: (() => { const s = document.createElement("span"); s.className = "label-caps"; document.body.appendChild(s); const v = getComputedStyle(s).fontSize; s.remove(); return v; })(),
    };
  });
  console.log(JSON.stringify(out));
  if (errors.length) throw new Error("console errors: " + JSON.stringify(errors));
  if (out.dropzoneH2 !== "24px") throw new Error("dropzone h2 not 24px: " + out.dropzoneH2);
  if (out.brandH1Tracking !== "normal") throw new Error("brand h1 tracking not removed: " + out.brandH1Tracking);
  console.log("T2 OK");
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
```
Run: `node /tmp/opencode/qa/t2-type.js`
Expected: `dropzoneH2: "24px"`, `brandH1Tracking: "normal"`, `labelCaps: "11px"`.

- [ ] **Step 5: Commit**

```bash
git add frontend/src/index.css
git commit -m "style(ui): type scale tokens, professional heading weight, caps labels"
```

---

### Task 3: Tone — calm the aurora, shine, and springs

**Files:**
- Modify: `frontend/src/index.css` — `.aurora-bg` (line ~62), `.aurora-vignette` (line ~69), `.aurora-fallback` (line ~77), `--shine` (line 31), `--ease-spring` (line 32), `brand-pulse` (line ~160)
- Modify: `frontend/src/ui/AuroraBackground.tsx:120` (`COLOR_STOPS`)
- Modify: `frontend/src/ui/Reveal.tsx:14` (default `y`), `frontend/src/ui/Stagger.tsx:26,28-32` (travel + damping)
- Modify: `frontend/src/components/PlatformCard.tsx:322-325` (modal spring — lines may shift after Task 4; edit by content)
- Test: `/tmp/opencode/qa/t3-tone.js` (create)

**Interfaces:**
- Consumes: nothing new (independent of Tasks 1–2).
- Produces: calmer visual constants; no later task depends on these values.

- [ ] **Step 1: Aurora layers — less presence, more vignette**

In `index.css`:
- `.aurora-bg` (line ~65): `opacity: 0.6;` → `opacity: 0.4;`
- `.aurora-fallback` (line ~78): add `opacity: 0.4;` (same calmer presence for the no-WebGL path)
- `.aurora-vignette` (line ~73-74): strengthen the darks:
```css
  background:
    radial-gradient(ellipse at 50% 35%, transparent 52%, rgba(11, 14, 20, 0.78) 100%),
    linear-gradient(rgba(11, 14, 20, 0.45), transparent 28%, transparent 72%, rgba(11, 14, 20, 0.55));
```

- [ ] **Step 2: Soften the palette**

In `frontend/src/ui/AuroraBackground.tsx:120`:
```ts
const COLOR_STOPS = ["#f2713c", "#34c8b8", "#f5a94a"];
```
(Softened versions of `#ff6b35`, `#2dd4bf`, `#ffb347` — same family, lower saturation.)

- [ ] **Step 3: Calm the shine, ease, and brand pulse**

In `index.css`:
- Line ~31: `--shine: linear-gradient(100deg, transparent 20%, rgba(255, 255, 255, 0.10) 50%, transparent 80%);` (alpha 0.14 → 0.10)
- Line ~32: `--ease-spring: cubic-bezier(0.34, 1.15, 0.64, 1);` (overshoot 1.4 → 1.15 — kills the rubbery bounce on badges/bars)
- `@keyframes brand-pulse` (~line 160-163): `0 0 26px rgba(255, 107, 53, 0.6)` → `0 0 18px rgba(255, 107, 53, 0.55)` (keep the 12px/0.35 base)

- [ ] **Step 4: Calmer motion defaults**

- `frontend/src/ui/Reveal.tsx:14`: `y = 14` → `y = 10`
- `frontend/src/ui/Stagger.tsx:26-32`: travel `y: 14` → `y: 10`; transition `stiffness: 240, damping: 24` → `stiffness: 240, damping: 28`
- `frontend/src/components/PlatformCard.tsx` modal-body transition: `{ type: "spring", stiffness: 300, damping: 28 }` → `{ type: "spring", stiffness: 260, damping: 30 }`

- [ ] **Step 5: Build gate**

Run: `cd frontend && npm run build` — clean.

- [ ] **Step 6: Browser gate — constants in the DOM**

Create `/tmp/opencode/qa/t3-tone.js` (upload screen):
```js
const { chromium } = require("playwright-core");
const EXEC = process.env.HOME + "/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
(async () => {
  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage();
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  const out = await page.evaluate(() => {
    const vg = getComputedStyle(document.querySelector(".aurora-vignette"));
    const bg = getComputedStyle(document.querySelector(".aurora-bg"));
    return {
      auroraOpacity: bg.opacity,
      vignetteDark: vg.backgroundImage.includes("0.78"),
      ease: getComputedStyle(document.documentElement).getPropertyValue("--ease-spring").trim(),
      shine: getComputedStyle(document.documentElement).getPropertyValue("--shine").trim(),
    };
  });
  console.log(JSON.stringify(out));
  if (errors.length) throw new Error("console errors: " + JSON.stringify(errors));
  if (out.auroraOpacity !== "0.4") throw new Error("aurora opacity: " + out.auroraOpacity);
  if (!out.vignetteDark) throw new Error("vignette not strengthened");
  console.log("T3 OK");
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
```
Run: `node /tmp/opencode/qa/t3-tone.js`
Expected: `auroraOpacity: "0.4"`, `vignetteDark: true`.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/index.css frontend/src/ui/AuroraBackground.tsx frontend/src/ui/Reveal.tsx frontend/src/ui/Stagger.tsx frontend/src/components/PlatformCard.tsx
git commit -m "style(ui): calm aurora presence, shine, brand pulse, and motion springs"
```

---

### Task 4: Platform cards — icons, status labels, professional copy

**Files:**
- Modify: `frontend/src/types.ts` — add `STATUS_LABEL`, `RESULT_LABEL` after `PLATFORM_LABELS` (line ~64)
- Modify: `frontend/src/components/PlatformCard.tsx` — imports (lines 1-7), failed block (lines 49-57), rendering variant badge (line ~165), header badge (line ~196), Play button (line ~244), safe-area toggle (lines ~246-254), fit labels (lines ~275-283), Copy spec (line ~302), modal Close (line ~330)
- Modify: `frontend/src/components/Checklist.tsx` — badge text (line 22-24)
- Modify: `frontend/src/index.css` — `.stderr-details` styles (add near line ~393)
- Test: `/tmp/opencode/qa/t4-cards.js` (create) — needs a real render (upload → results)

**Interfaces:**
- Consumes: Tasks 1–3 (icons available; type tokens; calm motion).
- Produces: `STATUS_LABEL` / `RESULT_LABEL` maps consumed by Task 5 (`JobProgress`, `ResultGrid`).

- [ ] **Step 1: Label maps in `types.ts`**

Append after `PLATFORM_LABELS`:
```ts
/** Display labels for version/job status — product voice, not dev-speak. */
export const STATUS_LABEL: Record<VersionStatus, string> = {
  queued: "Queued",
  rendering: "Processing",
  done: "Ready",
  failed: "Failed",
};

/** Display labels for verification check results. */
export const RESULT_LABEL: Record<CheckLevel, string> = {
  pass: "Passed",
  warn: "Review",
  fail: "Failed",
};
```

- [ ] **Step 2: PlatformCard — imports and status labels**

- Extend the lucide import: add `import { Play, Download, Copy, X } from "lucide-react";`
- Import the label maps: `import { STATUS_LABEL } from "../types";` (extend the existing `import type { ... } from "../types"` — types stay type-only, values import separately).
- Both badge renderings (`{version.status}` in the rendering variant and the done card header) → `{STATUS_LABEL[version.status]}`.

- [ ] **Step 3: Failed card — friendly headline + collapsible detail**

Replace the failed block:
```tsx
  if (version.status === "failed") {
    return (
      <article className="card failed" data-platform={platform}>
        <h3>{label}</h3>
        <div className="error-banner">This version failed to render</div>
        <details className="stderr-details">
          <summary>Technical details</summary>
          <pre className="stderr">{version.error}</pre>
        </details>
      </article>
    );
  }
```

- [ ] **Step 4: Play, safe areas, fit labels, copy, modal close**

- Play button: `<button className="btn tiny" onClick={() => setPlaying(true)}><Play size={14} fill="currentColor" aria-hidden="true" /> Play</button>`
- Safe-area toggle: `{overlay ? "Hide safe areas" : "Show safe areas"}` (both occurrences of the ternary string)
- Fit toggle: `Crop` stays; `Blur-pad` → `Blur fill`
- Fit hint: `"Blur-pad letterbox — no crop anchor"` → `"Letterboxes with a blurred background"`
- Copy button: `<button className="btn ghost" onClick={copySpec}><Copy size={14} aria-hidden="true" /> Copy details</button>`
- Modal close: `<button className="btn ghost" onClick={() => setPlaying(false)}><X size={14} aria-hidden="true" /> Close</button>`

- [ ] **Step 5: Checklist — result labels**

In `frontend/src/components/Checklist.tsx`: import `RESULT_LABEL` from `"../types"`; replace `{check.result.toUpperCase()}` with `{RESULT_LABEL[check.result]}` (the `LEVEL_CLASS` map stays — it drives styling classes).

- [ ] **Step 6: CSS for the collapsible error**

In `index.css` near `.stderr` (~line 393), add:
```css
.stderr-details { margin-top: 12px; }
.stderr-details summary { cursor: pointer; font-size: 12px; color: var(--muted); user-select: none; }
.stderr-details[open] summary { margin-bottom: 8px; }
```

- [ ] **Step 7: Build gate**

Run: `cd frontend && npm run build` — clean (watch unused imports: every lucide icon must be used).

- [ ] **Step 8: Browser gate — badges, labels, icons, collapse**

Create `/tmp/opencode/qa/t4-cards.js` — upload the fixtures, wait for `.results` (needs backend running):
```js
const { chromium } = require("playwright-core");
const EXEC = process.env.HOME + "/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
const VIDEO = "/home/rtx/Desktop/hackathonProjects/Edit-Once/backend/tests/fixtures/fixture.mp4";
const SRT = "/home/rtx/Desktop/hackathonProjects/Edit-Once/backend/tests/fixtures/fixture.srt";
(async () => {
  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.setInputFiles('input[type="file"][accept=".mp4"]', VIDEO);
  await page.setInputFiles('input[type="file"][accept=".srt,.vtt"]', SRT);
  await page.waitForTimeout(300);
  await page.click(".btn.primary");
  await page.waitForSelector(".results", { timeout: 240000 });
  await page.waitForTimeout(2500);
  const out = await page.evaluate(() => {
    const first = document.querySelector(".grid .card");
    const text = first.textContent;
    return {
      readyBadge: first.querySelector(".badge")?.textContent.trim(),
      hasPlayIcon: !!first.querySelector(".still-actions svg"),
      playLabel: first.querySelector(".still-actions")?.textContent.trim(),
      hasBlurFill: text.includes("Blur fill"),
      hasSafeAreas: text.includes("safe areas"),
      hasCopyDetails: text.includes("Copy details"),
      hasDownloadIcon: !!first.querySelector(".card-foot svg"),
      checkBadges: [...document.querySelectorAll(".grid .card .check-row .badge")].slice(0, 6).map((b) => b.textContent.trim()),
      noOldWords: !text.includes("Blur-pad") && !text.includes("Copy spec") && !text.includes("PASS"),
    };
  });
  console.log(JSON.stringify(out));
  if (errors.length) throw new Error("console errors: " + JSON.stringify(errors));
  if (out.readyBadge !== "Ready") throw new Error("badge: " + out.readyBadge);
  if (!out.hasPlayIcon || !out.hasDownloadIcon) throw new Error("missing SVG icons");
  if (!out.hasBlurFill || !out.hasSafeAreas || !out.hasCopyDetails) throw new Error("copy not updated");
  if (out.checkBadges.some((b) => b === "PASS" || b === "WARN" || b === "FAIL")) throw new Error("old check labels: " + JSON.stringify(out.checkBadges));
  console.log("T4 OK — checks:", JSON.stringify(out.checkBadges));
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
```
Run: `node /tmp/opencode/qa/t4-cards.js`
Expected: `readyBadge: "Ready"`, icons present, new copy present, no `PASS`/`WARN`/`FAIL` in check badges, no old words.

- [ ] **Step 9: Commit**

```bash
git add frontend/src/types.ts frontend/src/components/PlatformCard.tsx frontend/src/components/Checklist.tsx frontend/src/index.css
git commit -m "feat(ui): professional card copy, lucide icons, status labels, collapsible errors"
```

---

### Task 5: Upload, progress, results — copy + icons

**Files:**
- Modify: `frontend/src/components/UploadDropzone.tsx` — imports (lines 1-3), h2 (line 66), sub (lines 67-70), file labels (lines 82, 96), submit button (line 124)
- Modify: `frontend/src/components/JobProgress.tsx` — phase string (line 6), row badge (line 22), render label (line 42)
- Modify: `frontend/src/components/ResultGrid.tsx` — h2 (line 37), sub (after line 41), chip (line 34)
- Test: `/tmp/opencode/qa/t5-screens.js` (create) — needs a real render

**Interfaces:**
- Consumes: Task 4 (`STATUS_LABEL`, `RESULT_LABEL` from `types.ts`); lucide icons.
- Produces: final copy strings asserted by Task 7.

- [ ] **Step 1: UploadDropzone — heading, sub, labels, submit**

- Imports: add `import { Film, Captions } from "lucide-react";`
- h2: `Repack one edit for all four platforms` → `Upload your video and captions`
- Sub (`<p className="muted">`): replace the two lines with:
  `Upload your MP4 and caption file — we re-render captions into each platform's safe zone.`
- File labels:
  - `<span className="file-label">🎬 Video</span>` → `<span className="file-label"><Film size={14} aria-hidden="true" /> Video file</span>`
  - `<span className="file-label">💬 Captions</span>` → `<span className="file-label"><Captions size={14} aria-hidden="true" /> Caption file</span>`
- Submit button: `{canSubmit ? "Repack for 4 platforms →" : "Add video + captions to start"}` → `{canSubmit ? "Create 4 versions" : "Add video + captions to start"}`

- [ ] **Step 2: JobProgress — phase + badges**

- Line 6: `const phase = job.status === "analyzing" ? "Analyzing scene crop anchors…" : "Rendering…";` → `"Rendering your video…"`
- Line 22: `const label = v.status === "done" ? "done" : v.status === "failed" ? "failed" : \`${v.progress}%\`;` → `const label = v.status === "done" || v.status === "failed" ? STATUS_LABEL[v.status] : \`${v.progress}%\`;`
- Add `STATUS_LABEL` to the imports from `"../types"` (keep the `type` import separate as in Task 4 Step 2).

- [ ] **Step 3: ResultGrid — headline, sub-line, chip**

- Line 34: `checks PASS` → `checks passed`
- Line 37: `<h2>4 platform-correct versions</h2>` → `<h2>Your versions are ready</h2>`
- After the `<p className="muted">{job.input?...}` line (line ~41), add a second sub-line:
```tsx
        <p className="muted">Verified against each platform's spec.</p>
```

- [ ] **Step 4: Build gate**

Run: `cd frontend && npm run build` — clean.

- [ ] **Step 5: Browser gate — screen copy**

Create `/tmp/opencode/qa/t5-screens.js` — same harness as T4 (upload fixtures, wait for `.results`). Assert in order:
1. Before upload: `.dropzone h2` text is `Upload your video and captions`; `.file-row` contains `Video file` and `Caption file`; both file-pick rows contain an `svg`; no `🎬`/`💬` anywhere in `.file-row`.
2. Click submit; while the progress screen is up (wait for `.progress`), assert `h2` text contains `Rendering your video…` and badge texts come from `Queued | Processing | Ready | Failed` (at least the set appears).
3. On `.results`: `.results h2` is `Your versions are ready`; page text includes `Verified against each platform's spec.`; `.summary-checks` text ends with `checks passed`.
4. `errors.length === 0`.

Run: `node /tmp/opencode/qa/t5-screens.js`
Expected: all assertions pass.

- [ ] **Step 6: Commit**

```bash
git add frontend/src/components/UploadDropzone.tsx frontend/src/components/JobProgress.tsx frontend/src/components/ResultGrid.tsx
git commit -m "style(ui): product-voice copy on upload, progress, and results screens"
```

---

### Task 6: Upload hero, platform pills, how-it-works strip

**Files:**
- Modify: `frontend/src/App.tsx` — imports (lines 1-9), header tagline (line ~96), New job button (line ~101), main (lines ~114-120)
- Modify: `frontend/src/index.css` — hero/pills/steps styles (add after the dropzone section, ~line 280)
- Test: `/tmp/opencode/qa/t6-hero.js` (create) — upload screen only + one mobile overflow check

**Interfaces:**
- Consumes: `PLATFORM_ORDER`, `PLATFORM_LABELS` from `types.ts` (already exist); `Reveal`, `Stagger` primitives; Task 2 type tokens.
- Produces: `.hero`, `.pills`, `.pill`, `.how-it-works`, `.step`, `.step-num` CSS hooks (asserted in Task 7).

- [ ] **Step 1: App.tsx — imports and tagline**

- Extend the types import: `import type { JobState, PlatformId, VersionOptions } from "./types";` and add value imports: `import { PLATFORM_LABELS, PLATFORM_ORDER } from "./types";`
- Add `import { Upload } from "lucide-react";`
- Tagline (line ~96): `<p className="tagline gradient-text">Publish Everywhere — platform-correct shorts, verified.</p>` → `<p className="tagline gradient-text">One edit. Four platform-perfect videos.</p>`
- New job button (line ~101): `<button className="btn ghost" onClick={handleReset}>New job</button>` → `<button className="btn ghost" onClick={handleReset}><Upload size={14} aria-hidden="true" /> New project</button>`

- [ ] **Step 2: Hero block above the dropzone**

Inside `<main>`, before the `screen === "upload"` dropzone, add:
```tsx
        {screen === "upload" && (
          <Reveal>
            <section className="hero">
              <h1 className="hero-title">One edit. Four platforms. Zero re-editing.</h1>
              <p className="muted hero-sub">
                Upload once — get platform-correct videos for TikTok, Reels, Shorts and X,
                with captions re-rendered into each platform's safe zone.
              </p>
              <div className="pills" aria-label="Output platforms">
                {PLATFORM_ORDER.map((pid) => (
                  <span key={pid} className="pill" data-platform={pid}>
                    <span className="plat-dot" aria-hidden="true" />
                    {PLATFORM_LABELS[pid]}
                  </span>
                ))}
              </div>
            </section>
          </Reveal>
        )}
```

- [ ] **Step 3: How-it-works strip below the dropzone**

In the same `screen === "upload"` branch, after `<UploadDropzone ... />`:
```tsx
          <Stagger gap={0.12} className="how-it-works" aria-label="How it works">
            <div className="step">
              <span className="step-num" aria-hidden="true">1</span>
              <div>
                <h3>Upload</h3>
                <p className="muted">One clean edit and its caption file.</p>
              </div>
            </div>
            <div className="step">
              <span className="step-num" aria-hidden="true">2</span>
              <div>
                <h3>We render</h3>
                <p className="muted">Four platform-correct versions.</p>
              </div>
            </div>
            <div className="step">
              <span className="step-num" aria-hidden="true">3</span>
              <div>
                <h3>Export</h3>
                <p className="muted">Replay or download each one.</p>
              </div>
            </div>
          </Stagger>
```
Note: `Stagger` renders a plain `<div>` under reduced motion and its children are wrapped in `motion.div` — the existing `.how-it-works` grid CSS must target the wrapper class; children inside motion wrappers are `.step` (see Step 4 — use `.how-it-works > div` for grid items, or apply grid on the class and let the wrappers be the cells: `.how-it-works { display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px; }` — the motion wrappers ARE the grid cells and each contains `.step`; add `.how-it-works .step { height: 100%; }`).

- [ ] **Step 4: CSS — hero, pills, steps**

Add after the dropzone styles (~line 280):
```css
/* --- upload hero + how-it-works ------------------------------------------- */
.hero { max-width: 720px; margin: 44px auto 28px; text-align: center; }
.hero-title { margin: 0 0 10px; font-size: var(--fs-display); font-weight: 600; }
.hero-sub { margin: 0 auto 18px; max-width: 560px; }
.pills { display: flex; flex-wrap: wrap; justify-content: center; gap: 10px; }
.pill {
  display: inline-flex; align-items: center; gap: 6px;
  padding: 6px 14px; border-radius: 999px;
  background: var(--glass-bg); border: 1px solid var(--glass-border);
  font-size: 13px; font-weight: 600; color: var(--text);
}
.pill .plat-dot { width: 8px; height: 8px; }

.how-it-works {
  display: grid; grid-template-columns: repeat(3, 1fr); gap: 16px;
  margin: 32px 0 8px;
}
.how-it-works .step {
  height: 100%;
  display: flex; gap: 12px; align-items: flex-start;
  background: var(--glass-bg); border: 1px solid var(--glass-border);
  border-radius: 14px; padding: 16px;
}
.how-it-works .step h3 { margin: 0 0 4px; font-size: var(--fs-h3); }
.how-it-works .step p { margin: 0; font-size: 13px; }
.step-num {
  flex: none; width: 26px; height: 26px; border-radius: 50%;
  display: inline-flex; align-items: center; justify-content: center;
  background: var(--accent); color: #0b0e14;
  font-size: 13px; font-weight: 800;
}
```
And in the `@media (max-width: 720px)` block (line ~553), add:
```css
  .hero { margin: 28px auto 20px; }
  .how-it-works { grid-template-columns: 1fr; }
```

- [ ] **Step 5: Build gate**

Run: `cd frontend && npm run build` — clean.

- [ ] **Step 6: Browser gate — hero, pills, steps, mobile overflow**

Create `/tmp/opencode/qa/t6-hero.js`:
```js
const { chromium } = require("playwright-core");
const EXEC = process.env.HOME + "/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
(async () => {
  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.waitForTimeout(800);
  const desk = await page.evaluate(() => ({
    title: document.querySelector(".hero-title")?.textContent.trim(),
    pillCount: document.querySelectorAll(".pill").length,
    stepCount: document.querySelectorAll(".how-it-works .step").length,
    tagline: document.querySelector(".tagline")?.textContent.trim(),
    stepsColumns: getComputedStyle(document.querySelector(".how-it-works")).gridTemplateColumns.split(" ").length,
  }));
  await page.setViewportSize({ width: 390, height: 844 });
  await page.waitForTimeout(500);
  const mob = await page.evaluate(() => ({
    overflowX: document.documentElement.scrollWidth > window.innerWidth,
    stepsColumns: getComputedStyle(document.querySelector(".how-it-works")).gridTemplateColumns.split(" ").length,
  }));
  console.log(JSON.stringify({ desk, mob }));
  if (errors.length) throw new Error("console errors: " + JSON.stringify(errors));
  if (desk.title !== "One edit. Four platforms. Zero re-editing.") throw new Error("hero title: " + desk.title);
  if (desk.pillCount !== 4 || desk.stepCount !== 3) throw new Error("pill/step count");
  if (desk.stepsColumns !== 3 || mob.stepsColumns !== 1) throw new Error("steps grid responsive");
  if (mob.overflowX) throw new Error("horizontal overflow at 390px");
  console.log("T6 OK");
  await browser.close();
})().catch((e) => { console.error("FAILED:", e.message); process.exit(1); });
```
Run: `node /tmp/opencode/qa/t6-hero.js`
Expected: title/pills/steps present, 3 columns desktop → 1 column mobile, no horizontal overflow at 390px.

- [ ] **Step 7: Commit**

```bash
git add frontend/src/App.tsx frontend/src/index.css
git commit -m "feat(ui): upload hero with platform pills and how-it-works strip"
```

---

### Task 7: Full E2E regression + sign-off

**Files:**
- Test: `/tmp/opencode/qa/t7-regression.js` (create)
- No source changes expected — if the regression finds a defect, fix it in a separate commit following the repo's `fix(ui):` style.

**Interfaces:**
- Consumes: everything from Tasks 1–6.

- [ ] **Step 1: Write the regression script**

Create `/tmp/opencode/qa/t7-regression.js` — full flow at all three viewports, asserting **both** the professionalism pass and the previous session's fixes (modal fullscreen, exact 9:16, header full-bleed):
```js
const { chromium } = require("playwright-core");
const EXEC = process.env.HOME + "/.cache/ms-playwright/chromium-1234/chrome-linux64/chrome";
const VIDEO = "/home/rtx/Desktop/hackathonProjects/Edit-Once/backend/tests/fixtures/fixture.mp4";
const SRT = "/home/rtx/Desktop/hackathonProjects/Edit-Once/backend/tests/fixtures/fixture.srt";

async function modalCheck(page, w, h, label) {
  await page.setViewportSize({ width: w, height: h });
  await page.waitForTimeout(500);
  const m = await page.evaluate(() => {
    const v = document.querySelector(".modal video").getBoundingClientRect();
    const modal = document.querySelector(".modal").getBoundingClientRect();
    const vw = window.innerWidth, vh = window.innerHeight;
    const issues = [];
    if (Math.round(modal.width) !== vw || Math.round(modal.height) !== vh) issues.push("modal not fullscreen");
    if (v.bottom > vh + 1 || v.top < 0 || v.left < 0 || v.right > vw + 1) issues.push("video clipped");
    if (Math.abs(v.width / v.height - 9 / 16) > 0.02) issues.push("ratio " + (v.width / v.height).toFixed(3));
    return issues;
  });
  console.log(`  [${label}] ${m.length ? "ISSUES: " + m.join(" | ") : "OK"}`);
  if (m.length) throw new Error(label + " failed: " + m.join(", "));
}

(async () => {
  const browser = await chromium.launch({ executablePath: EXEC });
  const page = await browser.newPage({ viewport: { width: 1440, height: 900 } });
  const errors = [];
  page.on("console", (m) => { if (m.type() === "error") errors.push(m.text()); });
  page.on("pageerror", (e) => errors.push(e.message));

  await page.goto("http://localhost:5173/", { waitUntil: "networkidle" });
  await page.waitForTimeout(600);
  // upload screen: hero + pills + steps + professional copy
  const upload = await page.evaluate(() => ({
    title: document.querySelector(".hero-title")?.textContent.trim(),
    dropzoneH2: document.querySelector(".dropzone h2")?.textContent.trim(),
    fontLoaded: document.fonts.check('16px "Inter Variable"'),
    hasEmoji: /🎬|💬|▶|↓/.test(document.body.textContent),
  }));
  if (upload.title !== "One edit. Four platforms. Zero re-editing.") throw new Error("hero missing");
  if (upload.dropzoneH2 !== "Upload your video and captions") throw new Error("dropzone h2: " + upload.dropzoneH2);
  if (!upload.fontLoaded || upload.hasEmoji) throw new Error("font/emoji check failed");
  await page.screenshot({ path: "/tmp/opencode/qa/pro-upload.png" });

  await page.setInputFiles('input[type="file"][accept=".mp4"]', VIDEO);
  await page.setInputFiles('input[type="file"][accept=".srt,.vtt"]', SRT);
  await page.waitForTimeout(300);
  await page.click(".btn.primary");
  await page.waitForSelector(".progress", { timeout: 30000 });
  const progressText = await page.evaluate(() => document.querySelector(".progress h2")?.textContent.trim());
  if (!/Rendering your video|Analyzing/.test(progressText)) throw new Error("progress copy: " + progressText);
  await page.screenshot({ path: "/tmp/opencode/qa/pro-progress.png" });
  await page.waitForSelector(".results", { timeout: 240000 });
  await page.waitForTimeout(2500);

  const results = await page.evaluate(() => ({
    h2: document.querySelector(".results h2")?.textContent.trim(),
    hasSub: document.body.textContent.includes("Verified against each platform's spec."),
    chips: document.querySelector(".summary-checks")?.textContent.trim(),
    badges: [...document.querySelectorAll(".grid .card .card-head .badge")].map((b) => b.textContent.trim()),
    checkBadges: [...document.querySelectorAll(".check-row .badge")].map((b) => b.textContent.trim()),
    headerLeft: Math.round(document.querySelector(".header").getBoundingClientRect().left),
    headerW: Math.round(document.querySelector(".header").getBoundingClientRect().width),
  }));
  if (results.h2 !== "Your versions are ready" || !results.hasSub) throw new Error("results copy");
  if (!results.chips.includes("checks passed")) throw new Error("chip: " + results.chips);
  if (!results.badges.every((b) => ["Ready", "Queued", "Processing", "Failed"].includes(b))) throw new Error("badges: " + JSON.stringify(results.badges));
  if (results.checkBadges.some((b) => !["Passed", "Review", "Failed"].includes(b))) throw new Error("check badges: " + JSON.stringify(results.checkBadges));
  if (results.headerLeft !== 0 || results.headerW !== 1440) throw new Error("header not full-bleed");
  await page.screenshot({ path: "/tmp/opencode/qa/pro-results.png", fullPage: true });

  await page.locator(".grid .card").first().locator("button", { hasText: "Play" }).click();
  await page.waitForSelector("body > .modal video", { timeout: 5000 });
  await page.waitForTimeout(900);
  await modalCheck(page, 1440, 900, "desktop-wide");
  await modalCheck(page, 1024, 768, "laptop");
  await modalCheck(page, 390, 844, "mobile");
  await page.keyboard.press("Escape");
  await page.waitForTimeout(500);
  if (await page.evaluate(() => document.querySelector("body > .modal") !== null)) throw new Error("modal did not unmount");

  if (errors.length) throw new Error("console errors: " + JSON.stringify(errors));
  console.log("T7 REGRESSION PASS — zero console errors, all viewports green");
  await browser.close();
})().catch((e) => { console.error("REGRESSION FAILED:", e.message); process.exit(1); });
```

- [ ] **Step 2: Run the regression**

Run: `node /tmp/opencode/qa/t7-regression.js`
Expected: every check prints OK; final line `T7 REGRESSION PASS — zero console errors, all viewports green`. If it fails, fix the defect, re-run, then commit the fix separately (`fix(ui): ...`).

- [ ] **Step 3: Final build + verify tree state**

Run: `cd frontend && npm run build` then `git status --short`
Expected: build clean; only expected files modified (all committed by now).

- [ ] **Step 4: Commit**

If any fix was needed in Step 2, commit it now. Otherwise no commit (tasks 1–6 already committed individually).

---

## Self-Review

**Spec coverage:**
- §3 Typography (B) → Task 1 (font load) + Task 2 (scale, tracking, labels) ✓
- §4 Icons (C) → Task 4 (cards/modal) + Task 5 (dropzone chips) ✓
- §5 Copy (A) → Tasks 4 (cards), 5 (screens), 6 (tagline/hero) — every row of the spec table has a home ✓
- §6 Structure (D) → Task 6 (hero, pills, how-it-works, results sub-line) ✓
- §7 Tone (E) → Task 3 ✓
- §8 Files touched → every file mapped to a task ✓
- §9 Verification → Task 7 regression + per-task gates ✓

**Placeholder scan:** no TBD/TODO; every step has concrete code or commands. ✓

**Type consistency:** `STATUS_LABEL: Record<VersionStatus, string>` (Task 4) consumed identically in Task 5; `RESULT_LABEL: Record<CheckLevel, string>` used in Checklist (Task 4); `PLATFORM_ORDER`/`PLATFORM_LABELS` already exported from `types.ts` (verified). Stagger children wrappers handled by `.how-it-works > motion.div` cells — CSS written to match. ✓
