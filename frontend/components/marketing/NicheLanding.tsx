import Image from "next/image";
import Link from "next/link";
import type { NicheLandingContent } from "@/content/niches";
import { publishableTestimonials } from "@/content/testimonials";
import { formatPrice, type Plans } from "@/lib/billing";
import { faqJsonLd, softwareJsonLd } from "@/lib/json-ld";
import { costFaq, ctaLabel, startHref } from "@/lib/landing";
import { canonicalUrl } from "@/lib/seo";
import JsonLd from "@/components/marketing/JsonLd";
import NicheLinks from "@/components/marketing/NicheLinks";

// The primary call to action on public pages is terracotta (DESIGN.md note).
const CTA =
  "inline-block rounded-md bg-tertiary hover:bg-tertiary-dim text-on-tertiary px-7 py-3.5 text-[1rem] font-medium transition-colors";
const SECTION = "mx-auto w-full max-w-[68rem] px-4 sm:px-8";

/** A niche landing page, rendered on the server from one content file and the backend's plans. */
export default function NicheLanding({ content, plans }: { content: NicheLandingContent; plans: Plans | null }) {
  const cost = costFaq(plans);
  // One list feeds both the visible FAQ and its structured data.
  const faqs = cost ? [...content.faqs, cost] : content.faqs;
  const testimonials = publishableTestimonials(content.nicheKey);
  const href = startHref(content.nicheKey);
  const cta = ctaLabel(plans);
  const price = plans?.pro.price ?? null;

  return (
    <div className="min-h-screen bg-background text-on-surface font-sans">
      <JsonLd data={softwareJsonLd(canonicalUrl(`/${content.slug}`), content.metaDescription, plans)} />
      <JsonLd data={faqJsonLd(faqs)} />

      <header className={`${SECTION} py-5 flex items-center justify-between`}>
        <Link href="/" className="font-headline italic text-[1.25rem] text-on-surface">
          Contendo
        </Link>
        <Link href="/sign-in" className="text-[0.9375rem] text-secondary hover:text-on-surface py-2">
          Sign in
        </Link>
      </header>

      <main>
        <section className={`${SECTION} pt-10 pb-16 sm:pt-16 sm:pb-24`}>
          <h1 className="font-headline text-[2rem] leading-[1.15] sm:text-[3rem] sm:leading-[1.1] max-w-[46rem]">
            {content.headline}
          </h1>
          <p className="mt-6 max-w-[40rem] text-[1.0625rem] leading-relaxed text-secondary">{content.subhead}</p>
          <div className="mt-8">
            <Link href={href} className={CTA}>
              {cta}
            </Link>
            <p className="mt-3 text-[0.875rem] text-secondary">No card needed to start.</p>
          </div>
        </section>

        <section aria-labelledby="how-it-works" className="bg-surface-container-low py-16 sm:py-20">
          <div className={SECTION}>
            <h2 id="how-it-works" className="font-headline text-[1.625rem] sm:text-[2rem]">
              How it works
            </h2>
            <ol className="mt-10 grid gap-10 lg:grid-cols-3">
              {content.steps.map((step, index) => (
                <li key={step.title}>
                  {step.image && (
                    <Image
                      src={step.image.src}
                      alt={step.image.alt}
                      width={step.image.width}
                      height={step.image.height}
                      sizes="(min-width: 1024px) 22rem, 100vw"
                      className="mb-5 h-auto w-full rounded-lg bg-surface-container"
                    />
                  )}
                  <p className="label-caps text-tertiary">Step {index + 1}</p>
                  <h3 className="mt-2 font-headline text-[1.25rem]">{step.title}</h3>
                  <p className="mt-3 text-[1rem] leading-relaxed text-secondary">{step.body}</p>
                </li>
              ))}
            </ol>
          </div>
        </section>

        {content.examples.length > 0 && (
          <section aria-labelledby="examples" className={`${SECTION} py-16 sm:py-20`}>
            <h2 id="examples" className="font-headline text-[1.625rem] sm:text-[2rem]">
              Example posts
            </h2>
            <p className="mt-3 max-w-[40rem] text-[1rem] leading-relaxed text-secondary">{content.examplesIntro}</p>
            <ul className="mt-10 grid gap-6 md:grid-cols-2">
              {content.examples.map((example) => (
                <li key={example.pillar} className="rounded-lg bg-surface-container-lowest px-5 py-6 sm:px-6">
                  <p className="label-caps text-secondary">Example post · {example.pillar}</p>
                  <p className="mt-4 whitespace-pre-line text-[1rem] leading-relaxed">{example.post}</p>
                </li>
              ))}
            </ul>
          </section>
        )}

        {testimonials.length > 0 && (
          <section aria-labelledby="testimonials" className="bg-surface-container-low py-16 sm:py-20">
            <div className={SECTION}>
              <h2 id="testimonials" className="font-headline text-[1.625rem] sm:text-[2rem]">
                What agents say
              </h2>
              <ul className="mt-10 grid gap-6 md:grid-cols-2">
                {testimonials.map((testimonial) => (
                  <li key={`${testimonial.name}-${testimonial.date}`} className="rounded-lg bg-surface-container-lowest px-5 py-6 sm:px-6">
                    <blockquote className="text-[1.0625rem] leading-relaxed">{testimonial.quote}</blockquote>
                    <p className="mt-4 text-[0.9375rem] text-secondary">
                      {testimonial.name}, {testimonial.role}
                    </p>
                  </li>
                ))}
              </ul>
            </div>
          </section>
        )}

        {plans && (
          <section aria-labelledby="pricing" className={`${SECTION} py-16 sm:py-20`}>
            <h2 id="pricing" className="font-headline text-[1.625rem] sm:text-[2rem]">
              Pricing
            </h2>
            <div className="mt-10 grid gap-6 md:grid-cols-2">
              <div className="rounded-lg bg-surface-container-low px-5 py-7 sm:px-7">
                <h3 className="font-headline text-[1.375rem]">Free</h3>
                <ul className="mt-4 flex flex-col gap-2.5 text-[1rem] leading-relaxed text-secondary">
                  <li>{plans.free.generations_per_month} posts a month, written in your voice</li>
                  <li>Copy them and post them yourself</li>
                  <li>No card needed</li>
                </ul>
              </div>
              <div className="rounded-lg bg-surface-container-lowest px-5 py-7 sm:px-7">
                <h3 className="font-headline text-[1.375rem]">Pro</h3>
                {price && (
                  <p className="mt-2 text-[1.0625rem]">
                    {formatPrice(price)}
                    {price.trial_days > 0 ? `, after a ${price.trial_days}-day free trial` : ""}
                  </p>
                )}
                <ul className="mt-4 flex flex-col gap-2.5 text-[1rem] leading-relaxed text-secondary">
                  <li>{plans.pro.generations_per_month} posts a month</li>
                  <li>Connect up to {plans.pro.max_connected_accounts} social accounts</li>
                  <li>Publish now, schedule, or queue a post a day</li>
                  <li>Cancel any time</li>
                </ul>
              </div>
            </div>
          </section>
        )}

        <section aria-labelledby="faq" className="bg-surface-container-low py-16 sm:py-20">
          <div className={`${SECTION} max-w-[48rem]`}>
            <h2 id="faq" className="font-headline text-[1.625rem] sm:text-[2rem]">
              Questions agents ask
            </h2>
            <dl className="mt-10 flex flex-col gap-9">
              {faqs.map((faq) => (
                <div key={faq.question}>
                  <dt className="font-headline text-[1.1875rem]">{faq.question}</dt>
                  <dd className="mt-3 text-[1rem] leading-relaxed text-secondary">{faq.answer}</dd>
                </div>
              ))}
            </dl>
          </div>
        </section>

        <section className={`${SECTION} py-16 sm:py-24 text-center`}>
          <h2 className="font-headline text-[1.625rem] sm:text-[2rem]">Write your first post today</h2>
          <div className="mt-7">
            <Link href={href} className={CTA}>
              {cta}
            </Link>
          </div>
        </section>
      </main>

      <footer className="bg-surface-container-low py-12">
        <div className={`${SECTION} flex flex-col gap-10 sm:flex-row sm:justify-between`}>
          <div>
            <Link href="/" className="font-headline italic text-[1.1rem]">
              Contendo
            </Link>
            <p className="mt-2 text-[0.875rem] text-secondary">Your posts, written in your voice and published for you.</p>
          </div>
          <NicheLinks />
        </div>
      </footer>
    </div>
  );
}
