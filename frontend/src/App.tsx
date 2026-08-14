import { useCallback, useRef, useState } from "react";
import { ApiError, pollJob, uploadJob } from "./api";
import { JobProgress } from "./components/JobProgress";
import { ResultGrid } from "./components/ResultGrid";
import { UploadDropzone } from "./components/UploadDropzone";
import type { JobState } from "./types";

type Screen = "upload" | "running" | "results";

export default function App() {
  const [screen, setScreen] = useState<Screen>("upload");
  const [job, setJob] = useState<JobState | null>(null);
  const [error, setError] = useState<string | null>(null);
  const abortRef = useRef<AbortController | null>(null);

  const handleUpload = useCallback(async (video: File, srt: File) => {
    setError(null);
    const abort = new AbortController();
    abortRef.current = abort;
    try {
      const { job_id } = await uploadJob(video, srt);
      setScreen("running");
      const terminal = await pollJob(job_id, setJob, abort.signal);
      setJob(terminal);
      setScreen(terminal.status === "done" ? "results" : "upload");
      if (terminal.status === "failed") {
        setError(terminal.error ?? "Job failed — see platform errors below.");
      }
    } catch (err) {
      const message = err instanceof ApiError ? err.message : "Network error — is the server running?";
      setError(message);
      setScreen("upload");
    } finally {
      abortRef.current = null;
    }
  }, []);

  const handleReset = useCallback(() => {
    abortRef.current?.abort();
    setJob(null);
    setError(null);
    setScreen("upload");
  }, []);

  return (
    <div className="app">
      <header className="header">
        <div className="brand">
          <span className="brand-mark">EO</span>
          <div>
            <h1>Edit Once</h1>
            <p className="tagline">Publish Everywhere — platform-correct shorts, verified.</p>
          </div>
        </div>
        {screen !== "upload" && (
          <button className="btn ghost" onClick={handleReset}>
            New job
          </button>
        )}
      </header>

      {error && (
        <div className="error-banner" role="alert">
          <strong>Error:</strong> {error}
        </div>
      )}

      <main>
        {screen === "upload" && <UploadDropzone onSubmit={handleUpload} />}
        {screen === "running" && job && <JobProgress job={job} />}
        {screen === "results" && job && <ResultGrid job={job} />}
      </main>

      <footer className="footer">
        Upload one clean edit + SRT → 4 platform-correct MP4s. Captions are re-rendered into
        each platform's safe zone — your source must be caption-free.
      </footer>
    </div>
  );
}