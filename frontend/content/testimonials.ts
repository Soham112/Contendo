// Testimonials shown on the landing pages.
//
// Only real ones, from real customers who have agreed in writing to be quoted.
// Add an entry only when you hold that agreement, and set permissionConfirmed
// to true yourself: nothing else does. An entry without it is never rendered,
// and with no publishable entries the section does not appear at all.
//
// Never add a placeholder, a paraphrase, a rating, a review count, a user
// count or a "trusted by" logo here.

export interface Testimonial {
  name: string;
  /** e.g. "Real estate agent, Portland". */
  role: string;
  quote: string;
  /** True only once the person has agreed to this quote being published. */
  permissionConfirmed: boolean;
  /** When they agreed, as YYYY-MM-DD. */
  date: string;
  /** Limit it to one niche page (a nicheKey); omit to allow it on every page. */
  nicheKey?: string;
}

export const TESTIMONIALS: Testimonial[] = [];

/** The testimonials that may be shown on a niche's page. */
export function publishableTestimonials(nicheKey: string, all: Testimonial[] = TESTIMONIALS): Testimonial[] {
  return all.filter(
    (t) =>
      t.permissionConfirmed === true &&
      t.name.trim() !== "" &&
      t.quote.trim() !== "" &&
      (!t.nicheKey || t.nicheKey === nicheKey)
  );
}
