import { expect, it } from "vitest";
import { NO_POST_FALLBACK, NO_POST_MESSAGES, generateOutcome } from "./generate-outcome";

it("a post is a post", () => {
  expect(generateOutcome({ status: "ok", post: "A post." })).toEqual({ kind: "post" });
  expect(generateOutcome({ post: "A post." })).toEqual({ kind: "post" }); // older responses carry no status
});

it("low coverage carries the closest sources and whether an opinion post may be offered", () => {
  const sources = [{ title: "Notes", preview: "…", similarity: 0.2 }];
  expect(generateOutcome({ status: "low_coverage", post: "", closest_sources: sources, no_specifics_enabled: true }))
    .toEqual({ kind: "low_coverage", closestSources: sources, noSpecificsEnabled: true });
  expect(generateOutcome({ status: "low_coverage", post: "" }))
    .toEqual({ kind: "low_coverage", closestSources: [], noSpecificsEnabled: false });
});

it.each(["draft_truncated", "draft_refused", "draft_empty"])("%s shows the backend's message and never a post", (status) => {
  expect(generateOutcome({ status, post: "", message: "The backend's own words." }))
    .toEqual({ kind: "no_post", status, message: "The backend's own words." });
});

it.each(["draft_truncated", "draft_refused", "draft_empty"])("%s without a message still says what happened", (status) => {
  const outcome = generateOutcome({ status, post: "" });
  expect(outcome).toEqual({ kind: "no_post", status, message: NO_POST_MESSAGES[status] });
  expect(NO_POST_MESSAGES[status].length).toBeGreaterThan(20);
});

it("a blank message falls back to the status's own message", () => {
  expect(generateOutcome({ status: "draft_refused", post: "", message: "   " }))
    .toMatchObject({ kind: "no_post", message: NO_POST_MESSAGES.draft_refused });
});

it("an ok response with an empty post is not shown as a blank post", () => {
  expect(generateOutcome({ status: "ok", post: "" })).toEqual({ kind: "no_post", status: "ok", message: NO_POST_FALLBACK });
  expect(generateOutcome({ status: "ok", post: "  \n " })).toMatchObject({ kind: "no_post" });
  expect(generateOutcome({})).toMatchObject({ kind: "no_post" });
});

it("a status this page does not know is a message, never a silent failure", () => {
  expect(generateOutcome({ status: "some_new_status", post: "", message: "Explained by the backend." }))
    .toEqual({ kind: "no_post", status: "some_new_status", message: "Explained by the backend." });
  expect(generateOutcome({ status: "some_new_status", post: "" }))
    .toEqual({ kind: "no_post", status: "some_new_status", message: NO_POST_FALLBACK });
  // even if such a response carried text, a status that is not "ok" is not a finished post
  expect(generateOutcome({ status: "draft_truncated", post: "Half a po" })).toMatchObject({ kind: "no_post" });
});


it("returns a flagged draft for review instead of hiding its text", () => {
  expect(generateOutcome({ status: "needs_review", post: "A flagged draft." })).toEqual({ kind: "post" });
  expect(generateOutcome({ status: "needs_review", post: "" })).toMatchObject({ kind: "no_post" });
});
