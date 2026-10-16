/**
 * What an ingest response (/ingest, /ingest-file, /scrape-and-ingest) means for
 * the Add to library form.
 *
 * - "stored": new content was added; clear the form.
 * - "duplicate": already in the library. When it is the same file, image or link
 *   (`replaceable`), the form keeps its input so "Replace" can resend it with
 *   `replace_source_id`: the source is re-extracted and replaced in place.
 *   When the text itself is already stored, replacing would change nothing.
 * - "empty": nothing was stored and it isn't a duplicate: an error.
 */

export interface IngestResult {
  chunks_stored: number;
  tags: string[];
  title?: string | null;
  word_count?: number | null;
  duplicate?: boolean;
  replaceable?: boolean;
  existing_source_id?: string | null;
  existing_title?: string | null;
}

export type IngestOutcome =
  | { kind: "stored" }
  | { kind: "duplicate"; replaceSourceId: string | null }
  | { kind: "empty" };

export function ingestOutcome(result: IngestResult): IngestOutcome {
  if (result.duplicate) {
    const id = result.replaceable && result.existing_source_id ? result.existing_source_id : null;
    return { kind: "duplicate", replaceSourceId: id };
  }
  return result.chunks_stored > 0 ? { kind: "stored" } : { kind: "empty" };
}

/** Keep the form's input after this outcome, so Replace can resend it. */
export function keepsInput(outcome: IngestOutcome): boolean {
  return outcome.kind === "duplicate" && outcome.replaceSourceId !== null;
}
