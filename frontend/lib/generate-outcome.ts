import type { ClosestSource } from "./api";

/** What the pages need from a /generate response to decide what to show. */
export interface GenerateOutcomeInput {
  status?: string;
  message?: string;
  post?: string;
  closest_sources?: ClosestSource[];
  no_specifics_enabled?: boolean;
}

/**
 * What a /generate response means for the page:
 * - "post": there is a post to show.
 * - "low_coverage": the knowledge base doesn't cover the topic; show the notice.
 * - "no_post": nothing was written (the draft was cut off, the model declined,
 *   or the response has no post); show `message` instead of a post.
 */
export type GenerateOutcome =
  | { kind: "post" }
  | { kind: "low_coverage"; closestSources: ClosestSource[]; noSpecificsEnabled: boolean }
  | { kind: "no_post"; status: string; message: string };

/** Shown when the backend sent no message of its own for that status. */
export const NO_POST_MESSAGES: Record<string, string> = {
  draft_empty:
    "The model returned no post. Generate again, or try a different topic or wording.",
  draft_truncated:
    "The draft was cut off before it was finished, so there is no post to show. Generate again, or choose a shorter length.",
  draft_refused:
    "The model declined to write this post, so there is no post to show. Try a different topic or wording.",
};
export const NO_POST_FALLBACK = "No post was generated. Please try again.";

/**
 * Never returns "post" for an empty post: a status this page does not know, or
 * an "ok" with nothing in it, is a "no_post" with a message, not a blank editor.
 */
export function generateOutcome(data: GenerateOutcomeInput): GenerateOutcome {
  const status = data.status ?? "ok";
  if (status === "low_coverage") {
    return {
      kind: "low_coverage",
      closestSources: data.closest_sources ?? [],
      noSpecificsEnabled: data.no_specifics_enabled ?? false,
    };
  }
  if ((status === "ok" || status === "needs_review") && (data.post ?? "").trim() !== "") return { kind: "post" };
  const message = (data.message ?? "").trim() || NO_POST_MESSAGES[status] || NO_POST_FALLBACK;
  return { kind: "no_post", status, message };
}

/** Explanation used when onboarding cannot proceed to its draft screen. */
export function generateErrorMessage(outcome: Exclude<GenerateOutcome, { kind: "post" }>): string {
  return outcome.kind === "no_post"
    ? outcome.message
    : "Your memory doesn't cover this topic yet. Add a source about it, then generate again.";
}
