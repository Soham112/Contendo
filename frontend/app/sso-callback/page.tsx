"use client";

import { useEffect } from "react";
import { useRouter } from "next/navigation";
import LoadingWordmark from "@/components/LoadingWordmark";

export default function SSOCallbackPage() {
  const router = useRouter();

  useEffect(() => {
    // Legacy Clerk OAuth redirect target.
    // Supabase uses /auth/callback — redirect any stale bookmarks to sign-in.
    router.replace("/sign-in");
  }, [router]);

  return <LoadingWordmark />;
}
