import { PLATFORM_LABELS, PLATFORM_ORDER, type JobState } from "../types";
import { Reveal } from "../ui/Reveal";
import { Stagger } from "../ui/Stagger";

export function JobProgress({ job }: { job: JobState }) {
  const phase = job.status === "analyzing" ? "Analyzing scene crop anchors…" : "Rendering…";
  const analyzing = job.status === "analyzing";

  return (
    <section className="progress" aria-live="polite">
      <Reveal>
        <h2>{phase}</h2>
        <p className="muted">
          {job.input?.filename} · {(job.input?.duration_s ?? 0).toFixed(1)} s · one render at a
          time — this takes a minute or two.
        </p>
      </Reveal>
      <Stagger gap={0.07} startDelay={0.1} className="progress-grid">
        {PLATFORM_ORDER.map((pid) => {
          const v = job.versions[pid];
          if (!v) return null;
          const label = v.status === "done" ? "done" : v.status === "failed" ? "failed" : `${v.progress}%`;
          const active = v.status === "rendering";
          return (
            <div className={`progress-row${active ? " active" : ""}`} key={pid}>
              <span className="progress-name">{PLATFORM_LABELS[pid]}</span>
              {analyzing ? (
                // Skeleton while probing: no real progress to show yet.
                <div className="skeleton bar-skeleton" />
              ) : (
                <div
                  className="bar"
                  role="progressbar"
                  aria-valuemin={0}
                  aria-valuemax={100}
                  aria-valuenow={v.progress}
                  aria-label={`${PLATFORM_LABELS[pid]} render progress`}
                >
                  <div className={`bar-fill ${v.status}`} style={{ width: `${v.progress}%` }} />
                </div>
              )}
              <span className={`badge ${v.status}`}>{label}</span>
            </div>
          );
        })}
      </Stagger>
    </section>
  );
}