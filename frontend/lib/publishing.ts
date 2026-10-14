// Types and pure helpers for connected accounts and publish jobs.
// Platform limits come from the backend (GET /publishing/platforms); the checks
// here only preview what the backend will decide when the job is created.

export interface ConnectedAccount {
  id: string;
  platform: string;
  label: string;
  display_name: string;
  status: "connected" | "needs_reconnect" | "disconnected";
}

export interface PlatformRules {
  platform: string;
  label: string;
  max_characters: number;
  media_required: "none" | "image_or_video" | "video";
  max_images: number;
}

export interface MediaRef {
  ref: string;
  kind: "image" | "video";
}

export type JobStatus = "draft" | "scheduled" | "publishing" | "published" | "failed" | "cancelled";

export interface JobResult {
  account_id: string | null;
  platform: string | null;
  status: string;
  url: string;
  message: string;
}

export interface PublishJob {
  id: string;
  post_id: number | null;
  content: string;
  account_ids: string[];
  status: JobStatus;
  scheduled_at: string | null;
  published_at: string | null;
  created_at: string | null;
  results: JobResult[];
  /** What the user should do about a failed or paused job. "" when nothing. */
  message: string;
  error_code: string | null;
}

export type PublishWhen = "now" | "schedule" | "queue";

export interface CreateJobRequest {
  approval_id: string;
  content: string;
  account_ids: string[];
  post_id?: number | null;
  media: MediaRef[];
  when: PublishWhen;
  scheduled_at?: string | null;
  timezone: string;
}

/** The viewer's IANA time zone, e.g. "America/New_York". */
export function browserTimeZone(): string {
  return Intl.DateTimeFormat().resolvedOptions().timeZone || "UTC";
}

/**
 * A <input type="datetime-local"> value ("2026-11-03T09:30"), read as local
 * time in the browser's zone, as an ISO string with that zone's UTC offset.
 * null when the value is not a date.
 */
export function localInputToIso(value: string): string | null {
  if (!value) return null;
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return null;
  const offset = -date.getTimezoneOffset();
  const sign = offset >= 0 ? "+" : "-";
  const pad = (n: number) => String(Math.abs(n)).padStart(2, "0");
  const seconds = value.length === 16 ? ":00" : "";
  return `${value}${seconds}${sign}${pad(Math.trunc(offset / 60))}:${pad(offset % 60)}`;
}

/** How a post fits one platform, for the preview. */
export function fit(rules: PlatformRules, text: string, media: MediaRef[]): { count: number; problems: string[] } {
  const problems: string[] = [];
  const count = text.length;
  if (count > rules.max_characters) {
    problems.push(`${(count - rules.max_characters).toLocaleString("en-US")} characters over the limit`);
  }
  const images = media.filter((m) => m.kind === "image").length;
  const videos = media.filter((m) => m.kind === "video").length;
  if (rules.media_required === "video" && videos === 0) problems.push("Needs a video");
  else if (rules.media_required === "image_or_video" && images + videos === 0) problems.push("Needs an image or a video");
  if (rules.media_required !== "video" && images > rules.max_images) {
    problems.push(`Allows ${rules.max_images} image${rules.max_images === 1 ? "" : "s"}`);
  }
  return { count, problems };
}

const STATUS_LABELS: Record<JobStatus, string> = {
  draft: "Draft",
  scheduled: "Scheduled",
  publishing: "Publishing",
  published: "Published",
  failed: "Not published",
  cancelled: "Cancelled",
};

export function statusLabel(job: Pick<PublishJob, "status" | "error_code">): string {
  if (job.status === "scheduled" && job.error_code === "payment_required") return "Paused";
  return STATUS_LABELS[job.status] ?? job.status;
}

/** "Tue, Nov 3, 9:30 AM", in the viewer's own time zone. */
export function formatWhen(iso: string | null, locale = "en-US", timeZone?: string): string {
  if (!iso) return "";
  return new Date(iso).toLocaleString(locale, {
    weekday: "short", month: "short", day: "numeric", hour: "numeric", minute: "2-digit", timeZone,
  });
}

export interface ContentReview {
  post_id: number | null;
  id: string;
  content: string;
  media: MediaRef[];
  flags: import("@/components/GroundingNotice").ClaimFlag[];
  approved_at: string | null;
}

export function allFlagsAccepted(review: ContentReview, accepted: readonly string[]): boolean {
  const required = new Set(review.flags.map((flag) => flag.id));
  const actual = new Set(accepted);
  return actual.size === required.size && [...required].every((id) => actual.has(id));
}
