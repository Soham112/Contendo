"use client";

import { useEffect, useState } from "react";
import { useAuth } from "@clerk/nextjs";
import { useRouter, usePathname } from "next/navigation";
import { useApi } from "@/lib/api";

const SKIP_ROUTES = ["/welcome", "/sign-in", "/sign-up", "/onboarding", "/first-post"];

export function useProfileCheck() {
  const { isSignedIn, isLoaded } = useAuth();
  const [loading, setLoading] = useState(true);
  const [hasProfile, setHasProfile] = useState(false);
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const api = useApi();

  useEffect(() => {
    if (!isLoaded) return;
    if (!isSignedIn) {
      setLoading(false);
      return;
    }
    if (SKIP_ROUTES.some((r) => pathname?.startsWith(r))) {
      setLoading(false);
      return;
    }

    api
      .getProfile()
      .then(async (res) => {
        if (res.ok) {
          const data = await res.json();
          setProfile(data.profile);
          setHasProfile(data.has_profile);
          if (!data.has_profile) {
            router.push("/first-post");
          }
        }
      })
      .finally(() => setLoading(false));
  }, [isLoaded, isSignedIn, pathname]);

  return { loading, hasProfile, profile };
}
