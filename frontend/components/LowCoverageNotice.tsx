"use client";

import { useRouter } from "next/navigation";
import type { ClosestSource } from "@/lib/api";

/** Shown instead of a post when /generate returns status "low_coverage". */
export function LowCoverageNotice({
  sources,
  busy,
  onAddSource,
  onWriteOpinion,
}: {
  sources: ClosestSource[];
  busy: boolean;
  onAddSource: () => void;
  onWriteOpinion: () => void;
}) {
  const router = useRouter();

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
        <button
          onClick={onWriteOpinion}
          disabled={busy}
          className="rounded-xl text-[13px] font-semibold py-3 px-6 bg-surface-container text-on-surface hover:bg-surface-container-high disabled:opacity-50"
        >
          Write an opinion post without specifics
        </button>
      </div>
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
