"use client";

import { useState, useEffect } from "react";
import { usePathname } from "next/navigation";
import RetryNotice from "@/components/RetryNotice";
import Sidebar from "@/components/Sidebar";
import { useProfileCheck } from "@/hooks/useProfileCheck";
import { useAccount } from "@/hooks/useAccount";

import SegmentPrompt from "@/components/onboarding/SegmentPrompt";
import LoadingWordmark from "@/components/LoadingWordmark";
import PageTransition from "@/components/PageTransition";
import { useTracking } from "@/lib/useTracking";
import { isLegalPath } from "@/lib/legal";
import { isNichePath } from "@/content/niches";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading, hasProfile, error: profileError, retry: retryProfile } = useProfileCheck();
  // Who the user creates content for decides which onboarding prompt applies.
  const { account, loaded: accountLoaded, error: accountError, retry: retryAccount } = useAccount(hasProfile);
  const { logEvent } = useTracking();
  const [sidebarOpen, setSidebarOpen] = useState(false);

  useEffect(() => {
    if (pathname) {
      logEvent({ event_type: "page_view", page_url: pathname });
    }
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pathname]);

  // Marketing pages (home, niche and legal pages) are server-rendered: no shell
  // and no entrance animation, so their content is visible before any script
  // runs. The animation starts at opacity 0 and would hide them until hydration.
  if (pathname === "/" || pathname === "/welcome" || isNichePath(pathname) || isLegalPath(pathname)) {
    return <>{children}</>;
  }

  if (
    pathname === "/onboarding" ||
    pathname === "/first-post" ||
    pathname === "/get-started" ||
    pathname?.startsWith("/sign-in") ||
    pathname?.startsWith("/sign-up")
  ) {
    return <PageTransition key={pathname}>{children}</PageTransition>;
  }

  if (loading) {
    return <LoadingWordmark />;
  }

  if (profileError || accountError) return <main className="max-w-xl mx-auto px-4 py-10"><RetryNotice message={profileError || accountError} onRetry={profileError ? retryProfile : retryAccount} /></main>;



  return (
    <div className="min-h-screen bg-background text-on-surface flex">
      <div className="md:hidden fixed top-0 left-0 right-0 h-[52px] bg-background z-40" style={{ boxShadow: "0 1px 0 rgba(47,51,51,0.08)" }}>
        <div className="h-full px-2 flex items-center justify-between">
          <button
            type="button"
            aria-label="Open menu"
            onClick={() => setSidebarOpen(true)}
            className="w-11 h-11 rounded-md flex items-center justify-center text-on-surface hover:bg-surface-container"
          >
            <svg aria-hidden="true" width="22" height="22" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
              <line x1="4" y1="5" x2="20" y2="5" stroke="#2f3333" strokeWidth="2" strokeLinecap="round" />
              <line x1="4" y1="12" x2="20" y2="12" stroke="#2f3333" strokeWidth="2" strokeLinecap="round" />
              <line x1="4" y1="19" x2="20" y2="19" stroke="#2f3333" strokeWidth="2" strokeLinecap="round" />
            </svg>
          </button>
          <p className="font-headline italic text-[1.1rem] text-on-surface leading-none">Contendo</p>
          <div className="w-11 h-11" aria-hidden="true" />
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
        <div className="px-4 py-6 sm:px-6 md:px-10 md:py-10">
          <PageTransition key={pathname}>{children}</PageTransition>
        </div>
      </main>
      {hasProfile && accountLoaded && <SegmentPrompt due={!!account?.ask_segment} />}
    </div>
  );
}
