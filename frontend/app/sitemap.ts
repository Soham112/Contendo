import type { MetadataRoute } from "next";
import { NICHE_PAGES } from "@/content/niches";
import { canonicalUrl } from "@/lib/seo";

// The public pages. Pages behind sign-in are left out (and disallowed in robots.ts).
const PUBLIC_PAGES = ["/", "/about"];

export default function sitemap(): MetadataRoute.Sitemap {
  const paths = [...PUBLIC_PAGES, ...NICHE_PAGES.map((page) => `/${page.slug}`)];
  return paths.map((path) => ({ url: canonicalUrl(path), changeFrequency: "weekly", priority: path === "/" ? 1 : 0.8 }));
}
