import { useCallback, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
import { RotateCcw } from "lucide-react";
import { ApiError, pollJob, updateVersionOptions, uploadJob } from "./api";
import { JobProgress } from "./components/JobProgress";
import { ResultGrid } from "./components/ResultGrid";
import { UploadDropzone } from "./components/UploadDropzone";
import type { JobState, PlatformId, SeoPack, VersionOptions } from "./types";
import { SafeZoneDiagram } from "./ui/SafeZoneDiagram";

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
        // Stay where the user was (progress rows or results grid) so the
        // per-platform errors stay in context; the banner names recovery.
        setScreen(fromScreen);
        setError(terminal.error ?? "Job failed — see platform errors below.");
      } else {
        setScreen("results");
      }
    } catch (err) {
      if (abort.signal.aborted) return; // superseded by a newer poll
      const message =
        err instanceof ApiError ? err.message : "We couldn't reach the render server. Check your connection and try again.";
      // Keep the current screen: a dropped poll must not discard the
      // progress the user was watching. Retry re-polls the same job.
      setError(message);
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

  /** Re-poll the same job after a dropped connection — never loses context. */
  const retryPoll = useCallback(() => {
    if (!job) return;
    setError(null);
    void startPolling(job.job_id, screen);
  }, [job, screen, startPolling]);

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
      <header className="header">
        <div className="header-inner">
          <div className="brand">
            <img src="/logo.jpg" alt="Edit Once Logo" className="brand-mark" />
            <div>
              <h1>Edit Once</h1>
              <p className="tagline">One source edit · four platform-correct videos</p>
            </div>
          </div>
          {screen !== "upload" && (
            <button className="btn ghost" onClick={handleReset}>
              <RotateCcw size={14} aria-hidden="true" /> New project
            </button>
          )}
        </div>
      </header>

      <div className="app">
        {error && (
          <div className="error-banner" role="alert">
            <span>
              <strong>Error:</strong> {error}
            </span>
            {job && screen !== "upload" && (
              <button className="btn ghost tiny" onClick={retryPoll}>
                Retry
              </button>
            )}
          </div>
        )}

        <main>
          {screen === "upload" && (
            <section className="hero-split">
              <div className="hero-copy">
                <p className="eyebrow">Platform-correct video repacking</p>
                <h1 className="hero-title">
                  One edit. <span className="accent-text">Four platform-perfect exports.</span>
                </h1>
                <p className="lede">
                  Upload a finished short. We re-render captions into each platform's safe
                  zone, convert any ratio to 9:16, and verify every version against its spec
                  before it's marked ready.
                </p>
                <UploadDropzone onSubmit={handleUpload} />
                <p className="fineprint">
                  <strong>No re-editing.</strong> Captions are re-rendered from your SRT, never
                  OCR'd — transcribed locally on-device if you skip the file.
                </p>
              </div>
              <div className="hero-visual">
                <SafeZoneDiagram />
              </div>
            </section>
          )}
          {screen === "running" && job && <JobProgress job={job} onCancel={handleReset} />}
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
