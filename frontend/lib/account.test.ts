import { describe, expect, it } from "vitest";
import {
  EMPTY_BUSINESS_PROFILE,
  businessFormErrors,
  normaliseWebsite,
  resolveNicheParam,
} from "./account";

const OPTIONS = {
  other_niche: "other",
  niches: [
    { key: "real_estate", label: "Real estate agent", pillars: [] },
    { key: "other", label: "Other", pillars: [] },
  ],
};

const FILLED = {
  ...EMPTY_BUSINESS_PROFILE,
  business_name: "Harbor Street Realty",
  service_area: "Portland, Maine",
  services: "Homes for first-time buyers.",
  tone: "friendly",
};

describe("resolveNicheParam", () => {
  it("accepts a niche the backend lists", () => {
    expect(resolveNicheParam("real_estate", OPTIONS)).toBe("real_estate");
  });

  it("drops anything else", () => {
    expect(resolveNicheParam("astrologer", OPTIONS)).toBeNull();
    expect(resolveNicheParam("<script>", OPTIONS)).toBeNull();
    expect(resolveNicheParam("", OPTIONS)).toBeNull();
    expect(resolveNicheParam(null, OPTIONS)).toBeNull();
  });
});

describe("normaliseWebsite", () => {
  it("adds https to a bare domain and leaves the rest alone", () => {
    expect(normaliseWebsite(" example.com ")).toBe("https://example.com");
    expect(normaliseWebsite("http://example.com")).toBe("http://example.com");
    expect(normaliseWebsite("  ")).toBe("");
  });
});

describe("businessFormErrors", () => {
  it("passes a complete form", () => {
    expect(businessFormErrors("real_estate", "", FILLED, OPTIONS)).toEqual({});
  });

  it("names each missing required field", () => {
    const errors = businessFormErrors(null, "", EMPTY_BUSINESS_PROFILE, OPTIONS);
    expect(Object.keys(errors).sort()).toEqual(["business_name", "niche", "service_area", "services", "tone"]);
  });

  it("needs the user's own words for the other niche", () => {
    expect(businessFormErrors("other", "  ", FILLED, OPTIONS).niche).toBeDefined();
    expect(businessFormErrors("other", "Dog groomer", FILLED, OPTIONS)).toEqual({});
  });

  it("flags a website that is not an address, and allows none", () => {
    expect(businessFormErrors("real_estate", "", { ...FILLED, website: "not a url" }, OPTIONS).website).toBeDefined();
    expect(businessFormErrors("real_estate", "", { ...FILLED, website: "example.com" }, OPTIONS)).toEqual({});
  });
});
