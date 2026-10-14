import type { Metadata } from "next";
import JsonLd from "@/components/marketing/JsonLd";
import { HOME_SEO, ORGANIZATION_SAME_AS } from "@/content/home";
import { legalIdentity } from "@/lib/legal";
import { organizationJsonLd, softwareJsonLd } from "@/lib/json-ld";
import { fetchPlans } from "@/lib/landing";
import { SITE_NAME, canonicalUrl, pageMetadata } from "@/lib/seo";
import WelcomePage from "./welcome/page";

export const metadata: Metadata = pageMetadata(HOME_SEO);
// Re-rendered at most every ten minutes, so the offers follow the backend's plans.
export const revalidate = 600;

// The homepage. /welcome renders the same page and names "/" as canonical; the
// structured data is emitted here only, on the canonical URL.
export default async function HomePage() {
  const plans = await fetchPlans();
  const url = canonicalUrl("/");
  return (
    <>
      <JsonLd
        data={organizationJsonLd({
          name: SITE_NAME,
          url,
          logo: canonicalUrl("/favicon.png"),
          email: legalIdentity().email,
          sameAs: ORGANIZATION_SAME_AS,
        })}
      />
      <JsonLd data={softwareJsonLd(url, HOME_SEO.description, plans)} />
      <WelcomePage />
    </>
  );
}
