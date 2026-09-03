import { useState, type CSSProperties } from "react";
import { PLATFORM_LABELS, PLATFORM_ORDER, type PlatformId } from "../types";

/**
 * SafeZoneDiagram — the product's identity fingerprint.
 *
 * Renders the 9:16 output frame with each platform's safe-zone margin
 * rectangle overlaid in its brand color. The overlapping rectangles make the
 * product's actual value legible at a glance: Reels needs the most bottom
 * clearance, Shorts the most right. Hovering/focusing a legend row
 * highlights that platform's zone. Pure SVG, no WebGL, no motion.
 */

interface SafeZone {
  bottom: number; // bottom_margin (fraction)
  right: number; // right_margin (fraction)
  top: number; // top_margin (fraction)
  color: string;
}

// Mirrors backend/platforms.json safe_zone (single source of truth).
const PLAT_SAFE: Record<PlatformId, SafeZone> = {
  tiktok: { bottom: 0.18, right: 0.15, top: 0.05, color: "#25F4EE" },
  reels: { bottom: 0.3, right: 0.15, top: 0.05, color: "#E1306C" },
  shorts: { bottom: 0.2, right: 0.25, top: 0.05, color: "#FF0033" },
  x: { bottom: 0.15, right: 0.1, top: 0.05, color: "#E7E9EA" },
};

// viewBox 9:16
const W = 90;
const H = 160;

function zoneRect(z: SafeZone) {
  const top = z.top * H;
  const bottomInset = z.bottom * H;
  const rightInset = z.right * W;
  return {
    x: 0,
    y: top,
    width: W - rightInset,
    height: H - top - bottomInset,
  };
}

// Caption baseline (MarginV 410 / 1920 ≈ 21% from bottom).
const CAP_Y = H * (1 - 410 / 1920);

export function SafeZoneDiagram() {
  const [active, setActive] = useState<PlatformId | null>(null);

  return (
    <div className="sz-frame">
      <svg
        className="sz-svg"
        viewBox={`0 0 ${W} ${H}`}
        role="img"
        aria-label="Safe-zone diagram: the 9:16 frame with each platform's required clearance rectangle. Reels needs the most bottom clearance; Shorts the most on the right. The dashed line marks where captions are placed."
      >
        <title>Per-platform safe-zone margins</title>

        {/* Output frame */}
        <rect className="sz-outline" x={0} y={0} width={W} height={H} rx={3} />

        {/* Caption baseline */}
        <line className="sz-cap" x1={0} y1={CAP_Y} x2={W} y2={CAP_Y} />

        {/* Per-platform safe zones (drawn back-to-front so the largest is behind) */}
        {[...PLATFORM_ORDER].reverse().map((pid) => {
          const z = PLAT_SAFE[pid];
          const r = zoneRect(z);
          const cls =
            "sz-zone" +
            (active && active !== pid ? " dim" : "") +
            (active === pid ? " active" : "");
          return (
            <rect
              key={pid}
              className={cls}
              x={r.x}
              y={r.y}
              width={r.width}
              height={r.height}
              rx={2}
              style={{ stroke: z.color, ["--zc" as string]: z.color } as CSSProperties}
            />
          );
        })}
      </svg>

      {/* Legend doubles as the spec table for platforms.json */}
      <div className="sz-legend" role="group" aria-label="Platform safe-zone margins">
        {PLATFORM_ORDER.map((pid) => {
          const z = PLAT_SAFE[pid];
          return (
            <button
              key={pid}
              type="button"
              className="sz-legend-row"
              style={{ ["--zc" as string]: z.color } as CSSProperties}
              onMouseEnter={() => setActive(pid)}
              onMouseLeave={() => setActive(null)}
              onFocus={() => setActive(pid)}
              onBlur={() => setActive(null)}
              aria-pressed={active === pid}
            >
              <span className="sz-swatch" aria-hidden="true" />
              <span className="sz-plat">{PLATFORM_LABELS[pid]}</span>
              <span className="sz-spec">
                B <b>{Math.round(z.bottom * 100)}%</b>
              </span>
              <span className="sz-spec">
                R <b>{Math.round(z.right * 100)}%</b>
              </span>
            </button>
          );
        })}
      </div>
    </div>
  );
}
