"use client";

import type { Segment } from "@/lib/account";

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
}: {
  onChoose: (segment: Segment) => void;
  onSkip: () => void;
  busy?: boolean;
  error?: string;
}) {
  return (
    <div className="w-full">
      <h1 className="font-headline text-[1.5rem] sm:text-[1.75rem] leading-snug text-on-surface text-center">
        Who are you creating content for?
      </h1>
      <p className="mt-3 text-[0.9375rem] leading-relaxed text-secondary text-center">
        It decides what we ask you next and the kinds of post we suggest.
      </p>

      <div className="mt-8 grid gap-4 sm:grid-cols-2">
        {CHOICES.map((choice) => (
          <button
            key={choice.segment}
            type="button"
            disabled={busy}
            onClick={() => onChoose(choice.segment)}
            className="text-left rounded-lg bg-surface-container-low hover:bg-surface-container-highest px-5 py-5 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
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
        <button
          type="button"
          disabled={busy}
          onClick={onSkip}
          className="text-[0.875rem] text-secondary underline decoration-tertiary-fixed-dim underline-offset-4 hover:text-on-surface disabled:opacity-50"
        >
          Skip for now
        </button>
      </div>
    </div>
  );
}
