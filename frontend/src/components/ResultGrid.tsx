import {
  PLATFORM_LABELS,
  PLATFORM_ORDER,
  type JobState,
  type PlatformId,
  type VersionOptions,
} from "../types";
import { PlatformCard } from "./PlatformCard";
import { Reveal } from "../ui/Reveal";
import { Stagger } from "../ui/Stagger";

interface Props {
  job: JobState;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
}

export function ResultGrid({ job, onRerender }: Props) {
  return (
    <section className="results">
      <Reveal>
        <h2>Your versions are ready</h2>
      </Reveal>
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
    </section>
  );
}
