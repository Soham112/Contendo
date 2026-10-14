// What a niche landing page says about plans and price, built from the
// backend's GET /billing/plans. No amount or allowance is written in the
// frontend: if the backend cannot be reached, the page states none.

import { formatPrice, type Plans } from "./billing";
import type { Faq } from "./json-ld";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";
// Plans change rarely: one fetch serves the page for ten minutes.
const REVALIDATE_SECONDS = 600;

/** The plans, fetched on the server. null when the backend cannot be reached. */
export async function fetchPlans(): Promise<Plans | null> {
  try {
    const res = await fetch(`${API}/billing/plans`, { next: { revalidate: REVALIDATE_SECONDS } });
    return res.ok ? ((await res.json()) as Plans) : null;
  } catch {
    return null;
  }
}

/** "Start free — 10 posts", or "Start free" when the allowance is unknown. */
export function ctaLabel(plans: Plans | null): string {
  return plans ? `Start free — ${plans.free.generations_per_month} posts` : "Start free";
}

/** The "what does it cost" question, answered from the plans. null when they are unknown. */
export function costFaq(plans: Plans | null): Faq | null {
  if (!plans) return null;
  const free = `Writing posts is free for ${plans.free.generations_per_month} posts a month, and you can copy them and post them yourself.`;
  const price = plans.pro.price;
  if (!price) return { question: "What does it cost?", answer: `${free} Publishing and scheduling are part of the Pro plan.` };
  const trial = price.trial_days > 0 ? ` You can try it free for ${price.trial_days} days first.` : "";
  return {
    question: "What does it cost?",
    answer: `${free} Having Contendo publish and schedule them for you is part of the Pro plan, which is ${formatPrice(price)}.${trial}`,
  };
}

/** Where the call to action goes: sign up, then onboarding with the niche chosen. */
export function startHref(nicheKey: string): string {
  return `/sign-up?redirect_url=${encodeURIComponent(`/get-started?niche=${nicheKey}`)}`;
}
