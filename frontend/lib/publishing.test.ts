import { describe, expect, it } from "vitest";
import { fit, localInputToIso, statusLabel, type PlatformRules } from "./publishing";

const X: PlatformRules = { platform: "x", label: "X", max_characters: 280, media_required: "none", max_images: 4 };
const INSTAGRAM: PlatformRules = {
  platform: "instagram", label: "Instagram", max_characters: 2200, media_required: "image_or_video", max_images: 10,
};
const TIKTOK: PlatformRules = { platform: "tiktok", label: "TikTok", max_characters: 2200, media_required: "video", max_images: 0 };

describe("fit", () => {
  it("passes a post within the rules", () => {
    expect(fit(X, "x".repeat(280), [])).toEqual({ count: 280, problems: [] });
    expect(fit(INSTAGRAM, "Hello", [{ ref: "m", kind: "image" }]).problems).toEqual([]);
  });

  it("says how far over the limit a post is", () => {
    expect(fit(X, "x".repeat(300), []).problems).toEqual(["20 characters over the limit"]);
  });

  it("says what media a platform needs", () => {
    expect(fit(INSTAGRAM, "Hello", []).problems).toEqual(["Needs an image or a video"]);
    expect(fit(TIKTOK, "Hello", [{ ref: "m", kind: "image" }]).problems).toEqual(["Needs a video"]);
  });
});

describe("localInputToIso", () => {
  it("keeps the wall-clock time and adds the zone's offset", () => {
    const iso = localInputToIso("2026-11-03T09:30");
    expect(iso).toMatch(/^2026-11-03T09:30:00[+-]\d{2}:\d{2}$/);
    // Same instant as the browser reads the input.
    expect(new Date(iso as string).getTime()).toBe(new Date("2026-11-03T09:30").getTime());
  });

  it("is null for an empty or invalid value", () => {
    expect(localInputToIso("")).toBeNull();
    expect(localInputToIso("soon")).toBeNull();
  });
});

describe("statusLabel", () => {
  it("shows a job held by a failed payment as paused", () => {
    expect(statusLabel({ status: "scheduled", error_code: "payment_required" })).toBe("Paused");
    expect(statusLabel({ status: "scheduled", error_code: null })).toBe("Scheduled");
    expect(statusLabel({ status: "failed", error_code: "reconnect_required" })).toBe("Not published");
  });
});

import { allFlagsAccepted, type ContentReview } from "./publishing";

describe("claim resolution before approval", () => {
  const review: ContentReview = { id: "r", post_id: null, content: "A young couple paid $900,000.", media: [], approved_at: null,
    flags: [{ id: "age", text: "young", sentence: "", reason: "age absent" },
      { id: "price", text: "$900,000", sentence: "", reason: "price absent" }] };
  it("requires each flag and rejects unknown ids", () => {
    expect(allFlagsAccepted(review, [])).toBe(false);
    expect(allFlagsAccepted(review, ["age"])).toBe(false);
    expect(allFlagsAccepted(review, ["age", "price", "unknown"])).toBe(false);
    expect(allFlagsAccepted(review, ["age", "price"])).toBe(true);
  });
});
