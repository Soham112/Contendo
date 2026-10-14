// Account endpoints. Spread into useApi() (lib/api.ts), which supplies apiFetch
// with the user's token attached; never call these with a raw fetch.

import type { Account, NicheOptions, SegmentAnswer } from "./account";

type ApiFetch = (path: string, options?: RequestInit) => Promise<Response>;

async function readJson<T>(res: Response, what: string): Promise<T> {
  if (!res.ok) {
    const detail = (await res.json().catch(() => null))?.detail;
    throw new Error(typeof detail === "string" ? detail : `${what} failed. Please try again.`);
  }
  return res.json();
}

export function accountApi(apiFetch: ApiFetch) {
  return {
    /** Public: segments, niches with their content pillars, and tones. */
    getNicheOptions: async (): Promise<NicheOptions> =>
      readJson(await apiFetch("/niches"), "Loading the options"),

    getAccount: async (): Promise<Account> => readJson(await apiFetch("/account"), "Loading your account"),

    saveSegment: async (answer: SegmentAnswer): Promise<Account> =>
      readJson(
        await apiFetch("/account/segment", {
          method: "PUT",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(answer),
        }),
        "Saving your answer"
      ),

    skipSegment: async (): Promise<Account> =>
      readJson(await apiFetch("/account/segment/skip", { method: "POST" }), "Skipping"),
  };
}
