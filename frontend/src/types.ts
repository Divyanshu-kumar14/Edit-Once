/** API types mirroring backend/app/models.py (typed contract, NFR-5). */

export type CheckLevel = "pass" | "warn" | "fail";

export interface CheckResult {
  name: string;
  result: CheckLevel;
  detail: string;
}

export interface SpecInfo {
  width: number;
  height: number;
  duration_s: number;
  margins: { bottom: number; right: number; top: number };
}

export type VersionStatus = "queued" | "rendering" | "done" | "failed";

export type FitMode = "crop" | "blur";

export interface VersionState {
  status: VersionStatus;
  progress: number;
  error: string | null;
  checks: CheckResult[];
  stills: string[];
  download_url: string | null;
  spec: SpecInfo | null;
  fit: FitMode;                       // FR-3.3: crop (smart) vs blur-pad
  anchor_override: [number, number] | null;  // FR-4.3: manual crop anchor
}

export interface VersionOptions {
  fit: FitMode;
  anchor?: [number, number] | null;
}

export interface InputInfo {
  filename: string;
  duration_s: number;
  resolution: [number, number];
}

export type CaptionsSource = "uploaded" | "transcribed";

export interface CaptionsInfo {
  source: CaptionsSource;
  cue_count: number;
}

export interface SeoPack {
  title: string;
  description: string;
  hashtags: string[];
  error: string | null;
}

export type JobStatus = "queued" | "transcribing" | "analyzing" | "rendering" | "done" | "failed";

export interface JobState {
  job_id: string;
  status: JobStatus;
  created_at: string;
  input: InputInfo | null;
  versions: Record<string, VersionState>;
  error: string | null;
  captions: CaptionsInfo | null;
  transcribe_progress: number;
  seo_packs: Partial<Record<PlatformId, SeoPack>>;
  seo_generated_at: string | null;
}

export const PLATFORM_ORDER = ["tiktok", "reels", "shorts", "x"] as const;
export type PlatformId = (typeof PLATFORM_ORDER)[number];

export const PLATFORM_LABELS: Record<PlatformId, string> = {
  tiktok: "TikTok",
  reels: "Instagram Reels",
  shorts: "YouTube Shorts",
  x: "X",
};

/** Display labels for version/job status — product voice, not dev-speak. */
export const STATUS_LABEL: Record<VersionStatus, string> = {
  queued: "Queued",
  rendering: "Processing",
  done: "Ready",
  failed: "Failed",
};

/** Display labels for verification check results. */
export const RESULT_LABEL: Record<CheckLevel, string> = {
  pass: "Passed",
  warn: "Review",
  fail: "Failed",
};