import {
  PLATFORM_LABELS,
  PLATFORM_ORDER,
  type JobState,
  type PlatformId,
  type VersionOptions,
} from "../types";
import { PlatformCard } from "./PlatformCard";
import { CountUp } from "../ui/CountUp";
import { Reveal } from "../ui/Reveal";
import { Stagger } from "../ui/Stagger";

interface Props {
  job: JobState;
  onRerender: (platform: PlatformId, options: VersionOptions) => void;
}

export function ResultGrid({ job, onRerender }: Props) {
  const versionsDone = PLATFORM_ORDER.filter(
    (pid) => job.versions[pid].status === "done",
  ).length;
  const checks = PLATFORM_ORDER.flatMap((pid) => job.versions[pid].checks);
  const checksPassed = checks.filter((c) => c.result === "pass").length;

  return (
    <section className="results">
      <Reveal>
        <div className="summary-chip glass" aria-live="polite">
          <span className="summary-count">
            <CountUp value={versionsDone} /> / {PLATFORM_ORDER.length} versions
          </span>
          <span className="summary-sep" aria-hidden="true">·</span>
          <span className="summary-checks">
            <CountUp value={checksPassed} /> / {checks.length} checks passed
          </span>
        </div>
        <h2>Your versions are ready</h2>
        <p className="muted">
          {job.input?.filename} · {(job.input?.duration_s ?? 0).toFixed(1)} s ·{" "}
          {job.input?.resolution[0]}×{job.input?.resolution[1]} source
        </p>
        <p className="muted">Verified against each platform's spec.</p>
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