import { useEffect, useState } from "react";
import type { VersionState } from "../types";
import { Checklist } from "./Checklist";
import { SafeZoneOverlay } from "./SafeZoneOverlay";

interface Props {
  label: string;
  version: VersionState;
}

export function PlatformCard({ label, version }: Props) {
  const [overlay, setOverlay] = useState(false);
  const [playing, setPlaying] = useState(false);
  const [imgLoaded, setImgLoaded] = useState(false);

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
      <article className="card failed">
        <h3>{label}</h3>
        <div className="error-banner">Render failed</div>
        <pre className="stderr">{version.error}</pre>
      </article>
    );
  }

  const still = version.stills[0] ?? null;
  const spec = version.spec;

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

  return (
    <article className="card">
      <header className="card-head">
        <h3>{label}</h3>
        <span className={`badge ${version.status}`}>{version.status}</span>
      </header>

      {still ? (
        <div className="still-wrap">
          <div className="still-frame">
            {!imgLoaded && <div className="skeleton still-skeleton" aria-hidden="true" />}
            <img
              src={still}
              alt={`${label} preview`}
              className="still"
              onLoad={() => setImgLoaded(true)}
              onClick={() => setPlaying(true)}
            />
          </div>
          {overlay && spec && (
            <SafeZoneOverlay margins={spec.margins} label={label} />
          )}
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
                <img key={i} src={s} alt={`${label} still ${i + 2}`} onClick={() => setPlaying(true)} />
              ))}
            </div>
          )}
        </div>
      ) : (
        <div className="muted no-still">No preview available</div>
      )}

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

      {playing && version.download_url && (
        <div
          className="modal"
          role="dialog"
          aria-modal="true"
          aria-label={`${label} rendered video`}
          onClick={() => setPlaying(false)}
        >
          <div className="modal-body" onClick={(e) => e.stopPropagation()}>
            <video src={version.download_url} controls autoPlay className="modal-video" />
            <button className="btn ghost" onClick={() => setPlaying(false)}>
              Close
            </button>
          </div>
        </div>
      )}
    </article>
  );
}