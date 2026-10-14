import { describe, expect, it } from "vitest";
import { formatAmount, formatPrice, quotaLine, readPaywall, type Entitlements } from "./billing";

const FREE: Entitlements = {
  plan: "free", subscription_status: null, generation_limit: 10, generations_used: 7, generations_remaining: 3,
  can_generate: true, can_publish: false, publishing_paused: false, max_accounts_per_platform: 0,
  trial_end: null, current_period_end: null, cancel_at_period_end: false, period: "2026-10",
};

describe("readPaywall", () => {
  it("reads a 402 from a gate", () => {
    const body = { detail: { code: "quota_exceeded", message: "Used up.", entitlements: FREE } };
    expect(readPaywall(402, body)).toEqual({ code: "quota_exceeded", message: "Used up.", entitlements: FREE });
  });

  it("is null for anything else", () => {
    expect(readPaywall(500, { detail: { code: "quota_exceeded" } })).toBeNull();
    expect(readPaywall(402, { detail: "Payment required" })).toBeNull();
    expect(readPaywall(402, { detail: { code: "something_else" } })).toBeNull();
    expect(readPaywall(402, null)).toBeNull();
  });
});

describe("prices", () => {
  it("come from the amount the backend gives, with no cents when whole", () => {
    expect(formatAmount({ amount: 3900, currency: "usd" })).toBe("$39");
    expect(formatAmount({ amount: 3950, currency: "usd" })).toBe("$39.50");
    expect(formatPrice({ amount: 3900, currency: "usd", interval: "month", trial_days: 7 })).toBe("$39 a month");
    expect(formatPrice({ amount: 9900, currency: "usd", interval: null, trial_days: 0 })).toBe("$99");
  });
});

describe("quotaLine", () => {
  it("says how many free posts are left", () => {
    expect(quotaLine(FREE)).toBe("3 of 10 free posts left this month");
    expect(quotaLine({ ...FREE, plan: "pro", generation_limit: 300, generations_remaining: 290 })).toBe(
      "290 of 300 posts left this month"
    );
  });
});
