/**
 * Library page logic. A source is identified by its source_id, never by its
 * title: titles are not unique (one library has 21 sources with no title).
 */

export interface SourceRef {
  source_id: string;
}

/** Shown on the card when a delete fails; the card stays. */
export const DELETE_FAILED_MESSAGE = "Couldn't delete this source. Refresh and try again.";

/** React key for a source card or list row. */
export function sourceKey(source: SourceRef): string {
  return source.source_id;
}

/** The Library opened from a duplicate on Feed memory (/library?source=<id>):
 * only that source. No id: every source. */
export function focusOn<T extends SourceRef>(sources: T[], focusId: string | null): T[] {
  return focusId ? sources.filter((s) => s.source_id === focusId) : sources;
}

/** The list without the one deleted source. Other sources, same title or not, stay. */
export function removeSource<T extends SourceRef>(sources: T[], sourceId: string): T[] {
  return sources.filter((s) => s.source_id !== sourceId);
}

export type DeleteOutcome = { ok: true; chunksRemoved: number } | { ok: false; message: string };

/**
 * What a DELETE /library/source response means. Only a 2xx whose body reports
 * the deletion counts as deleted, so the card is removed only once the backend
 * has confirmed it. Anything else (404, the 422 an older backend or frontend
 * produces mid-deploy, a 5xx, a body that isn't JSON) is a failure.
 */
export async function deleteOutcome(response: Response): Promise<DeleteOutcome> {
  if (!response.ok) return { ok: false, message: DELETE_FAILED_MESSAGE };
  try {
    const body = await response.json();
    if (body?.deleted === true && typeof body.chunks_removed === "number") {
      return { ok: true, chunksRemoved: body.chunks_removed };
    }
  } catch {
    // fall through: an unreadable body is not a confirmation
  }
  return { ok: false, message: DELETE_FAILED_MESSAGE };
}

// ── Authorship (provenance step 3.3) ─────────────────────────────────────────

/** Who wrote a source. user_stated and system_inferred are set by rule only. */
export type Authorship = "user_authored" | "user_stated" | "external" | "system_inferred";
/** What the user can choose (PATCH /sources/{id}/authorship). */
export type AuthorshipChoice = "user_authored" | "external";
export type AuthorshipSetBy = "user" | "classifier" | "rule";

export interface AuthorshipFields extends SourceRef {
  authorship?: string | null;
  authorship_set_by?: string | null;
}

const AUTHORSHIP_LABELS: Record<Authorship, string> = {
  user_authored: "Your writing",
  external: "Someone else's",
  user_stated: "Your answer to Contendo",
  system_inferred: "Made by Contendo",
};

export const AUTHORSHIP_QUESTION = "Is this your own writing or experience?";
export const AUTHORSHIP_CHOICES: { value: AuthorshipChoice; label: string }[] = [
  { value: "user_authored", label: "Yes, mine" },
  { value: "external", label: "No, someone else's" },
];

export type AuthorshipView =
  | { kind: "ask" }
  | { kind: "label"; authorship: Authorship; label: string; note: string | null; editable: boolean };

/**
 * What a Library card shows. No label (the classifier was not confident, or the
 * source predates it): the user is asked. The user's choice is marked as theirs;
 * a classifier label is marked as Contendo's guess; both can be changed. Rule
 * labels are facts of the input path (a profile answer, an image description)
 * and cannot be changed here. An unknown value is asked about, never guessed.
 */
export function authorshipView(source: AuthorshipFields): AuthorshipView {
  const a = source.authorship;
  if (!a || !(a in AUTHORSHIP_LABELS)) return { kind: "ask" };
  const authorship = a as Authorship;
  const label = AUTHORSHIP_LABELS[authorship];
  if (authorship === "user_stated" || authorship === "system_inferred") {
    return { kind: "label", authorship, label, note: null, editable: false };
  }
  const note = source.authorship_set_by === "user" ? "Set by you"
    : source.authorship_set_by === "classifier" ? "Contendo's guess" : null;
  return { kind: "label", authorship, label, note, editable: true };
}

/** Sources the "Needs your answer" filter shows. */
export function needsAnswer(source: AuthorshipFields): boolean {
  return authorshipView(source).kind === "ask";
}

/** The list with one source labelled by the user, as the backend just confirmed. */
export function applyAuthorship<T extends AuthorshipFields>(sources: T[], sourceId: string, authorship: AuthorshipChoice): T[] {
  return sources.map((s) => (s.source_id === sourceId ? { ...s, authorship, authorship_set_by: "user" } : s));
}

export const AUTHORSHIP_FAILED_MESSAGE = "Couldn't save this. Refresh and try again.";
export const AUTHORSHIP_BUSY_MESSAGE = "This source is being replaced. Try again in a moment.";

export type AuthorshipOutcome = { ok: true; authorship: AuthorshipChoice } | { ok: false; message: string };

/**
 * What a PATCH /sources/{id}/authorship response means. Only a 2xx whose body
 * echoes the requested label as set by the user counts as saved; the card
 * changes only then. 409 (a replace is running) gets its own message.
 */
export async function authorshipOutcome(response: Response, requested: AuthorshipChoice): Promise<AuthorshipOutcome> {
  if (response.status === 409) return { ok: false, message: AUTHORSHIP_BUSY_MESSAGE };
  if (!response.ok) return { ok: false, message: AUTHORSHIP_FAILED_MESSAGE };
  try {
    const body = await response.json();
    if (body?.authorship === requested && body.authorship_set_by === "user") {
      return { ok: true, authorship: requested };
    }
  } catch {
    // fall through: an unreadable body is not a confirmation
  }
  return { ok: false, message: AUTHORSHIP_FAILED_MESSAGE };
}
