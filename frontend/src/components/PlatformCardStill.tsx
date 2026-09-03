import { useEffect, useRef, useState } from "react";
import { Crosshair } from "lucide-react";
import type { PlatformId, VersionOptions, VersionState } from "../types";

interface Props {
  version: VersionState;
  platform: PlatformId;
  label: string;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
  onPlay: () => void;
}

const DRAG_THRESHOLD_PX = 6;
const NUDGE_STEP = 0.05;

function clamp01(n: number): number {
  return Math.min(1, Math.max(0, n));
}

/** The 9:16 preview still. Crop-anchor changes are an explicit mode, not a
 *  hidden gesture: "Move anchor" arms the still, drag or arrow keys place a
 *  pending anchor, and Apply re-renders once. Cancel discards with no call.
 *  Clicking the still always plays. */
export function PlatformCardStill({ version, platform, label, onRerender, onPlay }: Props) {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [arming, setArming] = useState(false);
  const [pending, setPending] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef({ active: false, moved: false, startX: 0, startY: 0 });
  // Latest pointer position, ref-backed: pointerup may arrive before the
  // last rAF-flushed setState, so the final anchor must not come from the
  // (possibly stale) pending state closure.
  const posRef = useRef<{ x: number; y: number } | null>(null);
  const rafRef = useRef<number | null>(null);
  const suppressClickRef = useRef(false);
  const stillRef = useRef<HTMLImageElement>(null);
  const moveBtnRef = useRef<HTMLButtonElement>(null);

  // Cancel a pending rAF on unmount so we never setState after teardown.
  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  const still = version.stills[0] ?? null;
  const croppable = version.status === "done" && version.fit === "crop";
  const current: readonly [number, number] = version.anchor_override ?? [0.5, 0.5];
  const shown = pending ?? { x: current[0], y: current[1] };

  // Leaving crop mode disarms with nothing applied.
  useEffect(() => {
    if (!croppable) {
      setArming(false);
      setPending(null);
    }
  }, [croppable]);

  const startArming = () => {
    setArming(true);
    setPending(null);
    // Land keyboard users on the surface they are about to adjust.
    requestAnimationFrame(() => stillRef.current?.focus());
  };
  const cancelArming = () => {
    setArming(false);
    setPending(null);
    posRef.current = null;
    moveBtnRef.current?.focus();
  };
  const applyAnchor = (anchor: { x: number; y: number }) => {
    setArming(false);
    setPending(null);
    posRef.current = null;
    onRerender(platform, {
      fit: "crop",
      anchor: [anchor.x, anchor.y],
      caption_template: version.caption_template,
    });
    moveBtnRef.current?.focus();
  };

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!arming) return;
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
      x: clamp01((e.clientX - rect.left) / rect.width),
      y: clamp01((e.clientY - rect.top) / rect.height),
    };
    // rAF-coalesce: one setState per frame, not per pointer event.
    if (rafRef.current === null) {
      rafRef.current = requestAnimationFrame(() => {
        rafRef.current = null;
        setPending(posRef.current);
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
      // Drag places the pending anchor; Apply commits it. No render yet.
      setPending(final);
    }
  };

  const handleClick = () => {
    if (suppressClickRef.current) return;
    onPlay();
  };

  // Keyboard: idle still plays; armed still adjusts a pending anchor.
  const onStillKeyDown = (e: React.KeyboardEvent<HTMLImageElement>) => {
    if (!arming) {
      if (e.key === "Enter" || e.key === " ") {
        e.preventDefault();
        onPlay();
      }
      return;
    }
    const base = pending ?? { x: current[0], y: current[1] };
    const dx = e.key === "ArrowLeft" ? -NUDGE_STEP : e.key === "ArrowRight" ? NUDGE_STEP : 0;
    const dy = e.key === "ArrowUp" ? -NUDGE_STEP : e.key === "ArrowDown" ? NUDGE_STEP : 0;
    if (dx !== 0 || dy !== 0) {
      e.preventDefault();
      setPending({ x: clamp01(base.x + dx), y: clamp01(base.y + dy) });
      return;
    }
    if (e.key === "Enter") {
      e.preventDefault();
      if (pending) applyAnchor(pending);
      return;
    }
    if (e.key === "Escape") {
      e.preventDefault();
      cancelArming();
    }
  };

  if (!still) return <div className="muted no-still">No preview available</div>;

  const anchorLabel = version.anchor_override
    ? `Custom ${Math.round(shown.x * 100)}%, ${Math.round(shown.y * 100)}%`
    : "Center (default)";
  const stillAria = arming
    ? `${label} preview, placing anchor at ${Math.round(shown.x * 100)}%, ${Math.round(shown.y * 100)}%. Arrow keys move, Enter applies, Escape cancels.`
    : croppable
      ? `${label} preview. Enter to play.`
      : `${label} preview. Enter to play.`;

  return (
    <div className="still-wrap">
      <div className={`still-frame${arming ? " armed" : ""}`}>
        {!imgLoaded && <div className="skeleton still-skeleton" aria-hidden="true" />}
        <img
          src={still}
          alt={`${label} preview`}
          className="still"
          draggable={false}
          tabIndex={0}
          ref={stillRef}
          aria-label={stillAria}
          onLoad={() => setImgLoaded(true)}
          onClick={handleClick}
          onKeyDown={onStillKeyDown}
          onPointerDown={onPointerDown}
          onPointerMove={onPointerMove}
          onPointerUp={onPointerUp}
        />
        {croppable && (
          <span
            className={`anchor-marker${version.anchor_override || pending ? " static" : ""}`}
            style={{ left: `${shown.x * 100}%`, top: `${shown.y * 100}%` }}
            aria-hidden="true"
          />
        )}
      </div>
      {croppable && (
        <div className="anchor-bar">
          {arming ? (
            <>
              <span className="anchor-hint" id={`anchor-hint-${platform}`}>
                Drag the preview or use arrow keys, then Apply.
              </span>
              <span className="anchor-actions">
                <button className="btn ghost anchor-btn" onClick={cancelArming}>
                  Cancel
                </button>
                <button
                  className="btn primary anchor-btn"
                  disabled={!pending}
                  onClick={() => pending && applyAnchor(pending)}
                >
                  Apply anchor
                </button>
              </span>
            </>
          ) : (
            <>
              <span className="anchor-label">
                Anchor: {anchorLabel}
              </span>
              <button ref={moveBtnRef} className="anchor-move" onClick={startArming}>
                <Crosshair size={12} aria-hidden="true" /> Move anchor
              </button>
            </>
          )}
        </div>
      )}
    </div>
  );
}
