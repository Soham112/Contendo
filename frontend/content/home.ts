// The homepage's SEO data and the copy the on-page rules check. The page
// (app/welcome/page.tsx), its metadata (app/page.tsx, app/welcome/layout.tsx)
// and its structured data all read from here.

import { verifiedPlatformFaq } from "@/content/verified-platforms";
import type { Faq } from "@/lib/json-ld";
import type { PageSeo } from "@/lib/seo";

export const HOME_SEO: PageSeo = {
  title: "AI LinkedIn Post Generator in Your Voice",
  description:
    "Contendo is an AI LinkedIn post generator that learns what you know and how you write, then drafts posts that sound like you. Start free.",
  path: "/",
  primaryKeyword: "ai linkedin post generator",
};

export const HOME_HERO = {
  headline: "The AI LinkedIn post generator that writes in your voice",
  tagline: "Write like yourself. At scale.",
  intro:
    "Contendo is an AI LinkedIn post generator that works from your own notes, reading and opinions, so every draft sounds like you wrote it.",
  imageAlt: "Illustration of a person riding a pen upward, for Contendo's AI LinkedIn post generator",
};

export const HOME_FAQ_HEADING = "Questions about the LinkedIn post generator";

/** Official profile URLs for the Organization structured data. */
// TODO(Soham): add Contendo's official profile URLs (e.g. the LinkedIn company page). Leave empty until they exist.
export const ORGANIZATION_SAME_AS: readonly string[] = [];

// Publishing is claimed only once a platform is production-verified.
const MANUAL_POSTING: Faq = {
  question: "Does Contendo post to LinkedIn for me?",
  answer: "Not right now. When a post is ready, you copy it from Contendo and publish it on LinkedIn yourself.",
};

/** The homepage FAQ, visible on the page and emitted as FAQPage structured data. */
export function homeFaqs(): Faq[] {
  return [
    {
      question: "What is an AI LinkedIn post generator?",
      answer:
        "A tool that drafts LinkedIn posts for you. Most work from a short prompt and produce generic text. Contendo works from material you give it, such as articles, notes and your own opinions, so the draft reflects what you actually know.",
    },
    {
      question: "Will the posts sound like me?",
      answer:
        "That is what Contendo is built for. It writes from your own sources and the voice settings in your profile, and you can edit every draft before you use it.",
    },
    {
      question: "What can I give it to write from?",
      answer:
        "Links to articles, PDFs, your own notes and transcripts, and the opinions you hold. Everything you add becomes context it can draw on for later posts.",
    },
    {
      question: "Is Contendo free?",
      answer: "You can start writing posts on the free plan without a card. The free plan includes a set number of posts each month.",
    },
    verifiedPlatformFaq() ?? MANUAL_POSTING,
  ];
}
