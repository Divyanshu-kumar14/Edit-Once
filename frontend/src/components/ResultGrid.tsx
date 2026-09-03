import { useState } from "react";
import {
  PLATFORM_ORDER,
  type JobState,
  type PlatformId,
  type SeoPack,
  type VersionOptions,
} from "../types";
import { captionsUrl } from "../api";
import { PlatformCard } from "./PlatformCard";
import { SeoSection } from "./SeoSection";
import { Reveal } from "../ui/Reveal";
import { Stagger } from "../ui/Stagger";

interface Props {
  job: JobState;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
  onSeoPacks: (packs: Partial<Record<PlatformId, SeoPack>>, generatedAt: string) => void;
}

type Tab = "versions" | "seo";

/** Results end on downloads by default; the SEO pack is one tab away,
 *  not a second page below the grid. */
export function ResultGrid({ job, onRerender, onSeoPacks }: Props) {
  const captions = job.captions;
  const [tab, setTab] = useState<Tab>("versions");
  return (
    <section className="results">
      <Reveal>
        <h2>Your versions are ready</h2>
      </Reveal>
      {captions && (
        <Reveal>
          <div className="captions-panel panel" aria-label="Captions used for this job">
            <div>
              <strong>Captions</strong>
              <span className="muted">
                {" "}
                · {captions.cue_count} cue{captions.cue_count === 1 ? "" : "s"} ·{" "}
                {captions.source === "transcribed" ? "auto-transcribed from audio" : "from your upload"}
              </span>
            </div>
            <a className="btn ghost" href={captionsUrl(job.job_id)} download>
              Download SRT
            </a>
          </div>
        </Reveal>
      )}
      <div className="results-tabs" role="tablist" aria-label="Results sections">
        <button
          role="tab"
          aria-selected={tab === "versions"}
          aria-controls="panel-versions"
          id="tab-versions"
          className="results-tab"
          onClick={() => setTab("versions")}
        >
          Versions (4)
        </button>
        <button
          role="tab"
          aria-selected={tab === "seo"}
          aria-controls="panel-seo"
          id="tab-seo"
          className="results-tab"
          onClick={() => setTab("seo")}
        >
          SEO pack
        </button>
      </div>
      {tab === "versions" ? (
        <div id="panel-versions" role="tabpanel" aria-labelledby="tab-versions">
          <Stagger gap={0.09} startDelay={0.15} className="grid">
            {PLATFORM_ORDER.map((pid) => (
              <PlatformCard
                key={pid}
                platform={pid}
                version={job.versions[pid]}
                onRerender={onRerender}
              />
            ))}
          </Stagger>
        </div>
      ) : (
        <div id="panel-seo" role="tabpanel" aria-labelledby="tab-seo">
          <SeoSection job={job} onPacks={onSeoPacks} />
        </div>
      )}
    </section>
  );
}
