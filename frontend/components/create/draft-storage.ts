// The create screen's draft, kept in sessionStorage so a reload or a trip to
// another page can pick it up again. Every read and write tolerates storage
// being unavailable or corrupt.

import type { Grounding } from "@/components/GroundingNotice";
import {
  SS_CURRENT_POST_ID, SS_FEEDBACK, SS_FORMAT, SS_IDEAS, SS_ITERATIONS, SS_LENGTH, SS_POST, SS_RAW_POST, SS_SCORE,
  SS_SCORED, SS_SHOW_ANALYSIS, SS_TONE, SS_TOPIC, SS_VISUALS,
  type Format, type GenerateResult, type Suggestion, type Tone, type Visual,
} from "./config";

const SS_GROUNDING = "contentOS_last_grounding";
const SS_TRACE_ID = "contentOS_last_trace_id";

/** The keys a fresh generation clears. */
export const GENERATION_KEYS = [SS_POST, SS_SCORE, SS_FEEDBACK, SS_ITERATIONS, SS_VISUALS, SS_IDEAS, SS_CURRENT_POST_ID, SS_TOPIC, SS_FORMAT, SS_TONE, SS_LENGTH, SS_SCORED, SS_RAW_POST];
/** The keys "Start fresh" clears: the generation's, plus the analysis panel preference. */
export const START_FRESH_KEYS = [SS_POST, SS_SCORE, SS_FEEDBACK, SS_ITERATIONS, SS_VISUALS, SS_IDEAS, SS_CURRENT_POST_ID, SS_TOPIC, SS_FORMAT, SS_TONE, SS_LENGTH, SS_SCORED, SS_SHOW_ANALYSIS, SS_RAW_POST];

export function removeKeys(keys: string[]): void {
  keys.forEach((key) => sessionStorage.removeItem(key));
}

/** The ideas list saved with the draft; [] when there is none or it is unreadable. */
export function readSavedIdeas(): Suggestion[] {
  const saved = sessionStorage.getItem(SS_IDEAS);
  if (!saved) return [];
  try {
    const parsed = JSON.parse(saved);
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

/** The saved analysis-panel preference; null when none was saved. */
export function readShowAnalysis(): boolean | null {
  const saved = sessionStorage.getItem(SS_SHOW_ANALYSIS);
  return saved === null ? null : saved === "true";
}

/** The current post's id, from state or from storage when state hasn't caught up. */
export function storedPostId(current: number | null): number | null {
  return current ?? (() => {
    try { return Number(sessionStorage.getItem(SS_CURRENT_POST_ID)) || null; } catch { return null; }
  })();
}

export interface DraftSnapshot {
  result: GenerateResult;
  traceId: string | null;
  post: string;
  rawPost: string;
  visuals: Visual[];
  topic: string;
  format: Format;
  tone: Tone;
}

export function saveDraft(d: DraftSnapshot): void {
  try {
    sessionStorage.setItem(SS_GROUNDING, JSON.stringify(d.result.grounding ?? null));
    sessionStorage.setItem(SS_TRACE_ID, d.traceId ?? "");
    sessionStorage.setItem(SS_POST, d.post);
    sessionStorage.setItem(SS_RAW_POST, d.rawPost);
    sessionStorage.setItem(SS_SCORE, String(d.result.score));
    sessionStorage.setItem(SS_FEEDBACK, JSON.stringify(d.result.score_feedback));
    sessionStorage.setItem(SS_ITERATIONS, String(d.result.iterations));
    sessionStorage.setItem(SS_VISUALS, JSON.stringify(d.visuals));
    sessionStorage.setItem(SS_TOPIC, d.topic);
    sessionStorage.setItem(SS_FORMAT, d.format);
    sessionStorage.setItem(SS_TONE, d.tone);
    sessionStorage.setItem(SS_SCORED, String(d.result.scored));
  } catch {
    // ignore
  }
}

export interface SavedDraft {
  result: GenerateResult;
  post: string;
  /** The post with its [DIAGRAM:/IMAGE:] placeholders, for /generate-visuals. */
  rawPost: string;
  traceId: string | null;
  visuals: Visual[] | null;
  topic: string | null;
  format: Format | null;
  tone: Tone | null;
  postId: number | null;
}

/** The saved draft, for "Continue editing". null when there is no post text. */
export function readDraft(): SavedDraft | null {
  const post = sessionStorage.getItem(SS_POST);
  // Only the post text is required. Secondary keys (score, feedback,
  // iterations) get graceful defaults when missing, e.g. when SS_POST was
  // written by a selection refine before a full persistence flush ran.
  if (!post) return null;
  const feedback = sessionStorage.getItem(SS_FEEDBACK);
  const visuals = sessionStorage.getItem(SS_VISUALS);
  const postId = sessionStorage.getItem(SS_CURRENT_POST_ID);
  let parsedVisuals: Visual[] | null = null;
  if (visuals) {
    try { parsedVisuals = JSON.parse(visuals); } catch { /* ignore */ }
  }
  return {
    result: {
      grounding: JSON.parse(sessionStorage.getItem(SS_GROUNDING) ?? "null") as Grounding | null,
      post,
      score: Number(sessionStorage.getItem(SS_SCORE)) || 0,
      score_feedback: (() => {
        try { return feedback ? JSON.parse(feedback) : []; } catch { return []; }
      })(),
      iterations: Number(sessionStorage.getItem(SS_ITERATIONS)) || 1,
      // null = old session before lazy scoring: default to unscored so the
      // user can still run analysis; true = previously scored, preserve that.
      scored: sessionStorage.getItem(SS_SCORED) === "true",
    },
    post,
    rawPost: sessionStorage.getItem(SS_RAW_POST) ?? post,
    traceId: sessionStorage.getItem(SS_TRACE_ID) || null,
    visuals: parsedVisuals,
    topic: sessionStorage.getItem(SS_TOPIC) || null,
    format: (sessionStorage.getItem(SS_FORMAT) as Format | null) || null,
    tone: (sessionStorage.getItem(SS_TONE) as Tone | null) || null,
    postId: postId ? Number(postId) : null,
  };
}
