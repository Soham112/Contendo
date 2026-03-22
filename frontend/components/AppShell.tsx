"use client";

import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/welcome") {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-page text-text-primary flex">
      <Sidebar />
      <main className="flex-1 min-h-screen overflow-y-auto">
        <div className="max-w-3xl mx-auto px-8 py-10">{children}</div>
      </main>
    </div>
  );
}
