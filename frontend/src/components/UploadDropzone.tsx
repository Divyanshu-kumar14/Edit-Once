import { useCallback, useState } from "react";
import { CountUp } from "../ui/CountUp";
import { Reveal } from "../ui/Reveal";

interface Props {
  onSubmit: (video: File, srt: File) => void;
}

function countCues(srt: string): { count: number; preview: string } {
  const blocks = srt.replace(/\r/g, "").split(/\n{2,}/);
  const cues = blocks.filter((b) => b.includes("-->"));
  const preview = cues.slice(0, 3).map((b) => {
    const lines = b.split("\n");
    return lines[lines.length - 1];
  });
  return { count: cues.length, preview: preview.join(" | ") };
}

export function UploadDropzone({ onSubmit }: Props) {
  const [video, setVideo] = useState<File | null>(null);
  const [srt, setSrt] = useState<File | null>(null);
  const [dragging, setDragging] = useState(false);
  const [parseError, setParseError] = useState<string | null>(null);
  const [parsing, setParsing] = useState(false);
  const [preview, setPreview] = useState<{ count: number; preview: string } | null>(null);

  const selectSrt = (file: File | null) => {
    setSrt(file);
    setParseError(null);
    setPreview(null);
    if (!file) return;
    // Parse off-thread; show a skeleton bar instead of a stale/blank preview.
    setParsing(true);
    file
      .text()
      .then(countCues)
      .then(setPreview)
      .catch(() => setPreview(null))
      .finally(() => setParsing(false));
  };

  const handleDrop = useCallback((files: FileList | null) => {
    if (!files) return;
    setParseError(null);
    for (const file of Array.from(files)) {
      const ext = file.name.split(".").pop()?.toLowerCase();
      if (ext === "mp4" && !video) setVideo(file);
      else if ((ext === "srt" || ext === "vtt") && !srt) setSrt(file);
      else if (ext !== "mp4" && ext !== "srt" && ext !== "vtt") {
        setParseError(`Unsupported file type: ${file.name}`);
      }
    }
  }, [video, srt]);

  const canSubmit = video !== null && srt !== null;

  return (
    <Reveal>
      <section
        className={`dropzone glass ${dragging ? "dragging" : ""}`}
        aria-label="Upload area: drop or pick an MP4 video and an SRT caption file"
        onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
        onDragLeave={() => setDragging(false)}
        onDrop={(e) => { e.preventDefault(); setDragging(false); handleDrop(e.dataTransfer.files); }}
      >
      <h2>Repack one edit for all four platforms</h2>
      <p className="muted">
        Drop your finished MP4 (caption-free) and its SRT. We re-render captions into each
        platform's safe zone and verify every rule.
      </p>

      <div className="file-row">
        <label className="file-pick">
          {/* visually-hidden (not display:none) keeps the input focusable by keyboard */}
          <input
            type="file"
            accept=".mp4"
            className="visually-hidden"
            aria-label="Choose MP4 video file"
            onChange={(e) => { setVideo(e.target.files?.[0] ?? null); }}
          />
          <span className="file-label">🎬 Video</span>
          <span className={video ? "file-name" : "muted"}>
            {video ? `${video.name} (${(video.size / 1e6).toFixed(1)} MB)` : "MP4, ≤ 200 MB, ≤ 600 s"}
          </span>
        </label>

        <label className="file-pick">
          <input
            type="file"
            accept=".srt,.vtt"
            className="visually-hidden"
            aria-label="Choose SRT or VTT caption file"
            onChange={(e) => selectSrt(e.target.files?.[0] ?? null)}
          />
          <span className="file-label">💬 Captions</span>
          <span className={srt ? "file-name" : "muted"}>
            {srt ? `${srt.name}` : "SRT or VTT"}
          </span>
        </label>
      </div>

      {parsing && (
        <div className="parse-preview" aria-live="polite">
          <strong>Reading caption file…</strong>
          <div className="skeleton bar-skeleton" style={{ minWidth: 180 }} />
        </div>
      )}
      {!parsing && preview && (
        <div className="parse-preview" aria-live="polite">
          <strong>
            <CountUp value={preview.count} /> caption cue{preview.count === 1 ? "" : "s"}
          </strong>
          <span className="muted">{preview.preview}</span>
        </div>
      )}
      {parseError && <div className="error-banner" role="alert">{parseError}</div>}

      <button
        className="btn primary"
        disabled={!canSubmit}
        onClick={() => { if (canSubmit) onSubmit(video, srt); }}
      >
        {canSubmit ? "Repack for 4 platforms →" : "Add video + captions to start"}
      </button>
      </section>
    </Reveal>
  );
}