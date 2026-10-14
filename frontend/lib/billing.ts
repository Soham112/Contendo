// Types and pure helpers for plans, entitlements and upgrade prompts.
// Nothing here decides access: the backend does (billing/entitlements.py), and
// these only say what to show.

export interface Entitlements {
  plan: "free" | "pro";
  subscription_status: string | null;
  generation_limit: number;
  generations_used: number;
  generations_remaining: number;
  can_generate: boolean;
  can_publish: boolean;
  /** A Pro user whose payment failed: publishing waits until it succeeds. */
  publishing_paused: boolean;
  max_connected_accounts: number;
  trial_end: string | null;
  current_period_end: string | null;
  cancel_at_period_end: boolean;
  period: string;
}

export interface Price {
  /** In the currency's smallest unit (cents). */
  amount: number;
  currency: string;
  interval: string | null;
  trial_days: number;
}

export interface Plans {
  free: { generations_per_month: number; publishing: boolean };
  pro: {
    generations_per_month: number;
    publishing: boolean;
    max_connected_accounts: number;
    /** null when the backend could not read the price: show no figure at all. */
    price: Price | null;
  };
}

/** Why the backend refused with a 402, as the frontend reacts to it. */
export type PaywallCode = "quota_exceeded" | "upgrade_required" | "payment_required";

export interface Paywall {
  code: PaywallCode;
  message: string;
  entitlements: Entitlements | null;
}

const PAYWALL_CODES: readonly string[] = ["quota_exceeded", "upgrade_required", "payment_required"];

/** The paywall a response carries, or null when it is not a 402 from a gate. */
export function readPaywall(status: number, body: unknown): Paywall | null {
  if (status !== 402 || typeof body !== "object" || body === null) return null;
  const detail = (body as { detail?: unknown }).detail;
  if (typeof detail !== "object" || detail === null) return null;
  const { code, message, entitlements } = detail as Record<string, unknown>;
  if (typeof code !== "string" || !PAYWALL_CODES.includes(code)) return null;
  return {
    code: code as PaywallCode,
    message: typeof message === "string" ? message : "",
    entitlements: (entitlements as Entitlements | undefined) ?? null,
  };
}

/** "$39" or "$39.50", from an amount in the smallest unit. */
export function formatAmount(price: Pick<Price, "amount" | "currency">, locale = "en-US"): string {
  const whole = price.amount % 100 === 0;
  return new Intl.NumberFormat(locale, {
    style: "currency",
    currency: price.currency.toUpperCase(),
    minimumFractionDigits: whole ? 0 : 2,
    maximumFractionDigits: whole ? 0 : 2,
  }).format(price.amount / 100);
}

/** "$39 a month", or just the amount when the price does not recur. */
export function formatPrice(price: Price, locale = "en-US"): string {
  const amount = formatAmount(price, locale);
  return price.interval ? `${amount} a ${price.interval}` : amount;
}

/** "3 of 10 free posts left this month", for the quota line. */
export function quotaLine(entitlements: Entitlements): string {
  const { generations_remaining: left, generation_limit: limit, plan } = entitlements;
  const kind = plan === "free" ? "free posts" : "posts";
  return `${left} of ${limit} ${kind} left this month`;
}

/** A date like "November 3", for trial and renewal lines. */
export function formatDay(iso: string | null, locale = "en-US"): string {
  if (!iso) return "";
  return new Date(iso).toLocaleDateString(locale, { month: "long", day: "numeric" });
}
