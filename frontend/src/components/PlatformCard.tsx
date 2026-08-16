import { useEffect, useRef, useState } from "react";
import { createPortal } from "react-dom";
import { AnimatePresence, motion } from "motion/react";
import { Download, X } from "lucide-react";
import type { PlatformId, VersionOptions, VersionState, CaptionTemplate } from "../types";
import { STATUS_LABEL } from "../types";

interface Props {
  label: string;
  platform: PlatformId;
  version: VersionState;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
}

const DRAG_THRESHOLD_PX = 6;

export function PlatformCard({ label, platform, version, onRerender }: Props) {
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
  // Modal a11y refs: focus the dialog on open, restore to the still on close.
  const triggerRef = useRef<HTMLImageElement>(null);
  const modalRef = useRef<HTMLDivElement>(null);
  const closeRef = useRef<HTMLButtonElement>(null);

  // Cancel a pending rAF on unmount so we never setState after teardown.
  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  // Modal a11y: Escape closes, Tab is trapped inside the dialog, and focus
  // moves into the dialog on open and back to the still on close.
  useEffect(() => {
    if (!playing) return;
    const raf = requestAnimationFrame(() => closeRef.current?.focus());
    const onKey = (e: KeyboardEvent) => {
      if (e.key === "Escape") {
        setPlaying(false);
        return;
      }
      if (e.key === "Tab" && modalRef.current) {
        const focusables = modalRef.current.querySelectorAll<HTMLElement>(
          'button, [href], video, [tabindex]:not([tabindex="-1"])',
        );
        if (focusables.length === 0) return;
        const first = focusables[0];
        const last = focusables[focusables.length - 1];
        if (e.shiftKey && document.activeElement === first) {
          e.preventDefault();
          last.focus();
        } else if (!e.shiftKey && document.activeElement === last) {
          e.preventDefault();
          first.focus();
        }
      }
    };
    window.addEventListener("keydown", onKey);
    return () => {
      cancelAnimationFrame(raf);
      window.removeEventListener("keydown", onKey);
      triggerRef.current?.focus();
    };
  }, [playing]);

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

  const still = version.stills[0] ?? null;
  const croppable = version.status === "done" && version.fit === "crop";

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
      onRerender(platform, {
        fit: "crop",
        anchor: [final.x, final.y],
        caption_template: version.caption_template,
      });
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
      caption_template: version.caption_template,
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
          <span className={`badge ${version.status}`}>{STATUS_LABEL[version.status]}</span>
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
          <p className="muted">Processing…</p>
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
        <span className={`badge ${version.status}`}>{STATUS_LABEL[version.status]}</span>
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
              ref={triggerRef}
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
        </div>
      ) : (
        <div className="muted no-still">No preview available</div>
      )}

      {version.status === "done" && (
        <div className="card-settings">
          <label htmlFor={`style-select-${platform}`}>Caption Style:</label>
          <select
            id={`style-select-${platform}`}
            className="style-select"
            value={version.caption_template || "default"}
            onChange={(e) =>
              onRerender(platform, {
                fit: version.fit || "crop",
                anchor: version.anchor_override,
                caption_template: e.target.value as CaptionTemplate,
              })
            }
          >
            <option value="default">Default</option>
            <option value="karaoke">Karaoke (Word-by-word)</option>
            <option value="pop">Pop Red</option>
            <option value="bold">Bold Outline</option>
          </select>
        </div>
      )}

      <footer className="card-foot">
        {version.status === "done" && (
          <div className="fit-toggle" role="group" aria-label="Fit Mode">
            <button
              className={`fit-btn ${version.fit === "crop" ? "active" : ""}`}
              onClick={() =>
                onRerender(platform, {
                  fit: "crop",
                  anchor: version.anchor_override,
                  caption_template: version.caption_template,
                })
              }
              aria-pressed={version.fit === "crop"}
            >
              Crop
            </button>
            <button
              className={`fit-btn ${version.fit === "blur" ? "active" : ""}`}
              onClick={() =>
                onRerender(platform, {
                  fit: "blur",
                  anchor: version.anchor_override,
                  caption_template: version.caption_template,
                })
              }
              aria-pressed={version.fit === "blur"}
            >
              Blur Pad
            </button>
          </div>
        )}
        {version.download_url && (
          <a className="btn primary" href={version.download_url} download>
            <Download size={14} aria-hidden="true" /> Download MP4
          </a>
        )}
      </footer>

      {createPortal(
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
                ref={modalRef}
                onClick={(e) => e.stopPropagation()}
                initial={{ scale: 0.92, y: 14 }}
                animate={{ scale: 1, y: 0 }}
                exit={{ scale: 0.95, y: 8 }}
                transition={{ type: "spring", stiffness: 260, damping: 30 }}
              >
                <video src={version.download_url} controls autoPlay className="modal-video" />
                <button ref={closeRef} className="btn ghost" onClick={() => setPlaying(false)}>
                  <X size={14} aria-hidden="true" /> Close
                </button>
              </motion.div>
            </motion.div>
          )}
        </AnimatePresence>,
        document.body,
      )}
    </article>
  );
}
