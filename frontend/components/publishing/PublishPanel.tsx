"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { PaywallError, PublishProblems } from "@/lib/commerce-api";
import type { Paywall } from "@/lib/billing";
import {
  browserTimeZone, fit, formatWhen, localInputToIso,
  type ConnectedAccount, type MediaRef, type PlatformRules, type PublishWhen,
} from "@/lib/publishing";
import ApprovalReview from "./ApprovalReview";
import type { ContentReview } from "@/lib/publishing";
import UpgradeScreen from "@/components/billing/UpgradeScreen";

/**
 * Publish now, schedule, or add to the queue, for one finished post. Every
 * choice creates a job on the backend, which validates it again and sends it
 * from a worker; this panel only previews the platform rules.
 */
export default function PublishPanel({ content, postId, traceId }: { content: string; postId: number | null; traceId?: string | null }) {
  const api = useApi();
  const [approved, setApproved] = useState<ContentReview | null>(null);
  const [open, setOpen] = useState(false);
  const [accounts, setAccounts] = useState<ConnectedAccount[] | null>(null);
  const [rules, setRules] = useState<Record<string, PlatformRules>>({});
  const [chosen, setChosen] = useState<string[]>([]);
  const [media, setMedia] = useState<MediaRef[]>([]);
  const approvalId = approved?.post_id === postId && approved.content === content && JSON.stringify(approved.media) === JSON.stringify(media) ? approved.id : null;
  const [when, setWhen] = useState<PublishWhen>("now");
  const [scheduleValue, setScheduleValue] = useState("");
  const [busy, setBusy] = useState("");
  const [problems, setProblems] = useState<string[]>([]);
  const [done, setDone] = useState("");
  const [paywall, setPaywall] = useState<Paywall | null>(null);

  useEffect(() => {
    if (!open || accounts !== null) return;
    Promise.all([api.getConnectedAccounts(), api.getPlatformRules()])
      .then(([loadedAccounts, loadedRules]) => {
        setAccounts(loadedAccounts);
        setRules(Object.fromEntries(loadedRules.map((r) => [r.platform, r])));
      })
      .catch((e: Error) => {
        setAccounts([]);
        setProblems([e.message]);
      });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open]);

  function fail(e: unknown) {
    if (e instanceof PaywallError) setPaywall(e.paywall);
    else if (e instanceof PublishProblems) setProblems(e.problems);
    else setProblems([e instanceof Error ? e.message : "Something went wrong. Please try again."]);
  }

  async function addMedia(file: File | undefined) {
    if (!file) return;
    setBusy("media");
    setProblems([]);
    try {
      const uploaded = await api.uploadMedia(file);
      setMedia((prev) => [...prev, uploaded]);
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }

  async function submit() {
    setProblems([]);
    setDone("");
    if (!approvalId) { setProblems(["Read and approve the final text first."]); return; }
    const scheduledAt = when === "schedule" ? localInputToIso(scheduleValue) : null;
    if (when === "schedule" && !scheduledAt) {
      setProblems(["Choose a date and time."]);
      return;
    }
    setBusy("submit");
    try {
      const job = await api.createPublishJob({
        approval_id: approvalId, content, post_id: postId, account_ids: chosen, media, when,
        scheduled_at: scheduledAt, timezone: browserTimeZone(),
      });
      setDone(job.scheduled_at ? `Scheduled for ${formatWhen(job.scheduled_at)}.` : "On its way. It will be published in a moment.");
    } catch (e) {
      fail(e);
    } finally {
      setBusy("");
    }
  }

  if (!open) {
    return (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className="btn-primary text-white rounded-md px-5 py-2.5 text-[0.875rem] font-medium"
      >
        Publish
      </button>
    );
  }

  const usable = (accounts ?? []).filter((a) => a.status === "connected");
  const WHEN: { value: PublishWhen; label: string; action: string }[] = [
    { value: "now", label: "Publish now", action: "Publish now" },
    { value: "schedule", label: "Schedule", action: "Schedule" },
    { value: "queue", label: "Add to queue", action: "Add to queue" },
  ];

  return (
    <section aria-label="Publish this post" className="w-full rounded-lg bg-surface-container-low px-4 py-5 sm:px-6">
      <div className="flex items-center justify-between gap-4">
        <h3 className="font-headline text-[1.125rem] text-on-surface">Publish this post</h3>
        <button type="button" onClick={() => setOpen(false)} className="text-[0.875rem] text-secondary hover:text-on-surface py-1">
          Close
        </button>
      </div>

      {accounts === null ? (
        <p className="mt-4 text-[0.9375rem] text-secondary">Loading your accounts…</p>
      ) : (
        <>
          <fieldset className="mt-4">
            <legend className="label-caps text-secondary">Where</legend>
            {usable.length === 0 ? (
              <p className="mt-2 text-[0.9375rem] text-secondary">
                No accounts connected yet.{" "}
                <Link href="/settings/accounts" className="text-primary underline underline-offset-4">
                  Connect an account
                </Link>
              </p>
            ) : (
              <ul className="mt-2 flex flex-col gap-2">
                {usable.map((account) => {
                  const rule = rules[account.platform];
                  const preview = rule ? fit(rule, content, media) : null;
                  const selected = chosen.includes(account.id);
                  return (
                    <li key={account.id}>
                      <label className="flex items-start gap-3 rounded-lg bg-surface-container-lowest px-3 py-3 cursor-pointer">
                        <input
                          type="checkbox"
                          className="mt-1 accent-primary"
                          checked={selected}
                          onChange={() =>
                            setChosen((prev) => (selected ? prev.filter((id) => id !== account.id) : [...prev, account.id]))
                          }
                        />
                        <span className="min-w-0">
                          <span className="block text-[0.9375rem] text-on-surface truncate">
                            {account.label}
                            {account.display_name ? ` · ${account.display_name}` : ""}
                          </span>
                          {preview && rule && (
                            <span
                              className={`block text-[0.8125rem] ${preview.problems.length ? "text-error" : "text-secondary"}`}
                            >
                              {preview.count.toLocaleString("en-US")} of {rule.max_characters.toLocaleString("en-US")} characters
                              {preview.problems.length ? ` · ${preview.problems.join(" · ")}` : ""}
                            </span>
                          )}
                        </span>
                      </label>
                    </li>
                  );
                })}
              </ul>
            )}
            {(accounts ?? []).some((a) => a.status === "needs_reconnect") && (
              <p className="mt-2 text-[0.8125rem] text-error">
                Some accounts need reconnecting.{" "}
                <Link href="/settings/accounts" className="underline underline-offset-4">
                  Reconnect
                </Link>
              </p>
            )}
          </fieldset>

          <div className="mt-5">
            <p className="label-caps text-secondary">Image or video (optional)</p>
            <input
              type="file"
              accept="image/*,video/*"
              aria-label="Add an image or video"
              disabled={!!busy}
              onChange={(e) => {
                addMedia(e.target.files?.[0]);
                e.target.value = "";
              }}
              className="mt-2 block w-full text-[0.875rem] text-secondary"
            />
            {busy === "media" && <p className="mt-1 text-[0.8125rem] text-secondary">Uploading…</p>}
            {media.length > 0 && (
              <p className="mt-1 text-[0.8125rem] text-secondary">
                {media.length} file{media.length === 1 ? "" : "s"} attached.{" "}
                <button type="button" onClick={() => setMedia([])} className="underline underline-offset-4">
                  Remove
                </button>
              </p>
            )}
          </div>

          <fieldset className="mt-5">
            <legend className="label-caps text-secondary">When</legend>
            <div className="mt-2 flex flex-wrap gap-2">
              {WHEN.map((option) => (
                <button
                  key={option.value}
                  type="button"
                  aria-pressed={when === option.value}
                  onClick={() => setWhen(option.value)}
                  className={`rounded-full px-4 py-2 text-[0.875rem] transition-colors ${
                    when === option.value
                      ? "bg-primary-container text-on-primary-fixed outline outline-1 outline-primary"
                      : "bg-surface-container-lowest text-on-surface hover:bg-surface-container-highest"
                  }`}
                >
                  {option.label}
                </button>
              ))}
            </div>
            {when === "schedule" && (
              <div className="mt-3">
                <input
                  type="datetime-local"
                  aria-label="Date and time"
                  value={scheduleValue}
                  onChange={(e) => setScheduleValue(e.target.value)}
                  className="input-editorial w-full sm:w-auto px-3 py-2.5 text-[1rem] text-on-surface"
                />
                <p className="mt-1 text-[0.8125rem] text-secondary">Your time zone: {browserTimeZone()}</p>
              </div>
            )}
            {when === "queue" && (
              <p className="mt-2 text-[0.8125rem] text-secondary">
                Goes out at 9:00 AM your time on the next day with nothing scheduled.
              </p>
            )}
          </fieldset>

          {problems.length > 0 && (
            <ul role="alert" className="mt-4 flex flex-col gap-1 text-[0.875rem] text-error">
              {problems.map((problem) => (
                <li key={problem}>{problem}</li>
              ))}
            </ul>
          )}
          {done && (
            <p role="status" className="mt-4 text-[0.9375rem] text-primary">
              {done}{" "}
              <Link href="/scheduled" className="underline underline-offset-4">
                See all posts
              </Link>
            </p>
          )}

          <ApprovalReview key={JSON.stringify([content, postId, traceId, media])}
            content={content} postId={postId} traceId={traceId} media={media} onApproved={setApproved} onPaywall={setPaywall} />
          <button
            type="button"
            disabled={!!busy || chosen.length === 0 || !approvalId}
            onClick={submit}
            className="mt-5 btn-primary text-white rounded-md px-6 py-3 text-[0.9375rem] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
          >
            {busy === "submit" ? "Saving…" : WHEN.find((option) => option.value === when)?.action}
          </button>
        </>
      )}

      {paywall && <UpgradeScreen code={paywall.code} message={paywall.message} onClose={() => setPaywall(null)} />}
    </section>
  );
}
