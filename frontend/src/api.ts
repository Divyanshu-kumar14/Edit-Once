/** Typed fetch wrappers + 2 s polling (FR-8.4). */

import type { JobState } from "./types";

const API_BASE = "";

export class ApiError extends Error {
  readonly status: number;

  constructor(status: number, message: string) {
    super(message);
    this.status = status;
  }
}

async function parseError(resp: Response): Promise<ApiError> {
  let message = `HTTP ${resp.status}`;
  try {
    const body = await resp.json();
    if (typeof body?.detail === "string") message = body.detail;
  } catch {
    /* keep fallback message */
  }
  return new ApiError(resp.status, message);
}

export interface UploadResult {
  job_id: string;
  cues: number;
}

export async function uploadJob(video: File, srt: File): Promise<UploadResult> {
  const form = new FormData();
  form.append("video", video);
  form.append("srt", srt);
  const resp = await fetch(`${API_BASE}/api/jobs`, { method: "POST", body: form });
  if (!resp.ok) throw await parseError(resp);
  return resp.json();
}

export async function fetchJob(jobId: string): Promise<JobState> {
  const resp = await fetch(`${API_BASE}/api/jobs/${jobId}`);
  if (!resp.ok) throw await parseError(resp);
  return resp.json();
}

const TERMINAL: ReadonlySet<string> = new Set(["done", "failed"]);

/**
 * Poll a job every 2 s, invoking onState after each tick. Resolves with the
 * terminal state; rejects with ApiError on 404 etc.
 */
export async function pollJob(
  jobId: string,
  onState: (state: JobState) => void,
  signal?: AbortSignal,
): Promise<JobState> {
  for (;;) {
    if (signal?.aborted) throw new ApiError(0, "aborted");
    const state = await fetchJob(jobId);
    onState(state);
    if (TERMINAL.has(state.status)) return state;
    await new Promise((resolve) => setTimeout(resolve, 2000));
  }
}