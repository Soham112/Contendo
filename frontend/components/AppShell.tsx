"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import { useProfileCheck } from "@/hooks/useProfileCheck";
import OnboardingIntercept from "@/components/OnboardingIntercept";
import LoadingWordmark from "@/components/LoadingWordmark";
import PageTransition from "@/components/PageTransition";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading, hasProfile } = useProfileCheck();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  // Checked client-side only — default true to avoid flicker before mount
  const [interceptDone, setInterceptDone] = useState(true);
  const [interceptChecked, setInterceptChecked] = useState(false);

  useEffect(() => {
    setInterceptDone(localStorage.getItem("contendo_intercept_done") === "1");
    setInterceptChecked(true);
  }, []);

  if (
    pathname === "/" ||
    pathname === "/welcome" ||
    pathname === "/onboarding" ||
    pathname === "/first-post" ||
    pathname?.startsWith("/sign-in") ||
    pathname?.startsWith("/sign-up")
  ) {
    return <PageTransition key={pathname}>{children}</PageTransition>;
  }

  if (loading || !interceptChecked) {
    return <LoadingWordmark />;
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex">
      <div className="md:hidden fixed top-0 left-0 right-0 h-[52px] bg-background z-40" style={{ boxShadow: "0 1px 0 rgba(47,51,51,0.08)" }}>
        <div className="h-full px-2 flex items-center justify-between">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setSidebarOpen(true)}
            className="w-10 h-10 flex items-center justify-center text-on-surface"
          >
            <svg width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="4" y1="5" x2="20" y2="5" stroke="#2f3333" strokeWidth="2" strokeLinecap="round" />
              <line x1="4" y1="12" x2="20" y2="12" stroke="#2f3333" strokeWidth="2" strokeLinecap="round" />
              <line x1="4" y1="19" x2="20" y2="19" stroke="#2f3333" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <p className="font-headline italic text-[1.1rem] text-on-surface leading-none">Contendo</p>
          <div className="w-10 h-10" aria-hidden="true" />
        </div>
      </div>

      {sidebarOpen && (
        <div
          className="md:hidden fixed inset-0"
          style={{ zIndex: 45, background: "rgba(47,51,51,0.45)", backdropFilter: "blur(4px)" }}
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <Sidebar mobileOpen={sidebarOpen} onClose={() => setSidebarOpen(false)} />
      <main className="flex-1 min-h-screen overflow-y-auto pt-[52px] md:pt-0">
        <div className="px-10 py-10">
          <PageTransition key={pathname}>{children}</PageTransition>
        </div>
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
