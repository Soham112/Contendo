import { expect, it } from "vitest";
import { DELETE_FAILED_MESSAGE, deleteOutcome, focusOn, removeSource, sourceKey } from "./library";

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
