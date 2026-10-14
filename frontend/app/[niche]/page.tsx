import type { Metadata } from "next";
import { notFound } from "next/navigation";
import { NICHE_PAGES, nichePage } from "@/content/niches";
import { fetchPlans } from "@/lib/landing";
import { pageMetadata } from "@/lib/seo";
import NicheLanding from "@/components/marketing/NicheLanding";

// Niche landing pages, e.g. /social-media-posts-for-real-estate-agents. Only
// the slugs in content/niches exist: every other single-segment path is a 404.
export const dynamicParams = false;
// Re-rendered at most every ten minutes, so a price change in Stripe (read
// through the backend) reaches the page without a deploy.
export const revalidate = 600;

export function generateStaticParams() {
  return NICHE_PAGES.map((page) => ({ niche: page.slug }));
}

export function generateMetadata({ params }: { params: { niche: string } }): Metadata {
  const content = nichePage(params.niche);
  if (!content) return {};
  return pageMetadata({ title: content.metaTitle, description: content.metaDescription, path: `/${content.slug}` });
}

export default async function NichePage({ params }: { params: { niche: string } }) {
  const content = nichePage(params.niche);
  if (!content) notFound();
  return <NicheLanding content={content} plans={await fetchPlans()} />;
}
