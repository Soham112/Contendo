"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import type { Account } from "@/lib/account";

/**
 * The signed-in user's account (segment, niche, whether to ask the segment
 * question). `loaded` turns true once the answer is known, or known to be
 * unavailable: callers must not guess a segment before then.
 */
export function useAccount(enabled: boolean) {
  const api = useApi();
  const [account, setAccount] = useState<Account | null>(null);
  const [loaded, setLoaded] = useState(false);
  const [error, setError] = useState("");
  const [attempt, setAttempt] = useState(0);

  useEffect(() => {
    if (!enabled) return;
    let cancelled = false;
    setLoaded(false);
    setError("");
    api
      .getAccount()
      .then((result) => {
        if (!cancelled) setAccount(result);
      })
      .catch(() => { if (!cancelled) setError("We couldn’t load your account. Please try again."); })
      .finally(() => {
        if (!cancelled) setLoaded(true);
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, attempt]);

  return { account, loaded, error, retry: () => setAttempt((value) => value + 1) };
}
