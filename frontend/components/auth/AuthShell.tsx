"use client";

// The frame shared by sign-in and sign-up: wordmark, card, heading, the
// Google button and the "or" divider.

import type { ReactNode } from "react";
import { Button } from "@/components/ui/button";

export function AuthShell({ title, children }: { title: string; children: ReactNode }) {
  return (
    <main className="min-h-screen bg-background flex flex-col items-center justify-center gap-8 px-4 py-10">
      <span className="text-[28px] font-headline italic text-on-surface tracking-tight">Contendo</span>
      <div className="w-full max-w-sm flex flex-col gap-5 rounded-2xl bg-surface-container-lowest shadow-card px-6 py-8 sm:px-8">
        <h1 className="font-headline text-[1.375rem] text-on-surface text-center">{title}</h1>
        {children}
      </div>
    </main>
  );
}

/** "Continue with Google". Google's sign-in branding guidelines ask for its logo here. */
export function GoogleButton({ onClick }: { onClick: () => void }) {
  return (
    <Button variant="secondary" className="w-full" onClick={onClick}>
      <svg aria-hidden="true" width="18" height="18" viewBox="0 0 18 18" xmlns="http://www.w3.org/2000/svg">
            <path d="M17.64 9.2c0-.637-.057-1.251-.164-1.84H9v3.481h4.844a4.14 4.14 0 0 1-1.796 2.717v2.258h2.908c1.702-1.567 2.684-3.875 2.684-6.615z" fill="#4285F4"/>
            <path d="M9 18c2.43 0 4.467-.806 5.956-2.184l-2.908-2.258c-.806.54-1.837.86-3.048.86-2.344 0-4.328-1.584-5.036-3.711H.957v2.332A8.997 8.997 0 0 0 9 18z" fill="#34A853"/>
            <path d="M3.964 10.707A5.41 5.41 0 0 1 3.682 9c0-.593.102-1.17.282-1.707V4.961H.957A8.996 8.996 0 0 0 0 9c0 1.452.348 2.827.957 4.039l3.007-2.332z" fill="#FBBC05"/>
            <path d="M9 3.58c1.321 0 2.508.454 3.44 1.345l2.582-2.58C13.463.891 11.426 0 9 0A8.997 8.997 0 0 0 .957 4.961L3.964 7.293C4.672 5.163 6.656 3.58 9 3.58z" fill="#EA4335"/>
          </svg>
      Continue with Google
    </Button>
  );
}

export function OrDivider() {
  return (
    <div className="flex items-center gap-3" aria-hidden="true">
      <div className="flex-1 h-px bg-surface-container-high" />
      <span className="text-[0.75rem] text-on-surface-variant">or</span>
      <div className="flex-1 h-px bg-surface-container-high" />
    </div>
  );
}
