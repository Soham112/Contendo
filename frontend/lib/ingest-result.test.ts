import { expect, it } from "vitest";
import { ingestOutcome, keepsInput } from "./ingest-result";

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

it("text that is already stored is a duplicate with nothing to replace", () => {
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
