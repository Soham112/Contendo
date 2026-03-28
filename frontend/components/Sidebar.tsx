"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useUser, useClerk } from "@clerk/nextjs";

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
    href: "/ideas",
    label: "Get Ideas",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 2a4 4 0 0 1 2.5 7.1V11h-5V9.1A4 4 0 0 1 8 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
        <path d="M6 12.5h4M6.5 14h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
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
  const { user } = useUser();
  const { signOut } = useClerk();

  return (
    <aside className="w-[224px] shrink-0 h-screen sticky top-0 flex flex-col bg-surface-container-low">
      {/* Logo */}
      <div className="px-6 pt-7 pb-6">
        <Link href="/welcome" className="flex items-center gap-2.5 group">
          <div className="w-8 h-8 rounded-lg bg-surface-container flex items-center justify-center transition-colors group-hover:bg-surface-container-high">
            <svg width="14" height="14" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 9.5L4 3l4 5.5M5.5 7h3" stroke="#58614f" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <div className="flex flex-col leading-tight">
            <span className="text-[15px] font-bold text-on-surface tracking-tight font-headline">Contendo</span>
            <span className="text-[9px] uppercase tracking-[0.12em] text-secondary font-label">Editorial Atelier</span>
          </div>
        </Link>
      </div>

      {/* Nav */}
      <nav className="flex-1 px-3 pb-4 space-y-0.5 overflow-y-auto">
        {NAV_ITEMS.map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={`flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13.5px] transition-all duration-150 ${
                isActive
                  ? "bg-surface-container text-primary font-semibold"
                  : "text-secondary hover:text-on-surface hover:bg-surface-container font-medium"
              }`}
            >
              <span className={`shrink-0 ${isActive ? "text-primary" : "text-outline"}`}>
                {item.icon}
              </span>
              {item.label}
            </Link>
          );
        })}
      </nav>

      {/* New Draft CTA */}
      <div className="px-3 pb-3">
        <Link
          href="/create"
          className="btn-primary flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-[12px] uppercase tracking-widest font-semibold text-white shadow-card hover:opacity-90 active:scale-95 transition-all"
        >
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 10.5L3.5 7 10 1.5 13.5 5 6 10.5l-3.5 1.5 1-3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
          </svg>
          New Draft
        </Link>
      </div>

      {/* User row + sign out */}
      <div className="px-3 pb-5 pt-1">
        {user && (
          <div className="px-3 py-2.5 rounded-lg bg-surface-container">
            <div className="flex items-center gap-2.5 mb-2">
              {user.imageUrl ? (
                <img
                  src={user.imageUrl}
                  alt={user.fullName ?? "User"}
                  className="w-7 h-7 rounded-full shrink-0 object-cover"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                  <span className="text-[11px] font-semibold text-primary">
                    {(user.fullName ?? user.emailAddresses[0]?.emailAddress ?? "?")[0].toUpperCase()}
                  </span>
                </div>
              )}
              <div className="flex flex-col min-w-0">
                <span className="text-[13px] font-medium text-on-surface truncate leading-tight">
                  {user.fullName ?? "User"}
                </span>
                <span className="text-[11px] text-secondary truncate leading-tight">
                  {user.emailAddresses[0]?.emailAddress ?? ""}
                </span>
              </div>
            </div>
            <button
              onClick={() => signOut({ redirectUrl: "/sign-in" })}
              className="flex items-center gap-2 w-full text-[12px] text-secondary hover:text-on-surface transition-colors duration-150"
            >
              <svg width="13" height="13" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
                <path d="M6 14H3a1 1 0 0 1-1-1V3a1 1 0 0 1 1-1h3M11 11l3-3-3-3M14 8H6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
              Sign out
            </button>
          </div>
        )}
      </div>
    </aside>
  );
}
