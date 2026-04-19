"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import supabase from "@/lib/supabase";
import { useApi } from "@/lib/api";

const SKIP_ROUTES = ["/welcome", "/sign-in", "/sign-up", "/onboarding", "/first-post"];

export function useProfileCheck() {
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [isLoaded, setIsLoaded] = useState(false);
  const [loading, setLoading] = useState(true);
  const [hasProfile, setHasProfile] = useState(false);
  const [profileComplete, setProfileComplete] = useState(false);
  const [profile, setProfile] = useState<Record<string, unknown> | null>(null);
  const router = useRouter();
  const pathname = usePathname();
  const api = useApi();

  // Resolve auth state once on mount
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setIsSignedIn(!!user);
      setIsLoaded(true);
    });
  }, []);

  // Fetch profile once auth state is known
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
          setProfileComplete(data.profile_complete ?? false);
          if (!data.has_profile) {
            router.push("/first-post");
          }
        }
      })
      .finally(() => setLoading(false));
  }, [isLoaded, isSignedIn, pathname]);

  return { loading, hasProfile, profileComplete, profile };
}
