"use client";

import { useState, useEffect } from "react";
import Link from "next/link";
import { usePathname, useRouter } from "next/navigation";
import type { User } from "@supabase/supabase-js";
import supabase from "@/lib/supabase";
import FeedbackModal from "@/components/ui/FeedbackButton";

const NAV_ITEMS = [
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
    href: "/",
    label: "Feed Memory",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <path d="M8 2v12M2 8h12" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
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
    href: "/history",
    label: "History",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="8" cy="8" r="6" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M8 5v3.5l2 2" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
      </svg>
    ),
  },
  {
    href: "/settings",
    label: "Settings",
    icon: (
      <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
        <circle cx="8" cy="8" r="2" stroke="currentColor" strokeWidth="1.5"/>
        <path d="M8 1v2M8 13v2M1 8h2M13 8h2M3.05 3.05l1.41 1.41M11.54 11.54l1.41 1.41M3.05 12.95l1.41-1.41M11.54 4.46l1.41-1.41" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      </svg>
    ),
  },
];

const ADMIN_EMAIL = "soham112000@gmail.com";

export default function Sidebar({
  mobileOpen,
  onClose,
}: {
  mobileOpen: boolean;
  onClose: () => void;
}) {
  const pathname = usePathname();
  const router = useRouter();
  const [user, setUser] = useState<User | null>(null);
  const [feedbackOpen, setFeedbackOpen] = useState(false);

  useEffect(() => {
    supabase.auth.getUser().then(({ data: { user } }) => setUser(user));
    const {
      data: { subscription },
    } = supabase.auth.onAuthStateChange((_, session) => {
      setUser(session?.user ?? null);
    });
    return () => subscription.unsubscribe();
  }, []);

  async function handleSignOut() {
    await supabase.auth.signOut();
    router.push("/sign-in");
  }

  const displayName =
    user?.user_metadata?.full_name ??
    user?.user_metadata?.name ??
    "User";
  const email = user?.email ?? "";
  const avatarUrl = user?.user_metadata?.avatar_url ?? null;

  return (
    <>
    <aside
      className={`fixed top-0 left-0 h-screen w-[280px] bg-surface-container-low z-50 flex flex-col md:w-[224px] md:shrink-0 md:sticky md:top-0 md:z-auto ${
        mobileOpen ? "translate-x-0" : "-translate-x-full"
      } md:translate-x-0`}
      style={{ transition: `transform ${mobileOpen ? "250ms ease-out" : "200ms ease-in"}` }}
    >
      {/* Logo */}
      <div className="px-6 pt-7 pb-6 relative">
        <button
          type="button"
          aria-label="Close menu"
          onClick={onClose}
          className="md:hidden absolute top-3 right-3 w-10 h-10 flex items-center justify-center text-on-surface"
        >
          <svg width="18" height="18" viewBox="0 0 24 24" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M6 6L18 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
            <path d="M18 6L6 18" stroke="currentColor" strokeWidth="2" strokeLinecap="round" />
          </svg>
        </button>
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
        {[...NAV_ITEMS, ...(user?.email === ADMIN_EMAIL ? [{
          href: "/admin",
          label: "Admin",
          icon: (
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M8 2L2 5v4c0 3 2.5 5.2 6 6 3.5-.8 6-3 6-6V5L8 2z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          ),
        }] : [])].map((item) => {
          const isActive =
            item.href === "/"
              ? pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              onClick={onClose}
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

      {/* Create Post CTA */}
      <div className="px-3 pb-3">
        <Link
          href="/create"
          onClick={onClose}
          className="btn-primary flex items-center justify-center gap-2 w-full py-2.5 rounded-lg text-[12px] uppercase tracking-widest font-semibold text-white shadow-card hover:opacity-90 active:scale-95 transition-all"
        >
          <svg width="13" height="13" viewBox="0 0 14 14" fill="none" xmlns="http://www.w3.org/2000/svg">
            <path d="M2 10.5L3.5 7 10 1.5 13.5 5 6 10.5l-3.5 1.5 1-3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
          </svg>
          Create Post
        </Link>
      </div>

      {/* Send Feedback */}
      <div className="px-3 pb-1">
        <button
          onClick={() => setFeedbackOpen(true)}
          className="flex items-center gap-3 px-3 py-2.5 rounded-lg text-[13.5px] transition-all duration-150 w-full text-secondary hover:text-on-surface hover:bg-surface-container font-medium"
        >
          <span className="shrink-0 text-outline">
            <svg width="16" height="16" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M13 2H3a1 1 0 0 0-1 1v7a1 1 0 0 0 1 1h3l2 2 2-2h3a1 1 0 0 0 1-1V3a1 1 0 0 0-1-1z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
            </svg>
          </span>
          Send Feedback
        </button>
      </div>

      {/* User row + sign out */}
      <div className="px-3 pb-5 pt-1">
        {user && (
          <div className="px-3 py-2.5 rounded-lg bg-surface-container">
            <div className="flex items-center gap-2.5 mb-2">
              {avatarUrl ? (
                // eslint-disable-next-line @next/next/no-img-element
                <img
                  src={avatarUrl}
                  alt={displayName}
                  className="w-7 h-7 rounded-full shrink-0 object-cover"
                />
              ) : (
                <div className="w-7 h-7 rounded-full bg-primary/20 flex items-center justify-center shrink-0">
                  <span className="text-[11px] font-semibold text-primary">
                    {(displayName ?? email ?? "?")[0].toUpperCase()}
                  </span>
                </div>
              )}
              <div className="flex flex-col min-w-0">
                <span className="text-[13px] font-medium text-on-surface truncate leading-tight">
                  {displayName}
                </span>
                <span className="text-[11px] text-secondary truncate leading-tight">
                  {email}
                </span>
              </div>
            </div>
            <button
              onClick={handleSignOut}
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

    <FeedbackModal open={feedbackOpen} onClose={() => setFeedbackOpen(false)} />
    </>
  );
}
