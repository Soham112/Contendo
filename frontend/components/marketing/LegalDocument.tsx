import Link from "next/link";
import type { ReactNode } from "react";

export default function LegalDocument({ title, children }: { title: string; children: ReactNode }) {
  return <div className="min-h-screen bg-background font-sans text-on-surface">
    <header className="mx-auto max-w-4xl px-5 py-7 sm:px-9">
      <Link href="/" className="font-headline text-xl italic">Contendo</Link>
    </header>
    <main className="mx-auto max-w-4xl px-5 pb-20 pt-10 sm:px-9">
      <h1 className="font-headline text-4xl leading-tight">{title}</h1>
      <p className="mt-4 text-sm text-secondary">Last updated: October 13, 2026</p>
      <div className="mt-10 flex flex-col gap-9 text-base leading-relaxed [&_h2]:mb-3 [&_h2]:font-headline [&_h2]:text-2xl [&_p+p]:mt-3 [&_a]:underline [&_a]:underline-offset-4">
        {children}
      </div>
    </main>
    <footer className="bg-surface-container-low px-5 py-8">
      <nav aria-label="Legal" className="mx-auto flex max-w-4xl flex-wrap gap-6 text-sm text-secondary">
        <Link href="/">Contendo</Link><Link href="/privacy-policy">Privacy policy</Link><Link href="/terms-of-service">Terms of service</Link>
      </nav>
    </footer>
  </div>;
}
