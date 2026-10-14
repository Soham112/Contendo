// Site-wide SEO helpers: one place that knows the site's address and builds a
// page's title, description, canonical URL and social cards.

import type { Metadata } from "next";

/** The site's public address. Set NEXT_PUBLIC_SITE_URL per deployment. */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://contendoai.com").replace(/\/+$/, "");
export const SITE_NAME = "Contendo";
export const DEFAULT_DESCRIPTION =
  "Contendo learns what you know and how you write, then writes posts in your voice and publishes them for you.";
const SOCIAL_IMAGE = { url: "/images/landing-hero.png", width: 1376, height: 768, alt: "Contendo" };

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
}: {
  title: string;
  description?: string;
  path: string;
  index?: boolean;
}): Metadata {
  const url = canonicalUrl(path);
  return {
    title,
    description,
    alternates: { canonical: url },
    robots: index ? undefined : { index: false, follow: false },
    openGraph: { title, description, url, siteName: SITE_NAME, type: "website", images: [SOCIAL_IMAGE] },
    twitter: { card: "summary_large_image", title, description, images: [SOCIAL_IMAGE.url] },
  };
}
