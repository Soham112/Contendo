"use client";

import { Suspense, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { useApi } from "@/lib/api";
import { formatDay, formatPrice, quotaLine, type Plans } from "@/lib/billing";
import { useEntitlements } from "@/hooks/useEntitlements";

// After Checkout, Stripe's webhook reaches the backend a moment later. The page
// re-reads the plan a few times; it never marks the user as Pro itself.
const RECHECK_MS = 2000;
const RECHECKS = 8;

function Billing() {
  const api = useApi();
  const searchParams = useSearchParams();
  const checkout = searchParams.get("checkout");
  const { entitlements, refresh } = useEntitlements();
  const [plans, setPlans] = useState<Plans | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [rechecks, setRechecks] = useState(0);

  useEffect(() => {
    api.getPlans().then(setPlans).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const waiting = checkout === "success" && entitlements?.plan === "free" && rechecks < RECHECKS;
  useEffect(() => {
    if (!waiting) return;
    const id = setTimeout(() => {
      setRechecks((n) => n + 1);
      refresh();
    }, RECHECK_MS);
    return () => clearTimeout(id);
  }, [waiting, rechecks, refresh]);

  async function go(action: () => Promise<{ url: string }>) {
    setBusy(true);
    setError("");
    try {
      window.location.assign((await action()).url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  if (!entitlements) return <p className="text-secondary text-[0.9375rem]">Loading…</p>;

  const pro = entitlements.plan === "pro";
  const price = plans?.pro.price ?? null;

  return (
    <div className="flex flex-col gap-6">
      {checkout === "success" && (
        <p role="status" className="rounded-lg bg-primary-container text-on-primary-fixed px-4 py-3 text-[0.9375rem]">
          {pro
            ? "You're on Pro. Connect an account to start publishing."
            : waiting
              ? "Thanks. We're confirming your subscription with Stripe…"
              : "We haven't heard back from Stripe yet. Reload this page in a minute; you won't be charged twice."}
        </p>
      )}
      {checkout === "cancelled" && (
        <p role="status" className="rounded-lg bg-surface-container-low px-4 py-3 text-[0.9375rem] text-secondary">
          Checkout was cancelled. Nothing was charged.
        </p>
      )}
      {entitlements.publishing_paused && (
        <p role="alert" className="rounded-lg bg-tertiary-container text-on-tertiary-container px-4 py-3 text-[0.9375rem]">
          Your last payment didn&apos;t go through, so publishing is paused. Your posts, scheduled posts and connected
          accounts are safe. Update your payment method and publishing carries on.
        </p>
      )}

      <section className="rounded-lg bg-surface-container-lowest px-5 py-6 sm:px-7">
        <p className="label-caps text-secondary">Your plan</p>
        <p className="mt-2 font-headline text-[1.5rem] text-on-surface">{pro ? "Pro" : "Free"}</p>
        <p className="mt-2 text-[0.9375rem] text-secondary">{quotaLine(entitlements)}</p>
        {entitlements.trial_end && (
          <p className="mt-2 text-[0.9375rem] text-on-surface">
            Your free trial ends on {formatDay(entitlements.trial_end)}
            {price ? `, then ${formatPrice(price)}` : ""}.
          </p>
        )}
        {pro && !entitlements.trial_end && entitlements.current_period_end && (
          <p className="mt-2 text-[0.9375rem] text-on-surface">
            {entitlements.cancel_at_period_end ? "Your plan ends on " : "Renews on "}
            {formatDay(entitlements.current_period_end)}.
          </p>
        )}

        {error && (
          <p role="alert" className="mt-4 text-[0.875rem] text-error">
            {error}
          </p>
        )}

        <div className="mt-6">
          {pro ? (
            <button
              type="button"
              disabled={busy}
              onClick={() => go(api.openBillingPortal)}
              className="btn-primary text-white rounded-md px-5 py-3 text-[0.9375rem] font-medium disabled:opacity-50"
            >
              {busy ? "One moment…" : "Manage billing"}
            </button>
          ) : (
            <button
              type="button"
              disabled={busy}
              onClick={() => go(api.startCheckout)}
              className="rounded-md bg-tertiary hover:bg-tertiary-dim text-on-tertiary px-5 py-3 text-[0.9375rem] font-medium transition-colors disabled:opacity-50"
            >
              {busy
                ? "One moment…"
                : price && price.trial_days > 0
                  ? `Start ${price.trial_days}-day free trial`
                  : "Upgrade to Pro"}
            </button>
          )}
        </div>
      </section>

      {!pro && plans && (
        <section className="rounded-lg bg-surface-container-low px-5 py-6 sm:px-7">
          <p className="label-caps text-secondary">Pro</p>
          {price && <p className="mt-2 font-headline text-[1.25rem] text-on-surface">{formatPrice(price)}</p>}
          <ul className="mt-4 flex flex-col gap-2.5 text-[0.9375rem] leading-relaxed text-on-surface">
            <li>Connect {plans.pro.max_accounts_per_platform} account per platform.</li>
            <li>Publish now, schedule for later, or add posts to a daily queue.</li>
            <li>{plans.pro.generations_per_month} posts a month.</li>
            <li>Cancel any time from this page.</li>
          </ul>
          <p className="mt-4 text-[0.875rem] text-secondary">
            Free includes {plans.free.generations_per_month} posts a month that you can copy and post yourself.
          </p>
        </section>
      )}
    </div>
  );
}

export default function BillingPage() {
  return (
    <div className="max-w-[40rem] mx-auto">
      <h1 className="font-headline text-[2rem] sm:text-[2.5rem] text-on-surface leading-tight">Plan and billing</h1>
      <div className="mt-8">
        <Suspense fallback={<p className="text-secondary text-[0.9375rem]">Loading…</p>}>
          <Billing />
        </Suspense>
      </div>
    </div>
  );
}
