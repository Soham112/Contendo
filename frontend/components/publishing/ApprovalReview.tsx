"use client";

import { useEffect, useState } from "react";
import { PaywallError } from "@/lib/commerce-api";
import type { Paywall } from "@/lib/billing";
import { useApi } from "@/lib/api";
import { allFlagsAccepted, type ContentReview, type MediaRef } from "@/lib/publishing";
import { Button } from "@/components/ui/button";

export default function ApprovalReview({ content, postId, traceId, media, onApproved, onPaywall }: {
  content: string; postId: number | null; traceId?: string | null; media: MediaRef[];
  onApproved: (review: ContentReview) => void;
  onPaywall?: (paywall: Paywall) => void;
}) {
  const api = useApi();
  const [review, setReview] = useState<ContentReview | null>(null);
  const [accepted, setAccepted] = useState<string[]>([]);
  const [read, setRead] = useState(false);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  function fail(error: unknown) {
    if (error instanceof PaywallError && onPaywall) onPaywall(error.paywall);
    else setError(error instanceof Error ? error.message : "Couldn't prepare this text for approval. Try again.");
  }
  useEffect(() => {
    let active = true;
    api.reviewPublishText({ content, post_id: postId, trace_id: traceId, media })
      .then((value) => { if (active) setReview(value); })
      .catch((e: Error) => { if (active) fail(e); });
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
      fail(e);
    } finally { setBusy(false); }
  }

  const flagsDone = !!review && allFlagsAccepted(review, accepted);
  const reason = !read ? "Confirm you've read the text" : !flagsDone ? "Accept or fix each flagged detail" : undefined;
  return <section aria-label="Review and approve final text" className="mt-6 rounded-2xl bg-surface-container-lowest p-5">
    <h4 className="font-headline text-lg">Read the final text</h4>
    <p className="mt-3 whitespace-pre-wrap text-base leading-relaxed">{content}</p>
    {!review && !error && <p role="status" className="mt-4 text-sm text-on-surface-variant">Preparing your text for approval…</p>}
    {review && <>
      {review.flags.length > 0 && <div className="mt-5">
        <p className="text-sm text-tertiary">Edit the post to correct these details, or accept each one after checking it yourself.</p>
        {review.flags.map((flag) => <label key={flag.id} className="mt-3 flex min-h-11 cursor-pointer items-start gap-3 rounded-lg py-2 text-sm">
          <input type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-primary" checked={accepted.includes(flag.id)} disabled={!!review.approved_at}
            onChange={(e) => setAccepted((prev) => e.target.checked ? [...prev, flag.id] : prev.filter((id) => id !== flag.id))} />
          <span>{flag.text && <strong className="block">{flag.text}</strong>}{flag.reason}
            <span className="mt-1 block text-on-surface-variant">I have checked this and it is correct.</span></span>
        </label>)}
      </div>}
      <label className="mt-4 flex min-h-11 cursor-pointer items-start gap-3 py-2 text-sm">
        <input type="checkbox" className="mt-0.5 h-5 w-5 shrink-0 accent-primary" checked={read} disabled={!!review.approved_at} onChange={(e) => setRead(e.target.checked)} />
        I have read and approve this exact text for publishing.
      </label>
      <Button className="mt-4" onClick={approve} loading={busy}
        disabled={!!review.approved_at || !read || !flagsDone}
        disabledReason={review.approved_at ? undefined : reason}>
        {review.approved_at ? "Text approved" : "Approve this text"}
      </Button>
    </>}
    {error && <p role="alert" className="mt-4 text-sm text-error">{error}</p>}
  </section>;
}
