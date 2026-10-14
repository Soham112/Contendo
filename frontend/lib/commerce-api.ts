// Billing and publishing endpoints. Spread into useApi() (lib/api.ts), which
// supplies apiFetch with the user's token attached.

import { readPaywall, type Entitlements, type Paywall, type Plans } from "./billing";
import type { ConnectedAccount, CreateJobRequest, MediaRef, PlatformRules, PublishJob } from "./publishing";

type ApiFetch = (path: string, options?: RequestInit) => Promise<Response>;

/** Thrown when the backend refuses because of the user's plan (HTTP 402). */
export class PaywallError extends Error {
  constructor(public paywall: Paywall) {
    super(paywall.message);
  }
}

/** Thrown when a post cannot go out as it is (HTTP 422 with problems). */
export class PublishProblems extends Error {
  constructor(public problems: string[]) {
    super(problems.join(" "));
  }
}

async function read<T>(res: Response, fallback: string): Promise<T> {
  if (res.ok) return res.json();
  const body = await res.json().catch(() => null);
  const paywall = readPaywall(res.status, body);
  if (paywall) throw new PaywallError(paywall);
  const detail = body?.detail;
  if (detail?.code === "cannot_publish" && Array.isArray(detail.problems)) throw new PublishProblems(detail.problems);
  throw new Error(typeof detail === "string" ? detail : fallback);
}

const JSON_HEADERS = { "Content-Type": "application/json" };

export function commerceApi(apiFetch: ApiFetch) {
  return {
    // ── Billing ───────────────────────────────────────────────────────────
    /** Public: what each plan includes, and the Pro price from Stripe. */
    getPlans: async (): Promise<Plans> => read(await apiFetch("/billing/plans"), "Couldn't load the plans."),

    getEntitlements: async (): Promise<Entitlements> =>
      read(await apiFetch("/billing/entitlements"), "Couldn't load your plan."),

    /** A Stripe Checkout URL. The plan changes only when Stripe confirms it. */
    startCheckout: async (): Promise<{ url: string }> =>
      read(await apiFetch("/billing/checkout", { method: "POST" }), "Couldn't start checkout. Please try again."),

    openBillingPortal: async (): Promise<{ url: string }> =>
      read(await apiFetch("/billing/portal", { method: "POST" }), "Couldn't open billing. Please try again."),

    // ── Publishing ────────────────────────────────────────────────────────
    getPlatformRules: async (): Promise<PlatformRules[]> =>
      (await read<{ platforms: PlatformRules[] }>(await apiFetch("/publishing/platforms"), "Couldn't load platforms.")).platforms,

    getConnectedAccounts: async (): Promise<ConnectedAccount[]> =>
      (await read<{ accounts: ConnectedAccount[] }>(await apiFetch("/publishing/accounts"), "Couldn't load your accounts.")).accounts,

    /** Where to send the browser to connect one account on this platform. */
    connectAccount: async (platform: string): Promise<{ url: string }> =>
      read(
        await apiFetch("/publishing/connect", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify({ platform }) }),
        "Couldn't start connecting. Please try again."
      ),

    disconnectAccount: async (accountId: string): Promise<void> => {
      await read(await apiFetch(`/publishing/accounts/${accountId}`, { method: "DELETE" }), "Couldn't disconnect. Please try again.");
    },

    uploadMedia: async (file: File): Promise<MediaRef> => {
      const form = new FormData();
      form.append("file", file);
      return read(await apiFetch("/publishing/media", { method: "POST", body: form }), "Couldn't upload that file.");
    },

    createPublishJob: async (body: CreateJobRequest): Promise<PublishJob> =>
      (await read<{ job: PublishJob }>(
        await apiFetch("/publishing/jobs", { method: "POST", headers: JSON_HEADERS, body: JSON.stringify(body) }),
        "Couldn't schedule this post. Please try again."
      )).job,

    getPublishJobs: async (): Promise<PublishJob[]> =>
      (await read<{ jobs: PublishJob[] }>(await apiFetch("/publishing/jobs"), "Couldn't load your posts.")).jobs,

    cancelPublishJob: async (jobId: string): Promise<PublishJob> =>
      (await read<{ job: PublishJob }>(
        await apiFetch(`/publishing/jobs/${jobId}/cancel`, { method: "POST" }),
        "Couldn't cancel this post."
      )).job,
  };
}
