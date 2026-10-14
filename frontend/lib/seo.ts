// Site-wide SEO helpers: one place that knows the site's address and builds a
// page's title, description, canonical URL and social cards.

import type { Metadata } from "next";

/** The site's public address. Set NEXT_PUBLIC_SITE_URL per deployment. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://contendoai.com").replace(/\/+$/, "");
export const SITE_NAME = "Contendo";
// No publishing claim here: it is the fallback on every page, and publishing is
// only claimed where VERIFIED_PUBLISHING_PLATFORMS says it works.
export const DEFAULT_DESCRIPTION =
  "Contendo learns what you know and how you write, then writes posts in your voice.";
/** Ends every page's title tag. pageMetadata() adds it. */
export const TITLE_SUFFIX = ` | ${SITE_NAME}`;

export interface SocialImage {
  url: string;
  width: number;
  height: number;
  alt: string;
}

export const DEFAULT_SOCIAL_IMAGE: SocialImage = { url: "/images/landing-hero.png", width: 1376, height: 768, alt: "Contendo" };

/**
 * The SEO data of one keyword-targeted page, kept with the page's content so
 * metadata, structured data and the on-page checks all read the same values.
 * `title` is without TITLE_SUFFIX.
 */
export interface PageSeo {
  title: string;
  description: string;
  path: string;
  /** The one search phrase this page is written to rank for. */
  primaryKeyword: string;
  image?: SocialImage;
}

/** A path's canonical URL: no query string, no fragment, no trailing slash. */
export function canonicalUrl(path: string): string {
  const clean = path.split(/[?#]/)[0].replace(/\/+$/, "");
  return `${SITE_URL}${clean.startsWith("/") ? clean : `/${clean}`}` || SITE_URL;
}

/**
 * Metadata for one page. `path` is its canonical path, so ?ref= and UTM
 * variants all point search engines at the same URL. `index: false` is for
 * pages behind sign-in.
 */
export function pageMetadata({
  title,
  description = DEFAULT_DESCRIPTION,
  path,
  index = true,
  image = DEFAULT_SOCIAL_IMAGE,
}: {
  title: string;
  description?: string;
  path: string;
  index?: boolean;
  image?: SocialImage;
}): Metadata {
  const url = canonicalUrl(path);
  return {
    // Absolute, because Next applies the layout's title template only to child
    // segments, and the homepage shares the root layout's segment.
    title: { absolute: `${title}${TITLE_SUFFIX}` },
    description,
    alternates: { canonical: url },
    robots: index ? undefined : { index: false, follow: false },
    openGraph: { title, description, url, siteName: SITE_NAME, type: "website", images: [image] },
    twitter: { card: "summary_large_image", title, description, images: [image.url] },
  };
}

/** What a keyword page shows, as far as the on-page rules care. */
export interface OnPageText {
  h1: string;
  firstParagraph: string;
  imageAlts: string[];
  faqCount?: number;
}

const MAX_TITLE = 60;
const MAX_DESCRIPTION = 155;

/**
 * Where a keyword page breaks the on-page rules: the primary keyword in the
 * slug, near the front of the title, and in the description, H1, first
 * paragraph and an image's alt text; title and description lengths; 4 to 6
 * FAQs. An empty list means the page passes.
 */
export function seoProblems(seo: PageSeo, page: OnPageText): string[] {
  const keyword = seo.primaryKeyword.toLowerCase();
  const has = (text: string) => text.toLowerCase().includes(keyword);
  const problems: string[] = [];
  const title = `${seo.title}${TITLE_SUFFIX}`;
  if (title.length > MAX_TITLE) problems.push(`title is ${title.length} characters, over ${MAX_TITLE}`);
  const at = seo.title.toLowerCase().indexOf(keyword);
  if (at < 0) problems.push("title lacks the keyword");
  else if (at > seo.title.length / 2) problems.push("keyword is not near the front of the title");
  if (seo.description.length > MAX_DESCRIPTION) problems.push(`description is ${seo.description.length} characters, over ${MAX_DESCRIPTION}`);
  if (!has(seo.description)) problems.push("description lacks the keyword");
  const slug = keyword.trim().replace(/\s+/g, "-");
  if (seo.path !== "/" && !seo.path.toLowerCase().includes(slug)) problems.push("URL lacks the keyword");
  if (!has(page.h1)) problems.push("H1 lacks the keyword");
  if (!has(page.firstParagraph)) problems.push("first paragraph lacks the keyword");
  if (!page.imageAlts.some(has)) problems.push("no image alt text has the keyword");
  if (page.faqCount !== undefined && (page.faqCount < 4 || page.faqCount > 6)) problems.push(`${page.faqCount} FAQs, not 4 to 6`);
  return problems;
}
