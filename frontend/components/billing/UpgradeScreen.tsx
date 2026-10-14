"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { PRO_NOT_AVAILABLE, formatPrice, type PaywallCode, type Plans } from "@/lib/billing";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/card";
import { Dialog, DialogActions } from "@/components/ui/dialog";

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
    <Dialog
      open
      onOpenChange={(open) => { if (!open && !busy) onClose(); }}
      title={HEADLINES[code]}
      description={message}
    >
      {!paymentFailed && !plans && canBuy && (
        <div role="status" aria-label="Loading plan details" className="flex flex-col gap-3">
          <Skeleton className="h-4 w-4/5" />
          <Skeleton className="h-4 w-3/5" />
          <Skeleton className="h-4 w-2/3" />
        </div>
      )}
      {!paymentFailed && plans && (
        <>
          <ul className="flex flex-col gap-3 text-[0.9375rem] leading-relaxed text-on-surface">
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

      <DialogActions>
        <Button variant="secondary" onClick={onClose} disabled={busy}>
          {canBuy ? "Not now" : "Close"}
        </Button>
        {canBuy && (
          <Button variant="cta" onClick={go} loading={busy}>
            {paymentFailed
              ? "Update payment method"
              : price && price.trial_days > 0
                ? `Start ${price.trial_days}-day free trial`
                : "Upgrade to Pro"}
          </Button>
        )}
      </DialogActions>
    </Dialog>
  );
}
