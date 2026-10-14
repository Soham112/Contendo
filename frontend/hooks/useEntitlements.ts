"use client";

import { useCallback, useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import type { Entitlements } from "@/lib/billing";

/** The user's plan as the backend reports it. `refresh` re-reads it. */
export function useEntitlements() {
  const api = useApi();
  const [entitlements, setEntitlements] = useState<Entitlements | null>(null);

  const refresh = useCallback(async () => {
    try {
      setEntitlements(await api.getEntitlements());
    } catch {
      // Unknown plan: show nothing rather than a guess. The backend still enforces it.
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  useEffect(() => {
    refresh();
  }, [refresh]);

  return { entitlements, refresh };
}
