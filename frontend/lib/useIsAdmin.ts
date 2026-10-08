"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";

/**
 * Whether the signed-in user is an admin, as decided by the backend
 * (GET /admin/me). null while loading.
 *
 * This only decides what to show. The admin routes check the caller
 * themselves, so nothing here needs to be trusted.
 */
export function useIsAdmin(): boolean | null {
  const api = useApi();
  const [isAdmin, setIsAdmin] = useState<boolean | null>(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getAdminStatus()
      .then(async (res) => res.ok && (await res.json()).is_admin === true)
      .catch(() => false)
      .then((result) => {
        if (!cancelled) setIsAdmin(result);
      });
    return () => {
      cancelled = true;
    };
    // Checked once per mount; `api` is a new object every render.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return isAdmin;
}
