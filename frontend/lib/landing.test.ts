import { describe, expect, it } from "vitest";
import { NICHE_PAGES, isNichePath, nichePage } from "@/content/niches";
import { publishableTestimonials, TESTIMONIALS, type Testimonial } from "@/content/testimonials";
import type { Plans } from "./billing";
import { faqJsonLd, serializeJsonLd, softwareJsonLd } from "./json-ld";
import { costFaq, ctaLabel, startHref } from "./landing";
import { canonicalUrl, pageMetadata, SITE_URL } from "./seo";

const PLANS: Plans = {
  free: { generations_per_month: 10, publishing: false },
  pro: {
    generations_per_month: 300, publishing: true, max_accounts_per_platform: 1,
    price: { amount: 3900, currency: "usd", interval: "month", trial_days: 7 },
  },
};

describe("niche pages", () => {
  it("have unique slugs and distinct copy", () => {
    const unique = (values: string[]) => new Set(values).size === values.length;
    expect(unique(NICHE_PAGES.map((p) => p.slug))).toBe(true);
    expect(unique(NICHE_PAGES.map((p) => p.headline))).toBe(true);
    expect(unique(NICHE_PAGES.map((p) => p.metaDescription))).toBe(true);
    expect(unique(NICHE_PAGES.map((p) => p.metaTitle))).toBe(true);
  });

  it("are found by slug and by path, and nothing else is", () => {
    expect(nichePage("social-media-posts-for-real-estate-agents")?.nicheKey).toBe("real_estate");
    expect(isNichePath("/social-media-posts-for-real-estate-agents")).toBe(true);
    expect(isNichePath("/social-media-posts-for-real-estate-agents/extra")).toBe(false);
    expect(isNichePath("/create")).toBe(false);
    expect(nichePage("pricing")).toBeUndefined();
  });

  it("keep meta descriptions within what search results show", () => {
    for (const page of NICHE_PAGES) expect(page.metaDescription.length).toBeLessThanOrEqual(160);
  });

  it("show examples for distinct pillars only", () => {
    for (const page of NICHE_PAGES) {
      const pillars = page.examples.map((e) => e.pillar);
      expect(new Set(pillars).size).toBe(pillars.length);
    }
  });
});

describe("plans on the landing page", () => {
  it("takes every figure from the backend's plans", () => {
    expect(ctaLabel(PLANS)).toBe("Start free — 10 posts");
    const cost = costFaq(PLANS);
    expect(cost?.answer).toContain("10 posts a month");
    expect(cost?.answer).toContain("$39 a month");
    expect(cost?.answer).toContain("7 days");
  });

  it("states no figure when the backend cannot be reached or has no price", () => {
    expect(ctaLabel(null)).toBe("Start free");
    expect(costFaq(null)).toBeNull();
    const noPrice = costFaq({ ...PLANS, pro: { ...PLANS.pro, price: null } });
    expect(noPrice?.answer).not.toMatch(/\$/);
  });

  it("sends the call to action to onboarding with the niche chosen", () => {
    expect(startHref("real_estate")).toBe("/sign-up?redirect_url=%2Fget-started%3Fniche%3Dreal_estate");
  });
});

describe("structured data", () => {
  it("FAQ markup is exactly the visible questions and answers", () => {
    const page = NICHE_PAGES[0];
    const faqs = [...page.faqs, costFaq(PLANS)!];
    const data = faqJsonLd(faqs);
    expect(data["@type"]).toBe("FAQPage");
    expect(data.mainEntity.map((q) => [q.name, q.acceptedAnswer.text])).toEqual(faqs.map((f) => [f.question, f.answer]));
    expect(faqs.length).toBeGreaterThanOrEqual(5);
    expect(faqs.length).toBeLessThanOrEqual(7);
  });

  it("describes the product with offers from the plans and no ratings", () => {
    const data = softwareJsonLd("https://example.com/x", "About it.", PLANS);
    expect(data.offers).toEqual([
      { "@type": "Offer", name: "Free", price: "0", priceCurrency: "USD" },
      { "@type": "Offer", name: "Pro", price: "39.00", priceCurrency: "USD" },
    ]);
    expect(Object.keys(data)).not.toContain("aggregateRating");
    expect(Object.keys(data)).not.toContain("review");
    expect(softwareJsonLd("https://example.com/x", "About it.", null).offers).toHaveLength(1);
  });

  it("cannot close its script element", () => {
    expect(serializeJsonLd({ text: "</script><script>alert(1)" })).not.toContain("<");
  });
});

describe("canonical URLs", () => {
  it("drop query strings, fragments and trailing slashes", () => {
    expect(canonicalUrl("/about?ref=x&utm_source=y")).toBe(`${SITE_URL}/about`);
    expect(canonicalUrl("/about/#team")).toBe(`${SITE_URL}/about`);
    expect(canonicalUrl("/")).toBe(`${SITE_URL}/`);
  });

  it("are set on every page's metadata, with social cards", () => {
    const meta = pageMetadata({ title: "T", description: "D", path: "/about?ref=x" });
    expect(meta.alternates?.canonical).toBe(`${SITE_URL}/about`);
    expect(meta.openGraph?.title).toBe("T");
    expect((meta.twitter as { card: string }).card).toBe("summary_large_image");
    expect(pageMetadata({ title: "T", path: "/create", index: false }).robots).toEqual({ index: false, follow: false });
  });
});

describe("testimonials", () => {
  const real: Testimonial = {
    name: "A. Person", role: "Agent", quote: "It works.", permissionConfirmed: true, date: "2026-10-01",
  };

  it("ship with none", () => {
    expect(TESTIMONIALS).toEqual([]);
    expect(publishableTestimonials("real_estate")).toEqual([]);
  });

  it("show only entries whose permission is confirmed", () => {
    const all = [real, { ...real, name: "B", permissionConfirmed: false }, { ...real, name: "C", quote: " " }];
    expect(publishableTestimonials("real_estate", all).map((t) => t.name)).toEqual(["A. Person"]);
  });

  it("keep a niche's testimonial on that niche's page", () => {
    const all = [{ ...real, nicheKey: "dentist" }];
    expect(publishableTestimonials("real_estate", all)).toEqual([]);
    expect(publishableTestimonials("dentist", all)).toHaveLength(1);
  });
});
