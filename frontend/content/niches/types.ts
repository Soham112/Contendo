// The content of one niche landing page. The template
// (components/marketing/NicheLanding.tsx) renders any niche from this shape, so
// a new page is a new content file plus one line in ./index.ts.
//
// Each niche needs its own copy and its own examples: a page that only swaps
// the niche's name into another page's text is a thin duplicate and hurts both.

export interface NicheStep {
  title: string;
  body: string;
  /** A real screenshot of the app, under /public. Omit until one is captured. */
  image?: { src: string; alt: string; width: number; height: number };
}

export interface NicheExample {
  /** The pillar's label as GET /niches gives it, e.g. "New listing". */
  pillar: string;
  /** A post Contendo generated from fictional details. Never a real business. */
  post: string;
}

export interface NicheFaq {
  question: string;
  answer: string;
}

export interface NicheLandingContent {
  /** The URL path segment, e.g. "social-media-posts-for-real-estate-agents". */
  slug: string;
  /** The niche key in backend/config/niches.py; the call to action passes it to onboarding. */
  nicheKey: string;
  /** How the footer links to this page, e.g. "Real estate agents". */
  linkLabel: string;
  metaTitle: string;
  metaDescription: string;
  headline: string;
  subhead: string;
  steps: [NicheStep, NicheStep, NicheStep];
  examplesIntro: string;
  examples: NicheExample[];
  /** Questions answered the same whatever the plan costs. The cost question is added from the backend's price. */
  faqs: NicheFaq[];
}
