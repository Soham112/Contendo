"use client";

export default function RetryNotice({ message, onRetry }: { message: string; onRetry: () => void }) {
  return <div role="alert" className="rounded-lg bg-surface-container-low p-6 text-on-surface">
    <p className="text-[0.9375rem] leading-relaxed">{message}</p>
    <button type="button" onClick={onRetry} className="btn-primary mt-4 rounded-md px-5 py-2.5 text-white">Try again</button>
  </div>;
}
