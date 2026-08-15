import { useCallback, useRef, useState } from "react";
import { MotionConfig } from "motion/react";
import { ApiError, pollJob, updateVersionOptions, uploadJob } from "./api";
import { JobProgress } from "./components/JobProgress";
import { ResultGrid } from "./components/ResultGrid";
import { UploadDropzone } from "./components/UploadDropzone";
import type { JobState, PlatformId, VersionOptions } from "./types";
import AuroraBackground from "./ui/AuroraBackground";
import { Reveal } from "./ui/Reveal";

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
        err instanceof ApiError ? err.message : "Network error — is the server running?";
      setError(message);
      setScreen("upload");
    } finally {
      abortRef.current = null;
    }
  }, []);

  const handleUpload = useCallback(
    async (video: File, srt: File) => {
      setError(null);
      try {
        const { job_id } = await uploadJob(video, srt);
        setScreen("running");
        await startPolling(job_id, "running");
      } catch (err) {
        const message =
          err instanceof ApiError ? err.message : "Network error — is the server running?";
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

  return (
    <MotionConfig reducedMotion="user">
      <AuroraBackground />
      <div className="app">
        <Reveal y={-10}>
          <header className="header">
            <div className="brand">
              <span className="brand-mark">EO</span>
              <div>
                <h1>Edit Once</h1>
                <p className="tagline gradient-text">Publish Everywhere — platform-correct shorts, verified.</p>
              </div>
            </div>
            {screen !== "upload" && (
              <button className="btn ghost" onClick={handleReset}>
                New job
              </button>
            )}
          </header>
        </Reveal>

        {error && (
          <div className="error-banner" role="alert">
            <strong>Error:</strong> {error}
          </div>
        )}

        <main>
          {screen === "upload" && <UploadDropzone onSubmit={handleUpload} />}
          {screen === "running" && job && <JobProgress job={job} />}
          {screen === "results" && job && (
            <ResultGrid job={job} onRerender={handleRerender} />
          )}
        </main>

        <footer className="footer">
          Upload one clean edit + SRT → 4 platform-correct MP4s. Captions are re-rendered into
          each platform's safe zone — your source must be caption-free.
        </footer>
      </div>
    </MotionConfig>
  );
}