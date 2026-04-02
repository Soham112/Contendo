"use client";

import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";
import FeedbackButton from "@/components/ui/FeedbackButton";
import { useProfileCheck } from "@/hooks/useProfileCheck";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();
  const { loading } = useProfileCheck();

  if (pathname === "/welcome" || pathname === "/onboarding" || pathname?.startsWith("/sign-in") || pathname?.startsWith("/sign-up")) {
    return <>{children}</>;
  }

  if (loading) {
    return (
      <div className="min-h-screen bg-background flex items-center justify-center">
        <div className="w-5 h-5 border-2 border-primary/30 border-t-primary rounded-full animate-spin" />
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex">
      <Sidebar />
      <main className="flex-1 min-h-screen overflow-y-auto">
        <div className="px-10 py-10">{children}</div>
      </main>
      <FeedbackButton />
    </div>
  );
}
