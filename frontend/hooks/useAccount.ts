"use client";

import { useEffect, useState } from "react";
import { usePathname } from "next/navigation";
import { useApi } from "@/lib/api";
import type { Account } from "@/lib/account";

/**
 * The signed-in user's account (segment, niche, whether to ask the segment
 * question). `loaded` turns true once the answer is known, or known to be
 * unavailable: callers must check `error` and never guess a segment on failure.
 */
export function useAccount(enabled: boolean) {
  const api = useApi();
  const pathname = usePathname();
  const [resolvedPath, setResolvedPath] = useState<string | null>(null);
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
        if (!cancelled) { setResolvedPath(pathname); setLoaded(true); }
      });
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [enabled, attempt, pathname]);

  // AppShell survives navigation. Never reuse an unanswered account snapshot
  // from before a setup save on the newly opened workspace route.
  const current = loaded && resolvedPath === pathname;
  return { account: current ? account : null, loaded: current,
    error: current ? error : "", retry: () => setAttempt((value) => value + 1) };
}
