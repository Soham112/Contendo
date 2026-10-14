import { describe, expect, it } from "vitest";
import { HOME_HERO, HOME_SEO, homeFaqs } from "@/content/home";
import type { Plans } from "./billing";
import { faqJsonLd, organizationJsonLd, softwareJsonLd } from "./json-ld";
import { DEFAULT_SOCIAL_IMAGE, pageMetadata, seoProblems, type OnPageText, type PageSeo } from "./seo";

const SEO: PageSeo = {
  title: "Schedule LinkedIn Posts Free",
  description: "How to schedule LinkedIn posts, with a reason to read on.",
  path: "/schedule-linkedin-posts",
  primaryKeyword: "schedule linkedin posts",
};
const PAGE: OnPageText = {
  h1: "Schedule LinkedIn posts",
  firstParagraph: "You can schedule LinkedIn posts in two ways.",
  imageAlts: ["The screen where you schedule LinkedIn posts"],
  faqCount: 5,
};

describe("seoProblems", () => {
  it("passes a page that follows every rule", () => {
    expect(seoProblems(SEO, PAGE)).toEqual([]);
  });

  it("counts the title with its | Contendo suffix", () => {
    const title = "Schedule LinkedIn posts " + "x".repeat(25); // 49 + 11 = 60
    expect(seoProblems({ ...SEO, title }, PAGE)).toEqual([]);
    expect(seoProblems({ ...SEO, title: title + "x" }, PAGE)).toEqual(["title is 61 characters, over 60"]);
  });

  it("wants the keyword near the front of the title", () => {
    expect(seoProblems({ ...SEO, title: "A long guide for busy people: schedule linkedin posts" }, PAGE)).toContain(
      "keyword is not near the front of the title"
    );
  });

  it("finds the keyword whatever its case, and reports each place it is missing", () => {
    const missing = seoProblems(
      { ...SEO, description: "x".repeat(156), path: "/linkedin" },
      { h1: "Plan ahead", firstParagraph: "Intro.", imageAlts: ["A calendar"], faqCount: 3 }
    );
    expect(missing).toEqual([
      "description is 156 characters, over 155",
      "description lacks the keyword",
      "URL lacks the keyword",
      "H1 lacks the keyword",
      "first paragraph lacks the keyword",
      "no image alt text has the keyword",
      "3 FAQs, not 4 to 6",
    ]);
  });

  it("does not ask the homepage URL for a keyword, nor a page without an FAQ for a count", () => {
    const { faqCount: _none, ...noFaq } = PAGE;
    expect(seoProblems({ ...SEO, path: "/" }, noFaq)).toEqual([]);
  });
});

describe("homepage", () => {
  it("follows the on-page rules", () => {
    const page = { h1: HOME_HERO.headline, firstParagraph: HOME_HERO.intro, imageAlts: [HOME_HERO.imageAlt], faqCount: homeFaqs().length };
    expect(seoProblems(HOME_SEO, page)).toEqual([]);
  });

  it("does not claim publishing while no platform is verified", () => {
    const text = [HOME_SEO.description, HOME_HERO.intro, ...homeFaqs().map((f) => f.answer)].join(" ");
    expect(homeFaqs().find((f) => f.question.includes("post to LinkedIn"))?.answer).toMatch(/^Not right now/);
    expect(text).not.toMatch(/publishes (them|it|posts) for you/i);
  });

  it("emits FAQ markup that is exactly the visible list", () => {
    const faqs = homeFaqs();
    expect(faqJsonLd(faqs).mainEntity.map((q) => [q.name, q.acceptedAnswer.text])).toEqual(faqs.map((f) => [f.question, f.answer]));
  });
});

describe("metadata", () => {
  it("writes the full title itself, ending in | Contendo", () => {
    expect(pageMetadata(SEO).title).toEqual({ absolute: "Schedule LinkedIn Posts Free | Contendo" });
    expect(pageMetadata(HOME_SEO).title).toEqual({ absolute: `${HOME_SEO.title} | Contendo` });
  });

  it("uses the page's own social image when it has one", () => {
    const image = { url: "/og/home.png", width: 1200, height: 630, alt: "Home" };
    const meta = pageMetadata({ ...SEO, image });
    expect(meta.openGraph?.images).toEqual([image]);
    expect(pageMetadata(SEO).openGraph?.images).toEqual([DEFAULT_SOCIAL_IMAGE]);
  });
});

describe("structured data", () => {
  const plans = (checkout_available: boolean): Plans => ({
    free: { generations_per_month: 10, publishing: false },
    pro: {
      generations_per_month: 300, publishing: true, max_accounts_per_platform: 1,
      price: { amount: 3900, currency: "usd", interval: "month", trial_days: 7 },
    },
    checkout_available,
  });

  it("offers Pro only while it can be bought", () => {
    expect(softwareJsonLd("https://example.com", "D", plans(true)).offers).toHaveLength(2);
    expect(softwareJsonLd("https://example.com", "D", plans(false)).offers).toEqual([
      { "@type": "Offer", name: "Free", price: "0", priceCurrency: "USD" },
    ]);
  });

  it("describes the organisation, listing profiles only when there are some", () => {
    const base = { name: "Contendo", url: "https://example.com/", logo: "https://example.com/l.png", email: "a@b.c" };
    expect(organizationJsonLd({ ...base, sameAs: [] })).not.toHaveProperty("sameAs");
    expect(organizationJsonLd({ ...base, sameAs: ["https://x.example/c"] }).sameAs).toEqual(["https://x.example/c"]);
    expect(organizationJsonLd({ ...base, sameAs: [] })["@type"]).toBe("Organization");
  });
});
