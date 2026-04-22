"use client";

import { useEffect, useState } from "react";
import { useRouter, usePathname } from "next/navigation";
import supabase from "@/lib/supabase";
import { useApi } from "@/lib/api";

// Extension ID from chrome://extensions (load unpacked → copy the ID).
// The ID is stable for a given unpacked extension directory.
const CONTENDO_EXTENSION_ID = "nlfgeodogbhnningocmjcjdndgcimbon";

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

  // Resolve auth state once on mount and push token to the Chrome extension.
  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => {
      setIsSignedIn(!!user);
      setIsLoaded(true);

      if (user) {
        // Push the Supabase access_token to the Chrome extension via
        // externally_connectable. Runs whenever the Contendo app loads while
        // the user is signed in — this is the push model that replaces all
        // content-script polling. Fails silently if the extension isn't installed.
        supabase.auth.getSession().then(({ data: { session } }) => {
          if (!session?.access_token) return;
          try {
            const chr = (window as any).chrome;
            if (chr?.runtime?.sendMessage) {
              chr.runtime.sendMessage(
                CONTENDO_EXTENSION_ID,
                { action: "setToken", token: session.access_token },
                () => { void chr.runtime?.lastError; } // suppress "no listener" console error
              );
            }
          } catch (_) {
            // Extension not installed or externally_connectable not wired yet — ignore.
          }
        });
      }
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
