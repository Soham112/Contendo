"use client";

import { usePathname } from "next/navigation";
import Sidebar from "@/components/Sidebar";

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname();

  if (pathname === "/welcome") {
    return <>{children}</>;
  }

  return (
    <div className="min-h-screen bg-background text-on-surface flex">
      <Sidebar />
      <main className="flex-1 min-h-screen overflow-y-auto">
        <div className="px-10 py-10">{children}</div>
      </main>
    </div>
  );
}
