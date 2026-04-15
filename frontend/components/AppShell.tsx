"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { useProfileCheck } from "@/hooks/useProfileCheck";
import OnboardingIntercept from "@/components/OnboardingIntercept";
import LoadingWordmark from "@/components/LoadingWordmark";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading, hasProfile } = useProfileCheck();

  // Checked client-side only — default true to avoid flicker before mount
  const [interceptDone, setInterceptDone] = useState(true);
  const [interceptChecked, setInterceptChecked] = useState(false);

  useEffect(() => {
    setInterceptDone(localStorage.getItem("contendo_intercept_done") === "1");
    setInterceptChecked(true);
  }, []);

  if (
    pathname === "/welcome" ||
    pathname === "/onboarding" ||
    pathname === "/first-post" ||
    pathname?.startsWith("/sign-in") ||
    pathname?.startsWith("/sign-up")
  ) {
    return <>{children}</>;
  }

  if (loading || !interceptChecked) {
    return <LoadingWordmark />;
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex">
      <Sidebar />
      <main className="flex-1 min-h-screen overflow-y-auto">
        <div className="px-10 py-10">{children}</div>
      </main>
      {/* Safety net: returning user who completed first-post but never saw the intercept */}
      {hasProfile && !interceptDone && (
        <OnboardingIntercept
          destination={pathname ?? "/"}
          onComplete={() => setInterceptDone(true)}
        />
      )}
    </div>
  );
}
