import { useCallback, useState } from "react";
import { Film, Captions } from "lucide-react";

interface Props {
  onSubmit: (video: File, srt: File | null) => void;
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

  const canSubmit = video !== null;

  return (
    <section
      className={`dropzone glass ${dragging ? "dragging" : ""}`}
      aria-label="Upload area: drop or pick an MP4 video (captions optional)"
      onDragOver={(e) => { e.preventDefault(); setDragging(true); }}
      onDragLeave={() => setDragging(false)}
      onDrop={(e) => { e.preventDefault(); setDragging(false); handleDrop(e.dataTransfer.files); }}
    >
      <h2>Upload your video — captions optional</h2>
      <p className="muted">
        Drop an MP4 (and a caption file if you have one). No SRT? We transcribe your captions automatically.
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
          <span className="file-label"><Film size={14} aria-hidden="true" /> Video file</span>
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
          <span className="file-label"><Captions size={14} aria-hidden="true" /> Caption file (optional)</span>
          <span className={srt ? "file-name" : "muted"}>
            {srt ? `${srt.name}` : "Optional — auto-transcribed"}
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
            {preview.count} caption cue{preview.count === 1 ? "" : "s"}
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
        {canSubmit ? "Create 4 versions" : "Add a video to start"}
      </button>
    </section>
  );
}