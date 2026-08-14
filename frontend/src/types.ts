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

export interface VersionState {
  status: VersionStatus;
  progress: number;
  error: string | null;
  checks: CheckResult[];
  stills: string[];
  download_url: string | null;
  spec: SpecInfo | null;
}

export interface InputInfo {
  filename: string;
  duration_s: number;
  resolution: [number, number];
}

export type JobStatus = "queued" | "analyzing" | "rendering" | "done" | "failed";

export interface JobState {
  job_id: string;
  status: JobStatus;
  created_at: string;
  input: InputInfo | null;
  versions: Record<string, VersionState>;
  error: string | null;
}

export const PLATFORM_ORDER = ["tiktok", "reels", "shorts", "x"] as const;
export type PlatformId = (typeof PLATFORM_ORDER)[number];

export const PLATFORM_LABELS: Record<PlatformId, string> = {
  tiktok: "TikTok",
  reels: "Instagram Reels",
  shorts: "YouTube Shorts",
  x: "X",
};