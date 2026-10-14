"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import type { Entitlements } from "@/lib/billing";

/**
 * The user's plan as the backend reports it. `refresh` re-reads it. `failed`
 * is true when the last read failed, so a screen that needs the plan can
 * offer a retry instead of waiting forever.
 */
export function useEntitlements() {
  const api = useApi();
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);
  const [failed, setFailed] = useState(false);

  const refresh = useCallback(async () => {
    setFailed(false);
    try {
      setEntitlements(await api.getEntitlements());
    } catch {
      // Unknown plan: show nothing rather than a guess. The backend still enforces it.
      setFailed(true);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { entitlements, refresh, failed };
}
