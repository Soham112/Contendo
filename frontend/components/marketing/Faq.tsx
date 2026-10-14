import { faqJsonLd, type Faq as FaqItem } from "@/lib/json-ld";
import JsonLd from "@/components/marketing/JsonLd";

/**
 * A visible FAQ section and its FAQPage structured data, both built from the
 * one `faqs` list, so what search engines read is always what the page shows.
 */
export default function Faq({
  id,
  heading,
  faqs,
  className = "",
}: {
  /** The heading's id, for aria-labelledby and in-page links. */
  id: string;
  heading: string;
  faqs: FaqItem[];
  /** Classes for the outer section, e.g. its background. */
  className?: string;
}) {
  if (faqs.length === 0) return null;
  return (
    <section aria-labelledby={id} className={`py-16 sm:py-20 ${className}`}>
      <JsonLd data={faqJsonLd(faqs)} />
      <div className="mx-auto w-full max-w-[48rem] px-4 sm:px-8">
        <h2 id={id} className="font-headline text-[1.625rem] sm:text-[2rem] text-on-surface">
          {heading}
        </h2>
        <dl className="mt-10 flex flex-col gap-9">
          {faqs.map((faq) => (
            <div key={faq.question}>
              <dt className="font-headline text-[1.1875rem] text-on-surface">{faq.question}</dt>
              <dd className="mt-3 text-[1rem] leading-relaxed text-secondary">{faq.answer}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
