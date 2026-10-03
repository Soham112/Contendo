"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ClosestSource } from "@/lib/api";

const HINT_WHEN_DISABLED =
  "Or paste your own notes on this topic as a source, then generate again.";

/** Shown instead of a post when /generate returns status "low_coverage". */
export function LowCoverageNotice({
  sources,
  busy,
  opinionEnabled,
  onAddSource,
  onWriteOpinion,
  onWriteWithDetails,
}: {
  sources: ClosestSource[];
  busy: boolean;
  /** Backend flag NO_SPECIFICS_MODE_ENABLED: offer the opinion post and the details box. */
  opinionEnabled: boolean;
  onAddSource: () => void;
  onWriteOpinion: () => void;
  /** Generate from the user's own details only (sent as context, no-specifics mode). */
  onWriteWithDetails: (details: string) => void;
}) {
  const router = useRouter();
  const [detailsOpen, setDetailsOpen] = useState(false);
  const [details, setDetails] = useState("");
  const detailsRef = useRef<HTMLTextAreaElement>(null);

  useEffect(() => {
    if (detailsOpen) detailsRef.current?.focus();
  }, [detailsOpen]);

  return (
    <section className="bg-surface-container-low rounded-2xl p-8 space-y-5">
      <h2 className="font-headline italic text-2xl text-on-surface">
        Your memory doesn&apos;t cover this topic yet
      </h2>
      {sources.length > 0 && (
        <div className="space-y-3">
          <p className="text-sm text-on-surface-variant">Closest sources found:</p>
          <ul className="space-y-2">
            {sources.map((s, i) => (
              <li key={i} className="bg-surface-container-lowest rounded-xl p-4">
                <p className="text-sm font-semibold text-on-surface">{s.title}</p>
                <p className="text-sm text-on-surface-variant line-clamp-2">{s.preview}</p>
              </li>
            ))}
          </ul>
        </div>
      )}
      <div className="flex flex-wrap gap-3">
        <button
          onClick={() => {
            onAddSource();
            router.push("/feed-memory");
          }}
          className="btn-primary text-white rounded-xl font-bold tracking-widest uppercase text-[13px] py-3 px-6"
        >
          Add a source
        </button>
        {opinionEnabled && (
        <button
          onClick={onWriteOpinion}
          disabled={busy}
          className="rounded-xl text-[13px] font-semibold py-3 px-6 bg-surface-container text-on-surface hover:bg-surface-container-high disabled:opacity-50"
        >
          Write an opinion post without specifics
        </button>
        )}
      </div>
      {!opinionEnabled ? (
        <p className="text-sm text-on-surface-variant">
          {HINT_WHEN_DISABLED}
        </p>
      ) : detailsOpen ? (
        <div className="space-y-3">
          <textarea
            ref={detailsRef}
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            rows={4}
            placeholder="What happened, which ones, what you liked…"
            className="w-full rounded-xl bg-surface-container-lowest p-4 text-sm text-on-surface placeholder:text-on-surface-variant/60 outline-none resize-y"
          />
          <button
            onClick={() => onWriteWithDetails(details.trim())}
            disabled={busy || !details.trim()}
            className="rounded-xl text-[13px] font-semibold py-3 px-6 bg-surface-container text-on-surface hover:bg-surface-container-high disabled:opacity-50"
          >
            Write it from my details
          </button>
        </div>
      ) : (
        <button
          onClick={() => setDetailsOpen(true)}
          className="block text-left text-sm text-on-surface-variant hover:text-on-surface"
        >
          Or add details in the context box (what happened, which ones, what you liked), and we&apos;ll use only what you write.
        </button>
      )}
    </section>
  );
}

/** Small label above a post that was generated in no-specifics mode. */
export function OpinionPostLabel() {
  return (
    <p className="text-[12px] tracking-wide text-on-surface-variant mb-4">
      Opinion post · no specific facts from your memory
    </p>
  );
}
