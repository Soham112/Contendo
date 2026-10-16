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
