/**
 * What an ingest response (/ingest, /ingest-file, /scrape-and-ingest) means for
 * the Add to library form.
 *
 * - "stored": new content was added; clear the form.
 * - "duplicate": already in the library: the same file, image or link, or the
 *   same text (a source saved before its link was kept). The response names the
 *   match (`existing_*`). When it is the user's own source (`replaceable`), the
 *   form keeps its input so "Replace" can resend it with `replace_source_id`:
 *   the source is re-extracted and replaced in place, even if its text is unchanged.
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
  existing_type?: string | null;
  existing_added_at?: string | null;
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

/** sources.input_type, as a reader would name it; "unknown" (sources backfilled
 * from chunks) has no label. */
const SOURCE_TYPE_LABELS: Record<string, string> = {
  note: "note",
  file: "file",
  url: "web page",
  youtube: "YouTube video",
  image: "image",
  obsidian: "Obsidian note",
  business_profile: "business profile",
};

export interface DuplicateMatch {
  sourceId: string;
  title: string | null; // null: the source has no title
  details: string;     // "YouTube video, added 23 Apr 2026", or "" when neither is known
  libraryHref: string; // the Library showing only this source
}

/** Which source a duplicate matched, for "matches '<title>' (<type>, added <date>)". */
export function duplicateMatch(result: IngestResult): DuplicateMatch | null {
  if (!result.duplicate || !result.existing_source_id) return null;
  const type = result.existing_type ? SOURCE_TYPE_LABELS[result.existing_type] : undefined;
  const added = result.existing_added_at ? new Date(result.existing_added_at) : null;
  const date = added && !Number.isNaN(added.getTime())
    ? added.toLocaleDateString("en-GB", { day: "numeric", month: "short", year: "numeric" })
    : null;
  return {
    sourceId: result.existing_source_id,
    title: result.existing_title?.trim() || null,
    details: [type, date && `added ${date}`].filter(Boolean).join(", "),
    libraryHref: `/library?source=${encodeURIComponent(result.existing_source_id)}`,
  };
}
