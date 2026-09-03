import { useEffect, useRef, useState } from "react";
import type { PlatformId, VersionOptions, VersionState } from "../types";

interface Props {
  version: VersionState;
  platform: PlatformId;
  label: string;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
  onPlay: () => void;
}

const DRAG_THRESHOLD_PX = 6;

/** The 9:16 preview still. Owns the drag-to-set crop anchor (FR-4.3) and its
 *  keyboard equivalent, plus triggering the fullscreen preview. */
export function PlatformCardStill({ version, platform, label, onRerender, onPlay }: Props) {
  const [imgLoaded, setImgLoaded] = useState(false);
  const [dragPos, setDragPos] = useState<{ x: number; y: number } | null>(null);
  const dragRef = useRef({ active: false, moved: false, startX: 0, startY: 0 });
  // Latest pointer position, ref-backed: pointerup may arrive before the
  // last rAF-flushed setState, so the final anchor must not come from the
  // (possibly stale) dragPos state closure.
  const posRef = useRef<{ x: number; y: number } | null>(null);
  const rafRef = useRef<number | null>(null);
  const suppressClickRef = useRef(false);
  const triggerRef = useRef<HTMLImageElement>(null);

  // Cancel a pending rAF on unmount so we never setState after teardown.
  useEffect(
    () => () => {
      if (rafRef.current !== null) cancelAnimationFrame(rafRef.current);
    },
    [],
  );

  const still = version.stills[0] ?? null;
  const croppable = version.status === "done" && version.fit === "crop";

  const onPointerDown = (e: React.PointerEvent<HTMLDivElement>) => {
    if (!croppable) return;
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
    // rAF-coalesce: one setState per frame, not per pointer event.
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

  const handleClick = () => {
    if (suppressClickRef.current) return;
    onPlay();
  };

  // Keyboard equivalent of the drag. Enter/Space play; arrows nudge the anchor.
  const onStillKeyDown = (e: React.KeyboardEvent<HTMLImageElement>) => {
    if (e.key === "Enter" || e.key === " ") {
      e.preventDefault();
      onPlay();
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

  if (!still) return <div className="muted no-still">No preview available</div>;

  return (
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
          onClick={handleClick}
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
  );
}
