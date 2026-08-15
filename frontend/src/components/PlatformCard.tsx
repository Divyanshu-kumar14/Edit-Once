import { useEffect, useRef, useState } from "react";
import { AnimatePresence, motion } from "motion/react";
import type { PlatformId, VersionOptions, VersionState } from "../types";
import { Checklist } from "./Checklist";
import { SafeZoneOverlay } from "./SafeZoneOverlay";
import { Shine } from "../ui/Shine";

interface Props {
  label: string;
  platform: PlatformId;
  version: VersionState;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
}

const DRAG_THRESHOLD_PX = 6;

export function PlatformCard({ label, platform, version, onRerender }: Props) {
  const [overlay, setOverlay] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [imgLoaded, setImgLoaded] = useState(false);
  // FR-4.3: drag marker (normalized 0..1 within the still).
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef({ active: false, moved: false, startX: 0, startY: 0 });
  // Latest pointer position, ref-backed: pointerup may arrive before the
  // last rAF-flushed setState, so the final anchor must not come from the
  // (possibly stale) dragPos state closure.
  const posRef = useRef<{ x: number; y: number } | null>(null);
  const rafRef = useRef<number | null>(null);
  const suppressClickRef = useRef(false);

  // Cancel a pending rAF on unmount so we never setState after teardown.
  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  // Modal a11y: close on Escape (dialog role is on the element below).
  useEffect(() => {
    if (!playing) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") setPlaying(false);
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [playing]);

  if (version.status === "failed") {
    return (
      <article className="card failed" data-platform={platform}>
        <h3>{label}</h3>
        <div className="error-banner">Render failed</div>
        <pre className="stderr">{version.error}</pre>
      </article>
    );
  }

  const still = version.stills[0] ?? null;
  const spec = version.spec;
  const croppable = version.status === "done" && version.fit === "crop";

  const copySpec = async () => {
    if (!spec) return;
    const text =
      `${label}\n` +
      `Resolution: ${spec.width}×${spec.height}\n` +
      `Duration: ${spec.duration_s.toFixed(1)} s\n` +
      `Safe margins: bottom ${Math.round(spec.margins.bottom * 100)}% · ` +
      `right ${Math.round(spec.margins.right * 100)}% · top ${Math.round(spec.margins.top * 100)}%`;
    try {
      await navigator.clipboard.writeText(text);
    } catch {
      /* clipboard unavailable — non-critical */
    }
  };

  // -- FR-4.3 anchor drag ---------------------------------------------------
  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!croppable) return;
    // Keep the stream on the still even when the pointer leaves its bounds.
    e.currentTarget.setPointerCapture(e.pointerId);
    dragRef.current = { active: true, moved: false, startX: e.clientX, startY: e.clientY };
  };

  const onPointerMove = (e: React.PointerEvent<HTMLDivElement>) => {
    const d = dragRef.current;
    if (!d.active) return;
    if (!d.moved && Math.hypot(e.clientX - d.startX, e.clientY - d.startY) < DRAG_THRESHOLD_PX) {
      return;
    }
    d.moved = true;
    const rect = e.currentTarget.getBoundingClientRect();
    posRef.current = {
      x: Math.min(1, Math.max(0, (e.clientX - rect.left) / rect.width)),
      y: Math.min(1, Math.max(0, (e.clientY - rect.top) / rect.height)),
    };
    // rAF-coalesce: pointermove fires at input rate (~120 Hz), but the
    // marker can only move once per animation frame — re-rendering the
    // whole card per event is wasted work. One setState per frame.
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        setDragPos(posRef.current);
      });
    }
  };

  const onPointerUp = () => {
    const d = dragRef.current;
    if (!d.active) return;
    d.active = false;
    if (rafRef.current !== null) {
      cancelAnimationFrame(rafRef.current);
      rafRef.current = null;
    }
    const final = posRef.current;
    posRef.current = null;
    if (d.moved && final) {
      suppressClickRef.current = true;
      setTimeout(() => (suppressClickRef.current = false), 0);
      setDragPos(null);
      onRerender(platform, { fit: "crop", anchor: [final.x, final.y] });
    }
  };

  const openPlayer = () => {
    if (suppressClickRef.current) return;
    setPlaying(true);
  };

  // Keyboard equivalent of the drag (a11y: the pointer path is unreachable
  // for keyboard users). Enter/Space play; arrows nudge the anchor 5% and
  // re-render — one PUT per press, same cost as one drag.
  const onStillKeyDown = (e: React.KeyboardEvent<HTMLImageElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      openPlayer();
      return;
    }
    if (!croppable) return;
    const step = 0.05;
    const cur = version.anchor_override ?? [0.5, 0.5];
    const dx = e.key === "ArrowLeft" ? -step : e.key === "ArrowRight" ? step : 0;
    const dy = e.key === "ArrowUp" ? -step : e.key === "ArrowDown" ? step : 0;
    if (dx === 0 && dy === 0) return;
    e.preventDefault();
    onRerender(platform, {
      fit: "crop",
      anchor: [
        Math.min(1, Math.max(0, cur[0] + dx)),
        Math.min(1, Math.max(0, cur[1] + dy)),
      ],
    });
  };

  // Re-render in flight (FR-4.3): show progress instead of stale artifacts.
  if (version.status === "queued" || version.status === "rendering") {
    const pct = Math.round(version.progress);
    return (
      <article className="card" data-platform={platform}>
        <div className="plat-wash" aria-hidden="true" />
        <header className="card-head">
          <h3>{label}</h3>
          <span className={`badge ${version.status}`}>{version.status}</span>
        </header>
        <div className="card-render">
          <div className="skeleton still-skeleton" aria-hidden="true" />
          <div className="progress-row">
            <div
              className="bar"
              role="progressbar"
              aria-valuemin={0}
              aria-valuemax={100}
              aria-valuenow={pct}
              aria-label={`${label} render progress`}
            >
              <div className="bar-fill" style={{ width: `${version.progress}%` }} />
            </div>
            <span className="pct">{pct}%</span>
          </div>
          <p className="muted">Rendering…</p>
        </div>
      </article>
    );
  }

  return (
    <article className="card" data-platform={platform}>
      <div className="plat-wash" aria-hidden="true" />
      <header className="card-head">
        <h3>
          <span className="plat-dot" aria-hidden="true" />
          {label}
        </h3>
        <span className={`badge ${version.status}`}>{version.status}</span>
      </header>

      {still ? (
        <div className="still-wrap">
          <div className={`still-frame${croppable ? " draggable" : ""}`}>
            {!imgLoaded && <div className="skeleton still-skeleton" aria-hidden="true" />}
            <img
              src={still}
              alt={`${label} preview`}
              className="still"
              draggable={false}
              tabIndex={0}
              aria-label={
                croppable
                  ? `${label} preview. Enter to play. Arrow keys move the crop anchor.`
                  : `${label} preview. Enter to play.`
              }
              onLoad={() => setImgLoaded(true)}
              onClick={openPlayer}
              onKeyDown={onStillKeyDown}
              onPointerDown={onPointerDown}
              onPointerMove={onPointerMove}
              onPointerUp={onPointerUp}
            />
            {/* One light sweep across the preview once it has loaded. */}
            {imgLoaded && <Shine delay={0.3} />}
            {croppable && version.anchor_override && (
              <span
                className="anchor-marker static"
                style={{
                  left: `${version.anchor_override[0] * 100}%`,
                  top: `${version.anchor_override[1] * 100}%`,
                }}
                aria-hidden="true"
              />
            )}
            {croppable && dragPos && (
              <span
                className="anchor-marker"
                style={{ left: `${dragPos.x * 100}%`, top: `${dragPos.y * 100}%` }}
                aria-hidden="true"
              />
            )}
          </div>
          {overlay && spec && <SafeZoneOverlay margins={spec.margins} label={label} />}
          <div className="still-actions">
            <button className="btn tiny" onClick={() => setPlaying(true)}>
              ▶ Play
            </button>
            {spec && (
              <button
                className="btn tiny"
                aria-pressed={overlay}
                onClick={() => setOverlay((o) => !o)}
              >
                {overlay ? "Hide" : "Show"} safe zone
              </button>
            )}
          </div>
          {version.stills.length > 1 && (
            <div className="thumb-row">
              {version.stills.slice(1).map((s, i) => (
                <img key={i} src={s} alt={`${label} still ${i + 2}`} onClick={openPlayer} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="muted no-still">No preview available</div>
      )}

      <div className="fit-row">
        <div className="fit-toggle" role="group" aria-label={`${label} frame fit`}>
          <button
            className={version.fit === "crop" ? "active" : ""}
            aria-pressed={version.fit === "crop"}
            onClick={() => onRerender(platform, { fit: "crop", anchor: version.anchor_override })}
          >
            Crop
          </button>
          <button
            className={version.fit === "blur" ? "active" : ""}
            aria-pressed={version.fit === "blur"}
            onClick={() => onRerender(platform, { fit: "blur", anchor: version.anchor_override })}
          >
            Blur-pad
          </button>
        </div>
        <p className="muted fit-hint">
          {version.fit === "crop"
            ? "Drag the preview to set the crop anchor"
            : "Blur-pad letterbox — no crop anchor"}
        </p>
      </div>

      <Checklist checks={version.checks} />

      <footer className="card-foot">
        {version.download_url && (
          <a className="btn primary" href={version.download_url} download>
            ↓ Download MP4
          </a>
        )}
        {spec && (
          <button className="btn ghost" onClick={copySpec}>
            Copy spec
          </button>
        )}
      </footer>

      <AnimatePresence>
        {playing && version.download_url && (
          <motion.div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label={`${label} rendered video`}
            onClick={() => setPlaying(false)}
            initial={{ opacity: 0 }}
            animate={{ opacity: 1 }}
            exit={{ opacity: 0 }}
          >
            <motion.div
              className="modal-body"
              onClick={(e) => e.stopPropagation()}
              initial={{ scale: 0.92, y: 14 }}
              animate={{ scale: 1, y: 0 }}
              exit={{ scale: 0.95, y: 8 }}
              transition={{ type: "spring", stiffness: 300, damping: 28 }}
            >
              <video src={version.download_url} controls autoPlay className="modal-video" />
              <button className="btn ghost" onClick={() => setPlaying(false)}>
                Close
              </button>
            </motion.div>
          </motion.div>
        )}
      </AnimatePresence>
    </article>
  );
}