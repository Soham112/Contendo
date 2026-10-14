"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { allFlagsAccepted, type ContentReview, type MediaRef } from "@/lib/publishing";

export default function ApprovalReview({ content, postId, traceId, media, onApproved }: {
  content: string; postId: number | null; traceId?: string | null; media: MediaRef[];
  onApproved: (review: ContentReview) => void;
}) {
  const api = useApi();
  const [review, setReview] = useState<ContentReview | null>(null);
  const [accepted, setAccepted] = useState<string[]>([]);
  const [read, setRead] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  useEffect(() => {
    let active = true;
    api.reviewPublishText({ content, post_id: postId, trace_id: traceId, media })
      .then((value) => { if (active) setReview(value); })
      .catch((e: Error) => { if (active) setError(e.message); });
    return () => { active = false; };
    // The parent keys this component by the exact text, trace, post and media.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  async function approve() {
    if (!review || !read || !allFlagsAccepted(review, accepted)) return;
    setBusy(true);
    setError("");
    try {
      const approved = await api.approvePublishText(review.id, content, accepted);
      setReview(approved);
      onApproved(approved);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Couldn't approve this text. Try again.");
    } finally { setBusy(false); }
  }

  return <section aria-label="Review and approve final text" className="mt-6 rounded-lg bg-surface-container-lowest p-5">
    <h4 className="font-headline text-lg">Read the final text</h4>
    <p className="mt-3 whitespace-pre-wrap text-base leading-relaxed">{content}</p>
    {!review && !error && <p role="status" className="mt-4 text-sm text-secondary">Checking claims against your sources…</p>}
    {review && <>
      {review.flags.length > 0 && <div className="mt-5">
        <p className="text-sm text-tertiary">Edit the post to correct these details, or accept each claim after checking it yourself.</p>
        {review.flags.map((flag) => <label key={flag.id} className="mt-4 flex items-start gap-3 text-sm">
          <input type="checkbox" checked={accepted.includes(flag.id)} disabled={!!review.approved_at}
            onChange={(e) => setAccepted((prev) => e.target.checked ? [...prev, flag.id] : prev.filter((id) => id !== flag.id))} />
          <span>{flag.text && <strong className="block">{flag.text}</strong>}{flag.reason}
            <span className="mt-1 block">I have checked and accept this flagged claim.</span></span>
        </label>)}
      </div>}
      <label className="mt-5 flex items-start gap-3 text-sm">
        <input type="checkbox" checked={read} disabled={!!review.approved_at} onChange={(e) => setRead(e.target.checked)} />
        I have read and approve this exact text for publishing.
      </label>
      <button type="button" onClick={approve}
        disabled={busy || !!review.approved_at || !read || !allFlagsAccepted(review, accepted)}
        className="mt-4 btn-primary rounded-md px-5 py-2.5 text-sm text-white disabled:opacity-50">
        {review.approved_at ? "Text approved" : busy ? "Approving…" : "Approve this text"}
      </button>
    </>}
    {error && <p role="alert" className="mt-4 text-sm text-error">{error}</p>}
  </section>;
}
