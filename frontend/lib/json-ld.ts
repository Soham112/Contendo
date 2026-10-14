// Structured data for the landing pages, built from the same values the page
// shows. The FAQ markup takes the visible question-and-answer list itself, so
// the two cannot differ.

import type { Plans } from "./billing";

export interface Faq {
  question: string;
  answer: string;
}

export function faqJsonLd(faqs: Faq[]) {
  return {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: faqs.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: { "@type": "Answer", text: faq.answer },
    })),
  };
}

/** The product. Offers come from the backend's plans; no ratings or review counts. */
export function softwareJsonLd(url: string, description: string, plans: Plans | null) {
  const offers: Record<string, unknown>[] = [{ "@type": "Offer", name: "Free", price: "0", priceCurrency: "USD" }];
  const price = plans?.pro.price;
  // Pro is offered only while it can be bought (billing can be switched off).
  if (price && plans?.checkout_available) {
    offers.push({
      "@type": "Offer",
      name: "Pro",
      price: (price.amount / 100).toFixed(2),
      priceCurrency: price.currency.toUpperCase(),
    });
  }
  return {
    "@context": "https://schema.org",
    "@type": "SoftwareApplication",
    name: "Contendo",
    applicationCategory: "BusinessApplication",
    operatingSystem: "Web",
    url,
    description,
    offers,
  };
}

/** The organisation behind the site. `sameAs` lists its official profiles only. */
export function organizationJsonLd({ name, url, logo, email, sameAs }: {
  name: string;
  url: string;
  logo: string;
  email: string;
  sameAs: readonly string[];
}) {
  return {
    "@context": "https://schema.org",
    "@type": "Organization",
    name,
    url,
    logo,
    email,
    ...(sameAs.length ? { sameAs } : {}),
  };
}

/** JSON for a <script type="application/ld+json">, safe inside HTML. */
export function serializeJsonLd(data: unknown): string {
  return JSON.stringify(data).replace(/</g, "\\u003c");
}
