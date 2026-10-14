import { describe, expect, it } from "vitest";
import { errorDetail } from "./request-errors";

describe("errorDetail", () => {
  it("uses the server's own detail when it sent one", async () => {
    const res = new Response(JSON.stringify({ detail: "Topic is too long (limit 500 characters)" }), { status: 400 });
    expect(await errorDetail(res, "fallback")).toBe("Topic is too long (limit 500 characters)");
  });

  it("falls back for a plain-text error page instead of failing to parse it", async () => {
    expect(await errorDetail(new Response("Internal Server Error", { status: 500 }), "We couldn't do that.")).toBe("We couldn't do that.");
  });

  it("falls back when the detail is not text (validation errors are lists)", async () => {
    const res = new Response(JSON.stringify({ detail: [{ loc: ["body", "topic"], msg: "field required" }] }), { status: 422 });
    expect(await errorDetail(res, "fallback")).toBe("fallback");
  });
});
