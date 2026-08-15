import { useCallback, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
import { Upload } from "lucide-react";
import { ApiError, pollJob, updateVersionOptions, uploadJob } from "./api";
import { JobProgress } from "./components/JobProgress";
import { ResultGrid } from "./components/ResultGrid";
import { UploadDropzone } from "./components/UploadDropzone";
import type { JobState, PlatformId, SeoPack, VersionOptions } from "./types";
import { PLATFORM_LABELS, PLATFORM_ORDER } from "./types";
import AuroraBackground from "./ui/AuroraBackground";
import { Reveal } from "./ui/Reveal";
import { Stagger } from "./ui/Stagger";

type Screen = "upload" | "running" | "results";

export default function App() {
  const [screen, setScreen] = useState<Screen>("upload");
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  /** Poll until terminal (job done AND all versions done); keep results on screen. */
  const startPolling = useCallback(async (jobId: string, fromScreen: Screen) => {
    const abort = new AbortController();
    abortRef.current = abort;
    setError(null);
    try {
      const terminal = await pollJob(jobId, setJob, abort.signal);
      setJob(terminal);
      if (terminal.status === "failed") {
        setScreen(fromScreen === "running" ? "upload" : "results");
        setError(terminal.error ?? "Job failed — see platform errors below.");
      } else {
        setScreen("results");
      }
    } catch (err) {
      if (abort.signal.aborted) return; // superseded by a newer poll
      const message =
        err instanceof ApiError ? err.message : "We couldn't reach the render server. Check your connection and try again.";
      setError(message);
      setScreen("upload");
    } finally {
      abortRef.current = null;
    }
  }, []);

  const handleUpload = useCallback(
    async (video: File, srt: File | null) => {
      setError(null);
      try {
        const { job_id } = await uploadJob(video, srt);
        setScreen("running");
        await startPolling(job_id, "running");
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : "We couldn't reach the render server. Check your connection and try again.";
        setError(message);
        setScreen("upload");
      }
    },
    [startPolling],
  );

  /** FR-4.3: re-render one platform with new fit/anchor, keep the results grid. */
  const handleRerender = useCallback(
    async (platform: PlatformId, options: VersionOptions) => {
      if (!job) return;
      abortRef.current?.abort();
      setError(null);
      try {
        await updateVersionOptions(job.job_id, platform, options);
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : "Re-render request failed";
        setError(message);
        return;
      }
      await startPolling(job.job_id, "results");
    },
    [job, startPolling],
  );

  const handleReset = useCallback(() => {
    abortRef.current?.abort();
    setJob(null);
    setError(null);
    setScreen("upload");
  }, []);

  /** SEO packs are persisted server-side; merge them into app state so the
   * results screen shows them without a full re-poll. */
  const handleSeoPacks = useCallback(
    (packs: Partial<Record<PlatformId, SeoPack>>, generatedAt: string) => {
      setJob((prev) =>
        prev ? { ...prev, seo_packs: packs, seo_generated_at: generatedAt } : prev,
      );
    },
    [],
  );

  return (
    <MotionConfig reducedMotion="user">
      <AuroraBackground />
      <header className="header">
        <Reveal y={-10}>
          <div className="header-inner">
            <div className="brand">
              <img src="/logo.jpg" alt="Edit Once Logo" className="brand-mark" />
              <div>
                <h1>Edit Once</h1>
                <p className="tagline gradient-text">One edit. Four platform-perfect videos.</p>
              </div>
            </div>
            {screen !== "upload" && (
              <button className="btn ghost" onClick={handleReset}>
                <Upload size={14} aria-hidden="true" /> New project
              </button>
            )}
          </div>
        </Reveal>
      </header>

      <div className="app">

        {error && (
          <div className="error-banner" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        <main>
          {screen === "upload" && (
            <Reveal>
              <section className="hero">
                <h1 className="hero-title">One edit. Four platforms. Zero re-editing.</h1>
                <p className="muted hero-sub">
                  Upload once — get platform-correct videos for TikTok, Reels, Shorts and X,
                  with captions re-rendered into each platform's safe zone.
                </p>
                <div className="pills" aria-label="Output platforms">
                  {PLATFORM_ORDER.map((pid) => (
                    <span key={pid} className="pill" data-platform={pid}>
                      <span className="plat-dot" aria-hidden="true" />
                      {PLATFORM_LABELS[pid]}
                    </span>
                  ))}
                </div>
              </section>
            </Reveal>
          )}
          {screen === "upload" && <UploadDropzone onSubmit={handleUpload} />}
          {screen === "upload" && (
          <Stagger gap={0.12} className="how-it-works" aria-label="How it works">
            <div className="step">
              <span className="step-num" aria-hidden="true">1</span>
              <div>
                <h3>Upload</h3>
                <p className="muted">One clean edit and its caption file.</p>
              </div>
            </div>
            <div className="step">
              <span className="step-num" aria-hidden="true">2</span>
              <div>
                <h3>We render</h3>
                <p className="muted">Four platform-correct versions.</p>
              </div>
            </div>
            <div className="step">
              <span className="step-num" aria-hidden="true">3</span>
              <div>
                <h3>Export</h3>
                <p className="muted">Replay or download each one.</p>
              </div>
            </div>
          </Stagger>
          )}
          {screen === "running" && job && <JobProgress job={job} />}
          {screen === "results" && job && (
            <ResultGrid job={job} onRerender={handleRerender} onSeoPacks={handleSeoPacks} />
          )}
        </main>

        <footer className="footer">
          One source edit, four platform-correct videos — captions re-rendered into each
          platform's safe zone. Built for creators who post everywhere.
        </footer>
      </div>
    </MotionConfig>
  );
}