"use client";

import { useCallback, useEffect, useState } from "react";
import RetryNotice from "@/components/RetryNotice";
import { requestErrorMessage } from "@/lib/request-errors";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { formatWhen, statusLabel, type PublishJob } from "@/lib/publishing";

const TONE: Record<string, string> = {
  Published: "text-primary",
  "Not published": "text-error",
  Paused: "text-tertiary",
};

// While a post is on its way, look again so its status settles without a reload.
const REFRESH_MS = 5000;

export default function ScheduledPage() {
  const api = useApi();
  const [jobs, setJobs] = useState<PublishJob[] | null>(null);
  const [error, setError] = useState("");
  const [busy, setBusy] = useState("");

  const load = useCallback(async () => {
    setError("");
    try {
      setJobs(await api.getPublishJobs());
    } catch (e) {
      setError(requestErrorMessage(e, "load your scheduled posts"));
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    load();
  }, [load]);

  const inFlight = (jobs ?? []).some((job) => job.status === "publishing" || (job.status === "scheduled" && !job.scheduled_at));
  useEffect(() => {
    if (!inFlight) return;
    const id = setInterval(load, REFRESH_MS);
    return () => clearInterval(id);
  }, [inFlight, load]);

  async function cancel(job: PublishJob) {
    setBusy(job.id);
    setError("");
    try {
      await api.cancelPublishJob(job.id);
    } catch (e) {
      setError(requestErrorMessage(e, "cancel this post"));
    } finally {
      setBusy("");
      load();
    }
  }

  return (
    <div className="max-w-[44rem] mx-auto">
      <div className="flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <h1 className="font-headline text-[2rem] sm:text-[2.5rem] text-on-surface leading-tight">Scheduled and published</h1>
        <Link href="/settings/accounts" className="text-[0.875rem] text-primary underline underline-offset-4">
          Connected accounts
        </Link>
      </div>

      {error && (
        <div className="mt-6"><RetryNotice message={error} onRetry={load} /></div>
      )}

      {jobs === null && error ? null : jobs === null ? (
        <p className="mt-8 text-[0.9375rem] text-secondary">Loading…</p>
      ) : jobs.length === 0 ? (
        <p className="mt-8 text-[0.9375rem] leading-relaxed text-secondary">
          Nothing here yet. Write a post, then choose Publish to send it now, schedule it, or add it to your queue.
        </p>
      ) : (
        <ul className="mt-8 flex flex-col gap-4">
          {jobs.map((job) => {
            const label = statusLabel(job);
            const when = job.published_at ?? job.scheduled_at;
            return (
              <li key={job.id} className="rounded-lg bg-surface-container-lowest px-4 py-4 sm:px-5">
                <div className="flex flex-wrap items-baseline justify-between gap-x-4 gap-y-1">
                  <p className={`text-[0.9375rem] font-medium ${TONE[label] ?? "text-on-surface"}`}>{label}</p>
                  <p className="text-[0.8125rem] text-secondary">{when ? formatWhen(when) : "As soon as possible"}</p>
                </div>
                <p className="mt-2 text-[0.9375rem] leading-relaxed text-on-surface line-clamp-3 whitespace-pre-line">
                  {job.content}
                </p>
                {job.message && (
                  <p role="status" className="mt-3 text-[0.875rem] leading-relaxed text-error">
                    {job.message}{" "}
                    {job.error_code === "reconnect_required" || job.error_code === "account_removed" ? (
                      <Link href="/settings/accounts" className="underline underline-offset-4">
                        Go to accounts
                      </Link>
                    ) : job.error_code === "payment_required" || job.error_code === "subscription_ended" ? (
                      <Link href="/settings/billing" className="underline underline-offset-4">
                        Go to billing
                      </Link>
                    ) : null}
                  </p>
                )}
                {job.results.some((result) => result.url) && (
                  <p className="mt-3 flex flex-wrap gap-x-4 gap-y-1 text-[0.875rem]">
                    {job.results
                      .filter((result) => result.url)
                      .map((result) => (
                        <a
                          key={`${result.account_id}-${result.url}`}
                          href={result.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="text-primary underline underline-offset-4"
                        >
                          View post
                        </a>
                      ))}
                  </p>
                )}
                {job.status === "scheduled" && (
                  <button
                    type="button"
                    disabled={busy === job.id}
                    onClick={() => cancel(job)}
                    className="mt-3 py-1.5 text-[0.875rem] text-secondary underline underline-offset-4 hover:text-on-surface disabled:opacity-50"
                  >
                    {busy === job.id ? "Cancelling…" : "Cancel"}
                  </button>
                )}
              </li>
            );
          })}
        </ul>
      )}
    </div>
  );
}
