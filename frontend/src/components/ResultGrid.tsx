import {
  PLATFORM_LABELS,
  PLATFORM_ORDER,
  type JobState,
  type PlatformId,
  type VersionOptions,
} from "../types";
import { PlatformCard } from "./PlatformCard";

interface Props {
  job: JobState;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
}

export function ResultGrid({ job, onRerender }: Props) {
  return (
    <section className="results">
      <h2>4 platform-correct versions</h2>
      <p className="muted">
        {job.input?.filename} · {(job.input?.duration_s ?? 0).toFixed(1)} s ·{" "}
        {job.input?.resolution[0]}×{job.input?.resolution[1]} source
      </p>
      <div className="grid">
        {PLATFORM_ORDER.map((pid) => (
          <PlatformCard
            key={pid}
            label={PLATFORM_LABELS[pid]}
            platform={pid}
            version={job.versions[pid]}
            onRerender={onRerender}
          />
        ))}
      </div>
    </section>
  );
}