"use client";

import type { Segment } from "@/lib/account";
import { Button } from "@/components/ui/button";

const CHOICES: { segment: Segment; title: string; detail: string }[] = [
  {
    segment: "business",
    title: "My business",
    detail: "Posts that bring in customers: what you offer, your news, your advice.",
  },
  {
    segment: "individual",
    title: "Myself",
    detail: "Founder, creator or professional, posting under your own name.",
  },
];

/** The one onboarding question. Used full-page (/get-started) and in the prompt existing users see. */
export default function SegmentQuestion({
  onChoose,
  onSkip,
    busy = false,
  error = "",
  showHeading = true,
}: {
  onChoose: (segment: Segment) => void;
  onSkip: () => void;
  busy?: boolean;
  error?: string;
  /** False inside a dialog that already shows the question as its title. */
  showHeading?: boolean;
}) {
  return (
    <div className="w-full">
      {showHeading && (
        <>
          <h1 className="font-headline text-[1.5rem] sm:text-[1.75rem] leading-snug text-on-surface text-center">
            Who are you creating content for?
          </h1>
          <p className="mt-3 text-[0.9375rem] leading-relaxed text-secondary text-center">
            It decides what we ask you next and the kinds of post we suggest.
          </p>
        </>
      )}

      <div className={`${showHeading ? "mt-8" : ""} grid gap-4 sm:grid-cols-2`}>
        {CHOICES.map((choice) => (
          <button
            key={choice.segment}
            type="button"
            disabled={busy}
            onClick={() => onChoose(choice.segment)}
            className="flex flex-col items-start justify-start text-left rounded-2xl border border-outline-variant bg-surface-container-lowest hover:bg-surface-container-low hover:border-outline px-5 py-5 transition-colors duration-150 ease-out disabled:cursor-wait focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2"
          >
            <span className="block font-headline text-[1.125rem] text-on-surface">{choice.title}</span>
            <span className="mt-2 block text-[0.875rem] leading-relaxed text-secondary">{choice.detail}</span>
          </button>
        ))}
      </div>

      {error && (
        <p role="alert" className="mt-5 text-[0.875rem] text-error text-center">
          {error}
        </p>
      )}

      <div className="mt-7 text-center">
        <Button variant="tertiary" size="sm" disabled={busy} onClick={onSkip}>
          Skip for now
        </Button>
      </div>
    </div>
  );
}
