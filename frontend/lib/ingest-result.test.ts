import { expect, it } from "vitest";
import { duplicateMatch, ingestOutcome, keepsInput } from "./ingest-result";

it("new content is stored and the form clears", () => {
  const outcome = ingestOutcome({ chunks_stored: 3, tags: [] });
  expect(outcome).toEqual({ kind: "stored" });
  expect(keepsInput(outcome)).toBe(false);
});

it("the same file or link again offers Replace and keeps the input", () => {
  const outcome = ingestOutcome({ chunks_stored: 0, tags: [], duplicate: true, replaceable: true, existing_source_id: "s1" });
  expect(outcome).toEqual({ kind: "duplicate", replaceSourceId: "s1" });
  expect(keepsInput(outcome)).toBe(true);
});

it("a duplicate that isn't replaceable keeps nothing for Replace", () => {
  const outcome = ingestOutcome({ chunks_stored: 2, tags: [], duplicate: true, replaceable: false, existing_source_id: "s1" });
  expect(outcome).toEqual({ kind: "duplicate", replaceSourceId: null });
  expect(keepsInput(outcome)).toBe(false);
});

it("a replaceable duplicate without an id can't be replaced", () => {
  expect(ingestOutcome({ chunks_stored: 0, tags: [], duplicate: true, replaceable: true }))
    .toEqual({ kind: "duplicate", replaceSourceId: null });
});

it("nothing stored and no duplicate is empty", () => {
  expect(ingestOutcome({ chunks_stored: 0, tags: [] })).toEqual({ kind: "empty" });
});

it("an exact-text match names the source, its type and the date it was added", () => {
  const match = duplicateMatch({
    chunks_stored: 6, tags: ["langgraph"], duplicate: true, replaceable: true, existing_source_id: "1776a2a0",
    existing_title: "Langraph is an extension of Langchain", existing_type: "youtube",
    existing_added_at: "2026-04-23T19:57:03.895708+00:00",
  });
  expect(match).toEqual({
    sourceId: "1776a2a0", title: "Langraph is an extension of Langchain",
    details: "YouTube video, added 23 Apr 2026", libraryHref: "/library?source=1776a2a0",
  });
});

it("an untitled, backfilled match still names what is known", () => {
  const match = duplicateMatch({ chunks_stored: 1, tags: [], duplicate: true, existing_source_id: "s1",
                                 existing_title: "  ", existing_type: "unknown", existing_added_at: "not a date" });
  expect(match).toMatchObject({ title: null, details: "" });
});

it("no match without a duplicate or an id", () => {
  expect(duplicateMatch({ chunks_stored: 3, tags: [] })).toBeNull();
  expect(duplicateMatch({ chunks_stored: 0, tags: [], duplicate: true })).toBeNull();
});
