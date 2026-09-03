import { useState, type CSSProperties } from "react";
import { motion } from "motion/react";
import { AlertTriangle, Loader2, RefreshCw } from "lucide-react";
import type { PlatformId, VersionOptions, VersionState } from "../types";
import { PLATFORM_COLORS, PLATFORM_LABELS, STATUS_LABEL } from "../types";
import { VerifyList } from "./VerifyList";
import { PreviewModal } from "./PreviewModal";
import { PlatformCardStill } from "./PlatformCardStill";
import { PlatformCardControls } from "./PlatformCardControls";

interface Props {
  platform: PlatformId;
  version: VersionState;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
}

export function PlatformCard({ platform, version, onRerender }: Props) {
  const label = PLATFORM_LABELS[platform];
  const [playing, setPlaying] = useState(false);

  return (
    <motion.article
      layout
      initial={{ opacity: 0, y: 16 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, y: -10 }}
      transition={{ type: "spring", stiffness: 280, damping: 30 }}
      className={`card status-${version.status}`}
      data-platform={platform}
      style={{ "--plat": PLATFORM_COLORS[platform] } as CSSProperties}
      aria-label={label}
    >
      <header className="card-head">
        <h3>{label}</h3>
        <span className={`badge ${version.status}`}>{STATUS_LABEL[version.status]}</span>
      </header>

      {version.status === "failed" ? (
        <div className="muted fail">
          <AlertTriangle size={14} aria-hidden="true" /> {version.error ?? "Render failed."}
          <button
            className="btn ghost retry"
            onClick={() =>
              onRerender(platform, {
                fit: version.fit,
                anchor: version.anchor_override,
                caption_template: version.caption_template,
              })
            }
          >
            <RefreshCw size={14} aria-hidden="true" /> Retry
          </button>
        </div>
      ) : version.status === "queued" || version.status === "rendering" ? (
        <div className="muted pending">
          <Loader2 size={14} className="spin" aria-hidden="true" /> Render queued…
        </div>
      ) : (
        <>
          <PlatformCardStill
            version={version}
            platform={platform}
            label={label}
            onRerender={onRerender}
            onPlay={() => setPlaying(true)}
          />
          <VerifyList checks={version.checks} label={label} />
          <PlatformCardControls version={version} platform={platform} onRerender={onRerender} />
        </>
      )}

      <PreviewModal
        open={playing}
        label={label}
        src={version.download_url}
        onClose={() => setPlaying(false)}
      />
    </motion.article>
  );
}
