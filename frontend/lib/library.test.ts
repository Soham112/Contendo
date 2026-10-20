import { expect, it } from "vitest";
import {
  AUTHORSHIP_BUSY_MESSAGE, AUTHORSHIP_FAILED_MESSAGE, DELETE_FAILED_MESSAGE, applyAuthorship, authorshipOutcome,
  authorshipView, deleteOutcome, focusOn, needsAnswer, removeSource, sourceKey,
} from "./library";

const twins = [
  { source_id: "a", source_title: "Untitled", chunk_count: 2 },
  { source_id: "b", source_title: "Untitled", chunk_count: 3 },
  { source_id: "c", source_title: "Billing notes", chunk_count: 1 },
];

it("removing one of two same-title sources leaves the other", () => {
  expect(removeSource(twins, "a").map((s) => s.source_id)).toEqual(["b", "c"]);
});

it("removing an id that isn't listed changes nothing", () => {
  expect(removeSource(twins, "zzz")).toEqual(twins);
});

it("keys are source ids, unique even when titles repeat", () => {
  const keys = twins.map(sourceKey);
  expect(keys).toEqual(["a", "b", "c"]);
  expect(new Set(keys).size).toBe(twins.length);
});

const json = (status: number, body: unknown) =>
  new Response(JSON.stringify(body), { status, headers: { "Content-Type": "application/json" } });

it("a confirmed delete reports the chunks removed", async () => {
  expect(await deleteOutcome(json(200, { deleted: true, chunks_removed: 4, message: "Removed 4 chunks" })))
    .toEqual({ ok: true, chunksRemoved: 4 });
});

it.each([
  ["404", json(404, { detail: "Source not found" })],
  ["422 during the deploy window", json(422, { detail: [{ loc: ["body", "source_id"], msg: "Field required" }] })],
  ["500 with a plain-text body", new Response("Internal Server Error", { status: 500 })],
  ["200 that doesn't confirm", json(200, { deleted: false })],
  ["200 that isn't JSON", new Response("ok", { status: 200 })],
])("%s keeps the card and shows the delete error", async (_label, response) => {
  expect(await deleteOutcome(response)).toEqual({ ok: false, message: DELETE_FAILED_MESSAGE });
});

it("a link to one source shows only that source; no link shows all", () => {
  const sources = [{ source_id: "a" }, { source_id: "b" }];
  expect(focusOn(sources, "b")).toEqual([{ source_id: "b" }]);
  expect(focusOn(sources, "gone")).toEqual([]);
  expect(focusOn(sources, null)).toEqual(sources);
});

// ── Authorship ───────────────────────────────────────────────────────────────

it("an unlabelled source asks the user, as does an unknown or missing value", () => {
  for (const s of [
    { source_id: "a", authorship: null, authorship_set_by: null },
    { source_id: "b" },
    { source_id: "c", authorship: "someone", authorship_set_by: "classifier" },
  ]) {
    expect(authorshipView(s)).toEqual({ kind: "ask" });
    expect(needsAnswer(s)).toBe(true);
  }
});

it("a classifier label is Contendo's guess and can be changed", () => {
  expect(authorshipView({ source_id: "a", authorship: "external", authorship_set_by: "classifier" }))
    .toEqual({ kind: "label", authorship: "external", label: "Someone else's", note: "Contendo's guess", editable: true });
});

it("the user's choice is marked as theirs and can be changed", () => {
  const v = authorshipView({ source_id: "a", authorship: "user_authored", authorship_set_by: "user" });
  expect(v).toEqual({ kind: "label", authorship: "user_authored", label: "Your writing", note: "Set by you", editable: true });
  expect(needsAnswer({ source_id: "a", authorship: "user_authored", authorship_set_by: "user" })).toBe(false);
});

it("rule labels are shown but cannot be changed", () => {
  expect(authorshipView({ source_id: "a", authorship: "user_stated", authorship_set_by: "rule" }))
    .toEqual({ kind: "label", authorship: "user_stated", label: "Your answer to Contendo", note: null, editable: false });
  expect(authorshipView({ source_id: "a", authorship: "system_inferred", authorship_set_by: "rule" }))
    .toMatchObject({ label: "Made by Contendo", editable: false });
});

it("applying a choice changes only that source and marks it as the user's", () => {
  const list = [
    { source_id: "a", authorship: "external", authorship_set_by: "classifier" },
    { source_id: "b", authorship: null, authorship_set_by: null },
  ];
  expect(applyAuthorship(list, "b", "user_authored")).toEqual([
    list[0],
    { source_id: "b", authorship: "user_authored", authorship_set_by: "user" },
  ]);
});

it("a confirmed PATCH saves the requested label", async () => {
  const body = { source_id: "a", authorship: "external", authorship_set_by: "user", spans_mapped: true };
  expect(await authorshipOutcome(json(200, body), "external")).toEqual({ ok: true, authorship: "external" });
});

it("a 409 says a replace is running; other failures say it wasn't saved", async () => {
  expect(await authorshipOutcome(json(409, { detail: "busy" }), "external"))
    .toEqual({ ok: false, message: AUTHORSHIP_BUSY_MESSAGE });
  for (const status of [404, 422, 500]) {
    expect(await authorshipOutcome(json(status, {}), "external"))
      .toEqual({ ok: false, message: AUTHORSHIP_FAILED_MESSAGE });
  }
});

it("a 2xx that doesn't confirm the requested label is not a save", async () => {
  const mismatch = { authorship: "user_authored", authorship_set_by: "user" };
  expect((await authorshipOutcome(json(200, mismatch), "external")).ok).toBe(false);
  expect((await authorshipOutcome(json(200, { authorship: "external", authorship_set_by: "classifier" }), "external")).ok).toBe(false);
  expect((await authorshipOutcome(new Response("not json", { status: 200 }), "external")).ok).toBe(false);
});
