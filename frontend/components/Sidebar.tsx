"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const NAV_ITEMS = [
  {
    href: "/",
    label: "Feed Memory",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/library",
    label: "Library",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <rect x="2" y="3" width="3" height="10" rx="0.5" stroke="currentColor" strokeWidth="1.5"/>
        <rect x="6.5" y="3" width="3" height="10" rx="0.5" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M11 3.5l2.5 9" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
  {
    href: "/create",
    label: "Create Post",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M2 12.5L3.5 9 11 1.5 14.5 5 7 12.5l-3.5 1.5 1-3.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    href: "/history",
    label: "History",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M8 5v3.5l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
];

export default function Sidebar() {
  const pathname = usePathname();

  return (
    <aside className="w-56 shrink-0 h-screen sticky top-0 flex flex-col border-r border-border bg-surface">
      {/* Logo */}
      <div className="px-5 py-5 border-b border-border">
        <Link href="/welcome" className="flex items-center gap-2 group">
          <div className="w-6 h-6 rounded bg-amber flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 9.5L4 3l4 5.5M5.5 7h3" stroke="white" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="text-sm font-semibold text-text-primary tracking-tight">Contendo</span>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 py-4 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-2.5 px-2.5 py-2 rounded-lg text-sm transition-colors ${
                isActive
                  ? "bg-amber-light text-amber border border-amber-border font-medium"
                  : "text-text-secondary hover:text-text-primary hover:bg-hover"
              }`}
            >
              <span className="shrink-0">{item.icon}</span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* Bottom user row */}
      <div className="px-4 py-4 border-t border-border">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded-full bg-stat border border-border flex items-center justify-center shrink-0">
            <svg width="14" height="14" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
              <circle cx="7" cy="5" r="2.5" stroke="#aaa89f" strokeWidth="1.3"/>
              <path d="M2 12c0-2.5 2.24-4.5 5-4.5s5 2 5 4.5" stroke="#aaa89f" strokeWidth="1.3" strokeLinecap="round"/>
            </svg>
          </div>
          <span className="text-xs text-text-muted">My workspace</span>
        </div>
      </div>
    </aside>
  );
}
