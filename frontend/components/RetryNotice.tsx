"use client";

import { ErrorState } from "@/components/ui/states";

/** A failed load, in plain words, with a "Try again" button. */
export default function RetryNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <ErrorState message={message} onRetry={onRetry} />;
}
