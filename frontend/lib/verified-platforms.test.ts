import { describe, expect, it } from "vitest";
import { VERIFIED_PUBLISHING_PLATFORMS, verifiedPlatformFaq } from "../content/verified-platforms";
import { realEstate } from "../content/niches/real-estate";

describe("production platform claims", () => {
  it("starts empty and emits no platform FAQ", () => {
    expect(VERIFIED_PUBLISHING_PLATFORMS).toEqual([]);
    expect(verifiedPlatformFaq()).toBeNull();
    expect(realEstate.faqs.some((faq) => faq.question.includes("platforms"))).toBe(false);
  });
  it("names only the platforms explicitly verified", () => {
    const faq = verifiedPlatformFaq([{ key: "linkedin", label: "LinkedIn" }]);
    expect(faq?.answer).toContain("LinkedIn");
    expect(faq?.answer).not.toMatch(/Facebook|TikTok|YouTube|Instagram/);
  });
});
