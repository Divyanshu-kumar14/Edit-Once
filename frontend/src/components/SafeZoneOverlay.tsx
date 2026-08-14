interface Margins {
  bottom: number;
  right: number;
  top: number;
}

interface Props {
  margins: Margins;
  label: string;
}

const W = 1080;
const H = 1920;

/** SVG safe-zone overlay over a 9:16 still (FR-6.2, AC-4). */
export function SafeZoneOverlay({ margins, label }: Props) {
  const top = margins.top * H;
  const bottom = (1 - margins.bottom) * H;
  const left = margins.right * W;
  const right = (1 - margins.right) * W;

  return (
    <svg
      className="overlay"
      viewBox={`0 0 ${W} ${H}`}
      preserveAspectRatio="none"
      role="img"
      aria-label={`${label} safe zone`}
    >
      <defs>
        <pattern id={`hatch-${label}`} width="24" height="24" patternUnits="userSpaceOnUse" patternTransform="rotate(45)">
          <line x1="0" y1="0" x2="0" y2="24" stroke="rgba(255,107,53,0.25)" strokeWidth="6" />
        </pattern>
      </defs>
      {/* outside the safe rect: dimmed hatch */}
      <path
        d={`M0,0 h${W} v${H} h-${W} z M${left},${top} h${right - left} v${bottom - top} h-${right - left} z`}
        fillRule="evenodd"
        fill={`url(#hatch-${label})`}
      />
      <rect x={left} y={top} width={right - left} height={bottom - top}
        fill="rgba(52,211,153,0.06)" stroke="#34d399" strokeWidth="6" strokeDasharray="20 14" />
      <text x={left + 14} y={top + 44} fill="#34d399" fontSize="34" fontWeight="700">
        SAFE ZONE
      </text>
    </svg>
  );
}