import { useEffect, useState, type CSSProperties } from "react";
import { X } from "lucide-react";
import { PLATFORM_LABELS, PLATFORM_ORDER, STATUS_LABEL } from "../types";
import type { JobState } from "../types";
import { Reveal } from "../ui/Reveal";
import { Stagger } from "../ui/Stagger";

function formatElapsed(totalSeconds: number): string {
  const m = Math.floor(totalSeconds / 60);
  const s = totalSeconds % 60;
  return `${m}:${String(s).padStart(2, "0")}`;
}

export function JobProgress({ job, onCancel }: { job: JobState; onCancel: () => void }) {
  const transcribing = job.status === "transcribing";
  const analyzing = job.status === "analyzing";
  const phase = transcribing
    ? "Transcribing captions from your audio…"
    : analyzing
      ? "Analyzing scene crop anchors…"
      : "Rendering your video…";
  const busy = transcribing || analyzing; // skeletons while pre-render stages run

  const [elapsed, setElapsed] = useState(0);
  useEffect(() => {
    const started = Date.now();
    const tick = () => setElapsed(Math.floor((Date.now() - started) / 1000));
    const id = window.setInterval(tick, 1000);
    return () => window.clearInterval(id);
  }, []);

  const finished = PLATFORM_ORDER.filter((pid) => {
    const s = job.versions[pid]?.status;
    return s === "done" || s === "failed";
  }).length;
  const currentPid = PLATFORM_ORDER.find((pid) => job.versions[pid]?.status === "rendering")
    ?? PLATFORM_ORDER.find((pid) => job.versions[pid]?.status === "queued");
  const queueText =
    !busy && currentPid
      ? `Rendering ${PLATFORM_LABELS[currentPid]} · ${Math.min(finished + 1, 4)} of 4`
      : null;

  return (
    <section className="progress" aria-live="polite">
      <Reveal>
        <div className="progress-head">
          <div>
            <h2>{phase}</h2>
            <p className="muted">
              {job.input?.filename} · {(job.input?.duration_s ?? 0).toFixed(1)} s · one render at a
              time — this takes a minute or two.
            </p>
            {analyzing && (
              <p className="muted">
                Finding the subject in each scene so the 9:16 crop keeps them framed.
              </p>
            )}
            {queueText && (
              <p className="muted">
                {queueText} · <span className="elapsed">elapsed {formatElapsed(elapsed)}</span>
              </p>
            )}
            {!busy && !queueText && (
              <p className="muted">
                <span className="elapsed">Elapsed {formatElapsed(elapsed)}</span>
              </p>
            )}
          </div>
          <button className="btn ghost" onClick={onCancel} aria-label="Cancel and start over">
            <X size={14} aria-hidden="true" /> Cancel
          </button>
        </div>
        <p className="faint-note">Cancel stops watching here — the server finishes the current render.</p>
      </Reveal>
      {transcribing && (
        <div className="progress-row caption-row active" aria-live="polite">
          <span className="progress-name">Captions · auto-transcribed</span>
          <div
            className="bar"
            role="progressbar"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={job.transcribe_progress}
            aria-label="Caption transcription progress"
          >
            <div className="bar-fill transcribing" style={{ "--p": job.transcribe_progress / 100 } as CSSProperties} />
          </div>
          <span className="badge transcribing">{job.transcribe_progress}%</span>
        </div>
      )}
      <Stagger gap={0.07} startDelay={0.1} className="progress-grid">
        {PLATFORM_ORDER.map((pid) => {
          const v = job.versions[pid];
          if (!v) return null;
          const label = v.status === "done" || v.status === "failed" ? STATUS_LABEL[v.status] : `${v.progress}%`;
          const active = v.status === "rendering";
          return (
            <div className={`progress-row${active ? " active" : ""}`} key={pid}>
              <span className="progress-name">{PLATFORM_LABELS[pid]}</span>
              {busy ? (
                // Skeleton while probing/transcribing: no real progress to show yet.
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
                  <div className={`bar-fill ${v.status}`} style={{ "--p": v.progress / 100 } as CSSProperties} />
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