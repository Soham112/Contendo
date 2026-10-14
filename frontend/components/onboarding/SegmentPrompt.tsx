"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import type { Segment } from "@/lib/account";
import SegmentQuestion from "@/components/onboarding/SegmentQuestion";
import { Dialog } from "@/components/ui/dialog";

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

  return (
    <Dialog
      open={open}
      // It must be answered or skipped with its own buttons.
      onOpenChange={() => {}}
      hideClose
      title="Who are you creating content for?"
      description="It decides what we ask you next and the kinds of post we suggest."
      className="max-w-[34rem]"
    >
      <SegmentQuestion onChoose={choose} onSkip={() => finish(() => api.skipSegment())} busy={busy} error={error} showHeading={false} />
    </Dialog>
  );
}
