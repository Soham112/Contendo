import type { MetadataRoute } from "next";
import { SITE_URL } from "@/lib/seo";

// Pages behind sign-in, and the sign-in flow itself: nothing there to index.
const PRIVATE = [
  "/create", "/feed-memory", "/ideas", "/library", "/history", "/scheduled", "/settings", "/admin",
  "/get-started", "/first-post", "/onboarding", "/sign-in", "/sign-up", "/sso-callback", "/auth",
];

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [{ userAgent: "*", allow: "/", disallow: PRIVATE }],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
