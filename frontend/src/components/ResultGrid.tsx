import {
  PLATFORM_LABELS,
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

export function ResultGrid({ job, onRerender, onSeoPacks }: Props) {
  const captions = job.captions;
  return (
    <section className="results">
      <Reveal>
        <h2>Your versions are ready</h2>
      </Reveal>
      {captions && (
        <Reveal>
          <div className="captions-panel glass" aria-label="Captions used for this job">
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
      <Stagger gap={0.09} startDelay={0.15} className="grid">
        {PLATFORM_ORDER.map((pid) => (
          <PlatformCard
            key={pid}
            label={PLATFORM_LABELS[pid]}
            platform={pid}
            version={job.versions[pid]}
            onRerender={onRerender}
          />
        ))}
      </Stagger>
      <SeoSection job={job} onPacks={onSeoPacks} />
    </section>
  );
}
