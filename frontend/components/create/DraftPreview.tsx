"use client";

/**
 * The first draft as it is written (POST /generate/stream). It is a preview:
 * not editable, and replaced by the checked post, which may differ (spacing
 * and punctuation are normalised, and a post over the length limit is
 * shortened), or by a message when the run makes no post.
 */
export default function DraftPreview({ text }: { text: string }) {
  return (
    <div role="status" aria-live="off" aria-busy="true" className="mx-auto w-full max-w-2xl py-12">
      <p className="font-headline text-[1.25rem] text-on-surface">Writing your post</p>
      <p className="mt-1 text-[0.8125rem] text-on-surface-variant">
        A preview. It opens for editing once it&apos;s checked against your sources.
      </p>
      <div className="mt-6 rounded-xl bg-surface-container-low px-6 py-5">
        <p className="text-[15.5px] leading-[1.9] text-on-surface whitespace-pre-wrap">
          {text}
          <span aria-hidden="true" className="ml-0.5 inline-block h-[1em] w-[2px] translate-y-[2px] bg-primary animate-pulse motion-reduce:animate-none" />
        </p>
      </div>
    </div>
  );
}
