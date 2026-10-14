"use client";

import { useEffect, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import type { ClosestSource } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Label, Textarea } from "@/components/ui/field";

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
    <section aria-labelledby="low-coverage-title" className="bg-surface-container-low rounded-2xl p-5 sm:p-8 space-y-5">
      <h2 id="low-coverage-title" className="font-headline italic text-[1.5rem] text-on-surface">
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
        <Button
          onClick={() => {
            onAddSource();
            router.push("/feed-memory");
          }}
        >
          Add a source
        </Button>
        {opinionEnabled && (
          <Button variant="secondary" onClick={onWriteOpinion} loading={busy} className="whitespace-normal text-left">
            Write an opinion post without specifics
          </Button>
        )}
      </div>
      {!opinionEnabled ? (
        <p className="text-sm text-on-surface-variant">
          {HINT_WHEN_DISABLED}
        </p>
      ) : detailsOpen ? (
        <div className="space-y-3">
          <Label htmlFor="low-coverage-details">Your details</Label>
          <Textarea
            id="low-coverage-details"
            ref={detailsRef}
            value={details}
            onChange={(e) => setDetails(e.target.value)}
            rows={4}
            placeholder="What happened, which ones, what you liked…"
            className="resize-y bg-surface-container-lowest"
          />
          <Button
            variant="secondary"
            onClick={() => onWriteWithDetails(details.trim())}
            loading={busy}
            disabled={!details.trim()}
            disabledReason="Add your details to continue"
          >
            Write it from my details
          </Button>
        </div>
      ) : (
        <button
          type="button"
          onClick={() => setDetailsOpen(true)}
          className="block min-h-11 rounded-md text-left text-[0.875rem] text-on-surface-variant underline decoration-outline-variant underline-offset-4 hover:text-on-surface"
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
