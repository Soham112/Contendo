"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import type { Segment } from "@/lib/account";
import SegmentQuestion from "@/components/onboarding/SegmentQuestion";

/**
 * The segment question for someone already using the app. The backend decides
 * whether it is due (account.ask_segment, passed in by AppShell); skipping
 * records that there, so the question does not come back on every page or
 * every device.
 */
export default function SegmentPrompt({ due }: { due: boolean }) {
  const api = useApi();
  const router = useRouter();
  const [dismissed, setDismissed] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const open = due && !dismissed;
  const setOpen = (value: boolean) => setDismissed(!value);

  async function finish(action: () => Promise<unknown>) {
    setBusy(true);
    setError("");
    try {
      await action();
      setOpen(false);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setBusy(false);
    }
  }

  function choose(segment: Segment) {
    if (segment === "business") {
      setOpen(false);
      router.push("/get-started?segment=business");
      return;
    }
    finish(() => api.saveSegment({ segment }));
  }

  if (!open) return null;

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-label="Who are you creating content for?"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: "rgba(47, 51, 51, 0.45)" }}
    >
      <div className="w-full max-w-[34rem] max-h-[90vh] overflow-y-auto bg-surface-container-lowest rounded-2xl shadow-float px-5 py-8 sm:px-10 sm:py-10">
        <SegmentQuestion onChoose={choose} onSkip={() => finish(() => api.skipSegment())} busy={busy} error={error} />
      </div>
    </div>
  );
}
