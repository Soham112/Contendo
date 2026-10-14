import { realEstate } from "./real-estate";
import type { NicheLandingContent } from "./types";

// Every niche landing page. Adding one here adds its route, its sitemap entry,
// its footer link and its public-route entry: nothing else needs editing.
export const NICHE_PAGES: NicheLandingContent[] = [realEstate];

export function nichePage(slug: string): NicheLandingContent | undefined {
  return NICHE_PAGES.find((page) => page.slug === slug);
}

/** Whether a URL path is a niche landing page ("/social-media-posts-for-..."). */
export function isNichePath(pathname: string | null | undefined): boolean {
  return !!pathname && NICHE_PAGES.some((page) => pathname === `/${page.slug}`);
}

export type { NicheLandingContent } from "./types";
