import { Download, SlidersHorizontal } from "lucide-react";
import type { PlatformId, VersionOptions, VersionState, CaptionTemplate } from "../types";

interface Props {
  version: VersionState;
  platform: PlatformId;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
}

/** Default view is proof + action only (still + checks + Download).
 *  Escape-hatch settings (caption style, fit, anchor hint) live collapsed
 *  behind a single native "Adjust" disclosure. */
export function PlatformCardControls({ version, platform, onRerender }: Props) {
  return (
    <>
      <footer className="card-foot">
        {version.download_url && (
          <a className="btn primary download-block" href={version.download_url} download>
            <Download size={14} aria-hidden="true" /> Download MP4
          </a>
        )}
      </footer>

      {version.status === "done" && (
        <details className="adjust">
          <summary className="adjust-summary">
            <SlidersHorizontal size={13} aria-hidden="true" /> Adjust
          </summary>
          <div className="adjust-body">
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
            <p className="adjust-hint">
              Anchor: drag the still or use arrow keys when Crop is active.
            </p>
          </div>
        </details>
      )}
    </>
  );
}
