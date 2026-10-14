"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { PRO_NOT_AVAILABLE, formatPrice, type PaywallCode, type Plans } from "@/lib/billing";

const HEADLINES: Record<PaywallCode, string> = {
  quota_exceeded: "You've used this month's free posts",
  upgrade_required: "Have your posts published for you",
  payment_required: "Your last payment didn't go through",
};

/**
 * Shown when the backend refuses something the plan doesn't include. It only
 * explains and links to Stripe: the plan changes when Stripe tells the backend.
 */
export default function UpgradeScreen({
  code,
  message,
  onClose,
}: {
  code: PaywallCode;
  message: string;
  onClose: () => void;
}) {
  const api = useApi();
  const [plans, setPlans] = useState<Plans | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api.getPlans().then(setPlans).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const paymentFailed = code === "payment_required";
  const price = plans?.pro.price ?? null;
  // Only a known "no": while the plans are loading the button stays, and the server still decides.
  const canBuy = paymentFailed || plans?.checkout_available !== false;

  async function go() {
    setBusy(true);
    setError("");
    try {
      const { url } = paymentFailed ? await api.openBillingPortal() : await api.startCheckout();
      window.location.assign(url);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Something went wrong. Please try again.");
      setBusy(false);
    }
  }

  return (
    <div
      role="dialog"
      aria-modal="true"
      aria-labelledby="upgrade-title"
      className="fixed inset-0 z-50 flex items-center justify-center px-4"
      style={{ background: "rgba(47, 51, 51, 0.45)" }}
    >
      <div className="w-full max-w-[30rem] max-h-[90vh] overflow-y-auto bg-surface-container-lowest rounded-2xl shadow-float px-5 py-8 sm:px-9 sm:py-9">
        <h2 id="upgrade-title" className="font-headline text-[1.5rem] leading-snug text-on-surface">
          {HEADLINES[code]}
        </h2>
        <p className="mt-3 text-[0.9375rem] leading-relaxed text-secondary">{message}</p>

        {!paymentFailed && plans && (
          <>
            <ul className="mt-6 flex flex-col gap-3 text-[0.9375rem] leading-relaxed text-on-surface">
              <li>Connect {plans.pro.max_accounts_per_platform} account per platform.</li>
              <li>Publish now, schedule for later, or add posts to a daily queue.</li>
              <li>{plans.pro.generations_per_month} posts a month, written in your voice.</li>
              <li>You approve every post before it goes out.</li>
            </ul>
            {price && (
              <p className="mt-6 text-[0.9375rem] leading-relaxed text-on-surface">
                {price.trial_days > 0 ? `Free for ${price.trial_days} days, then ` : ""}
                <span className="font-semibold">{formatPrice(price)}</span>. Cancel any time.
              </p>
            )}
          </>
        )}

        {!canBuy && (
          <p role="status" className="mt-6 text-[0.9375rem] leading-relaxed text-on-surface">
            {PRO_NOT_AVAILABLE}
          </p>
        )}

        {error && (
          <p role="alert" className="mt-5 text-[0.875rem] text-error">
            {error}
          </p>
        )}

        <div className="mt-8 flex flex-col-reverse sm:flex-row sm:justify-end gap-3">
          <button
            type="button"
            onClick={onClose}
            disabled={busy}
            className="px-5 py-3 text-[0.9375rem] text-secondary hover:text-on-surface disabled:opacity-50"
          >
            {canBuy ? "Not now" : "Close"}
          </button>
          {canBuy && (
          <button
            type="button"
            onClick={go}
            disabled={busy}
            className="rounded-md bg-tertiary hover:bg-tertiary-dim text-on-tertiary px-6 py-3 text-[0.9375rem] font-medium transition-colors disabled:opacity-50"
          >
            {busy
              ? "One moment…"
              : paymentFailed
                ? "Update payment method"
                : price && price.trial_days > 0
                  ? `Start ${price.trial_days}-day free trial`
                  : "Upgrade to Pro"}
          </button>
          )}
        </div>
      </div>
    </div>
  );
}
