"use client";

import Link from "next/link";
import { useUser } from "@clerk/nextjs";

const STEPS = [
  {
    title: "Feed your knowledge",
    description:
      "Paste articles, YouTube transcripts, PDFs, or raw notes into Contendo. The system chunks and embeds everything into a personal vector memory store — searchable by meaning, not just keywords.",
  },
  {
    title: "Set up your voice profile",
    description:
      "Fill in your profile once: your role, your opinions, phrases you use, words you avoid, and a few writing samples. This is what separates posts that sound like you from posts that sound like ChatGPT.",
  },
  {
    title: "Generate a draft",
    description:
      "Pick a topic, format, and tone. Contendo retrieves the most relevant chunks from your memory, feeds them into the draft alongside your voice profile, then runs a humanizer pass to strip AI patterns.",
  },
  {
    title: "Score, refine, publish",
    description:
      "Every post gets an authenticity score across 5 dimensions. If anything scores low, one click sends targeted feedback to the refiner — which fixes exactly what's flagged, nothing else.",
  },
];

const MOOD_GRADIENTS = [
  "linear-gradient(135deg, #dce6ce 0%, #ced8c1 100%)",
  "linear-gradient(135deg, #eae1d8 0%, #dcd3ca 100%)",
  "linear-gradient(135deg, #f5c9ab 0%, #dfa78a 100%)",
  "linear-gradient(150deg, #e6e9e8 0%, #dfe3e2 100%)",
  "linear-gradient(135deg, #dce6ce 0%, #eae1d8 100%)",
  "linear-gradient(120deg, #eae1d8 0%, #f5c9ab 100%)",
];

export default function WelcomePage() {
  const { isSignedIn, isLoaded } = useUser();

  return (
    <div className="min-h-screen bg-background flex flex-col font-sans">

      {/* ── Navigation ──────────────────────────────────────────────────────── */}
      <nav className="fixed top-0 left-0 right-0 z-50 h-16 px-6 md:px-16 flex items-center justify-between bg-background/80 backdrop-blur-md">
        <Link href="/welcome" className="font-headline italic text-on-surface text-xl tracking-tight select-none">
          Contendo
        </Link>

        <div className="hidden md:flex items-center gap-10 h-full">
          {/* Features dropdown */}
          <div className="relative group h-full flex items-center">
            <button className="uppercase text-xs tracking-widest text-secondary hover:text-on-surface transition-colors flex items-center gap-1 cursor-pointer focus:outline-none">
              Features
              <svg
                width="10" height="10" viewBox="0 0 24 24" fill="none"
                stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round"
                className="opacity-50 group-hover:rotate-180 transition-transform duration-200"
              >
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            <div className="absolute top-[calc(100%-4px)] left-1/2 -translate-x-1/2 w-44 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 pt-2 z-50">
              <div className="bg-surface-container-lowest rounded-xl overflow-hidden py-1 shadow-card">
                <Link href="/" className="block px-4 py-2.5 text-[13px] text-secondary hover:text-on-surface hover:bg-surface-container-low transition-colors text-center">
                  Feed Memory
                </Link>
                <Link href="/library" className="block px-4 py-2.5 text-[13px] text-secondary hover:text-on-surface hover:bg-surface-container-low transition-colors text-center">
                  Library
                </Link>
                <Link href="/create" className="block px-4 py-2.5 text-[13px] text-secondary hover:text-on-surface hover:bg-surface-container-low transition-colors text-center">
                  Create Post
                </Link>
                <Link href="/ideas" className="block px-4 py-2.5 text-[13px] text-secondary hover:text-on-surface hover:bg-surface-container-low transition-colors text-center">
                  Get Ideas
                </Link>
                <Link href="/history" className="block px-4 py-2.5 text-[13px] text-secondary hover:text-on-surface hover:bg-surface-container-low transition-colors text-center">
                  History
                </Link>
              </div>
            </div>
          </div>

          <a href="#how-it-works" className="uppercase text-xs tracking-widest text-secondary hover:text-on-surface transition-colors">
            How it works
          </a>
          <a href="#" className="uppercase text-xs tracking-widest text-secondary hover:text-on-surface transition-colors">
            Pricing
          </a>
        </div>

        <div className="flex items-center gap-3">
          {isLoaded && isSignedIn ? (
            <Link
              href="/"
              className="btn-primary text-white text-xs uppercase tracking-widest font-semibold rounded-lg px-5 py-2.5 hover:opacity-90 transition-opacity"
            >
              Open workspace
            </Link>
          ) : (
            <>
              <Link href="/sign-in?redirect_url=/welcome" className="text-sm text-secondary hover:text-on-surface transition-colors px-4 py-2 rounded-lg hidden sm:block">
                Log in
              </Link>
              <Link
                href="/first-post"
                className="btn-primary text-white text-xs uppercase tracking-widest font-semibold rounded-lg px-5 py-2.5 hover:opacity-90 transition-opacity"
              >
                Write your first post
              </Link>
            </>
          )}
        </div>
      </nav>

      {/* ── Hero ────────────────────────────────────────────────────────────── */}
      <section className="flex flex-col items-center text-center px-6 pt-40 md:pt-52 pb-24 md:pb-32">
        {/* Pill badge */}
        <div className="inline-flex items-center gap-2 px-4 py-1.5 rounded-full bg-surface-container mb-10">
          <span className="text-primary text-[10px] leading-none">●</span>
          <span className="uppercase text-xs tracking-widest text-secondary font-medium">
            Powered by your knowledge
          </span>
        </div>

        {/* Headline */}
        <h1 className="font-headline text-5xl md:text-7xl lg:text-[6rem] text-on-surface leading-[1.08] tracking-tight mb-7 max-w-4xl">
          Write posts that sound like{" "}
          <span className="italic">you</span>
          {" "}— not like everyone else
        </h1>

        {/* Subtext */}
        <p className="text-xl text-secondary font-light leading-relaxed max-w-2xl mb-14">
          Contendo learns your knowledge base, your voice, and your style. Then it writes content that actually sounds like you wrote it.
        </p>

        {/* CTAs */}
        <div className="flex flex-col sm:flex-row items-center gap-4">
          {isLoaded && isSignedIn ? (
            <Link
              href="/"
              className="btn-primary text-white text-sm uppercase tracking-widest font-semibold rounded-lg px-9 py-4 hover:opacity-90 transition-opacity"
            >
              Open workspace
            </Link>
          ) : (
            <div className="flex flex-col items-center gap-3">
              <Link
                href="/first-post"
                className="btn-primary text-white text-sm uppercase tracking-widest font-semibold rounded-lg px-9 py-4 hover:opacity-90 transition-opacity"
              >
                Write your first post →
              </Link>
              <p style={{ fontSize: 13, color: "rgba(47,51,51,0.5)" }} className="font-sans text-center">
                Takes 2 minutes. No setup required.
              </p>
            </div>
          )}
          <a
            href="#how-it-works"
            className="flex items-center gap-2 px-9 py-4 text-sm font-medium text-secondary border border-outline-variant rounded-lg hover:text-on-surface hover:border-outline transition-colors"
          >
            See how it works
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <path d="M5 12h14M12 5l7 7-7 7" />
            </svg>
          </a>
        </div>
      </section>

      {/* ── Feature cards ───────────────────────────────────────────────────── */}
      <section id="features" className="px-6 md:px-16 pb-28">
        <div className="max-w-5xl mx-auto grid grid-cols-1 md:grid-cols-3 gap-5">

          <div className="rounded-xl bg-surface-container-low hover:bg-surface-container p-8 transition-colors duration-200">
            <div className="w-12 h-12 rounded-lg bg-surface-container flex items-center justify-center mb-7">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
              </svg>
            </div>
            <h3 className="font-headline text-lg text-on-surface mb-3">Feed your knowledge</h3>
            <p className="text-secondary text-sm leading-relaxed">
              Articles, notes, YouTube videos, PDFs — anything you've read becomes fuel for your posts.
            </p>
          </div>

          <div className="rounded-xl bg-surface-container-low hover:bg-surface-container p-8 transition-colors duration-200">
            <div className="w-12 h-12 rounded-lg bg-surface-container flex items-center justify-center mb-7">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 2l2.09 6.43H21l-5.47 3.97 2.09 6.43L12 15l-5.62 3.83 2.09-6.43L3 8.43h6.91z" />
              </svg>
            </div>
            <h3 className="font-headline text-lg text-on-surface mb-3">Generate in your voice</h3>
            <p className="text-secondary text-sm leading-relaxed">
              The AI learns your writing style, your opinions, and your phrases — then drafts in your exact voice.
            </p>
          </div>

          <div className="rounded-xl bg-surface-container-low hover:bg-surface-container p-8 transition-colors duration-200">
            <div className="w-12 h-12 rounded-lg bg-surface-container flex items-center justify-center mb-7">
              <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                <polyline points="22 4 12 14.01 9 11.01" />
              </svg>
            </div>
            <h3 className="font-headline text-lg text-on-surface mb-3">Score and refine</h3>
            <p className="text-secondary text-sm leading-relaxed">
              Every post gets an authenticity score. One-click refinement fixes what the AI flags before you publish.
            </p>
          </div>
        </div>
      </section>

      {/* ── Philosophy / How it works ────────────────────────────────────────── */}
      <section id="how-it-works" className="px-6 md:px-16 py-24 md:py-32 bg-surface-container-low">
        <div className="max-w-6xl mx-auto grid grid-cols-1 md:grid-cols-2 gap-16 md:gap-24 items-center">

          {/* Left: warm image placeholder */}
          <div
            className="rounded-xl bg-surface-container relative overflow-hidden"
            style={{ aspectRatio: "4/3" }}
          >
            <div className="absolute inset-0 flex items-center justify-center" style={{ opacity: 0.18 }}>
              <svg width="140" height="140" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="0.65">
                <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                <line x1="9" y1="7" x2="15" y2="7" />
                <line x1="9" y1="11" x2="15" y2="11" />
                <line x1="9" y1="15" x2="13" y2="15" />
              </svg>
            </div>
          </div>

          {/* Right: text */}
          <div>
            <p className="uppercase text-xs tracking-widest text-tertiary font-medium mb-5">
              The Philosophy
            </p>
            <h2 className="font-headline text-4xl md:text-5xl text-on-surface leading-tight mb-6">
              From raw knowledge to published post
            </h2>
            <p className="text-secondary leading-relaxed mb-10" style={{ fontSize: 15 }}>
              Four steps. No templates. No generic output. Contendo retrieves from your memory, composes in your voice, and scores the result — end to end.
            </p>

            <div className="space-y-6">
              {STEPS.slice(0, 2).map((step, i) => (
                <div key={i} className="flex gap-4">
                  <div className="w-9 h-9 rounded-lg bg-surface-container flex items-center justify-center shrink-0 mt-0.5">
                    {i === 0 ? (
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                        <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                      </svg>
                    ) : (
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                        <polygon points="12 2 15.09 8.26 22 9.27 17 14.14 18.18 21.02 12 17.77 5.82 21.02 7 14.14 2 9.27 8.91 8.26 12 2" />
                      </svg>
                    )}
                  </div>
                  <div>
                    <p className="font-medium text-on-surface mb-1" style={{ fontSize: 15 }}>{step.title}</p>
                    <p className="text-sm text-secondary leading-relaxed">{step.description}</p>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </div>
      </section>

      {/* ── Craftsman's Toolkit ──────────────────────────────────────────────── */}
      <section className="px-6 md:px-16 py-24 md:py-32">
        <div className="max-w-6xl mx-auto">
          <div className="text-center mb-16">
            <h2 className="font-headline text-4xl md:text-5xl text-on-surface">
              The Craftsman&rsquo;s Toolkit
            </h2>
            <div className="w-10 h-px bg-outline-variant mx-auto mt-5" />
          </div>

          <div className="grid grid-cols-12 gap-5">

            {/* Left tall card */}
            <div
              className="col-span-12 md:col-span-5 bg-surface-container-low rounded-xl p-8 flex flex-col justify-between"
              style={{ minHeight: 420 }}
            >
              <div>
                <div className="w-11 h-11 rounded-lg bg-surface-container flex items-center justify-center mb-6">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
                    <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
                  </svg>
                </div>
                <h3 className="font-headline text-2xl text-on-surface mb-4">Feed your knowledge</h3>
                <p className="text-secondary leading-relaxed" style={{ fontSize: 15 }}>
                  Paste articles, YouTube transcripts, PDFs, or raw notes into Contendo. The system chunks and embeds everything into a personal vector memory store — searchable by meaning, not just keywords.
                </p>
              </div>
              <div className="mt-8">
                <span className="inline-flex items-center gap-1.5 text-xs text-primary uppercase tracking-widest font-medium">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary inline-block" />
                  Memory-first architecture
                </span>
              </div>
            </div>

            {/* Right dark primary card */}
            <div
              className="col-span-12 md:col-span-7 rounded-xl p-8 flex flex-col justify-between relative overflow-hidden"
              style={{
                minHeight: 420,
                background: "linear-gradient(135deg, #58614f 0%, #4c5543 100%)",
              }}
            >
              {/* Faint icon watermark */}
              <div className="absolute right-4 bottom-4 pointer-events-none" style={{ opacity: 0.06 }}>
                <svg width="240" height="240" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="0.65">
                  <path d="M12 2l2.09 6.43H21l-5.47 3.97 2.09 6.43L12 15l-5.62 3.83 2.09-6.43L3 8.43h6.91z" />
                </svg>
              </div>

              <div>
                <div
                  className="w-11 h-11 rounded-lg flex items-center justify-center mb-6"
                  style={{ background: "rgba(255,255,255,0.12)" }}
                >
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="white" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M12 2l2.09 6.43H21l-5.47 3.97 2.09 6.43L12 15l-5.62 3.83 2.09-6.43L3 8.43h6.91z" />
                  </svg>
                </div>
                <h3 className="font-headline text-2xl text-white mb-4">Generate in your voice</h3>
                <p className="leading-relaxed" style={{ fontSize: 15, color: "rgba(255,255,255,0.70)" }}>
                  Fill in your profile once: your role, your opinions, phrases you use, words you avoid, and a few writing samples. This is what separates posts that sound like you from posts that sound like ChatGPT.
                </p>
              </div>
              <div className="mt-8">
                <span
                  className="inline-flex items-center gap-1.5 text-xs uppercase tracking-widest font-medium"
                  style={{ color: "rgba(255,255,255,0.55)" }}
                >
                  <span
                    className="w-1.5 h-1.5 rounded-full inline-block"
                    style={{ background: "rgba(255,255,255,0.55)" }}
                  />
                  Voice profile engine
                </span>
              </div>
            </div>

            {/* Bottom full-width card */}
            <div className="col-span-12 bg-surface-container-low rounded-xl p-10 flex flex-col md:flex-row items-start md:items-center gap-10">
              <div className="flex-1">
                <div className="w-11 h-11 rounded-lg bg-surface-container flex items-center justify-center mb-6">
                  <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
                    <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
                    <polyline points="22 4 12 14.01 9 11.01" />
                  </svg>
                </div>
                <h3 className="font-headline text-2xl text-on-surface mb-4">Score and refine</h3>
                <p className="text-secondary leading-relaxed max-w-lg" style={{ fontSize: 15 }}>
                  Every post gets an authenticity score across 5 dimensions. If anything scores low, one click sends targeted feedback to the refiner — which fixes exactly what's flagged, nothing else.
                </p>
              </div>

              {/* Glass score card mockup */}
              <div
                className="glass rounded-xl p-5 shrink-0 w-60"
                style={{ border: "0.5px solid rgba(174,179,178,0.35)" }}
              >
                <p className="uppercase tracking-widest text-outline font-medium mb-4" style={{ fontSize: "0.55rem" }}>
                  AUTHSCORE
                </p>
                <div className="flex items-center gap-3 mb-5">
                  <div
                    className="w-10 h-10 rounded-full shrink-0"
                    style={{ background: "linear-gradient(135deg, #dce6ce, #c5d0b8)" }}
                  />
                  <div className="flex-1">
                    <div className="h-1.5 rounded-full bg-surface-container-high w-3/4 mb-2" />
                    <div className="h-1.5 rounded-full bg-surface-container-high w-1/2" />
                  </div>
                </div>
                {["READABILITY", "CLARITY", "ENGAGEMENT"].map((label) => (
                  <div key={label} className="mb-2.5">
                    <div className="flex justify-between mb-1">
                      <span className="uppercase tracking-widest text-outline" style={{ fontSize: "0.53rem" }}>{label}</span>
                      <span className="text-secondary" style={{ fontSize: "0.53rem" }}>87</span>
                    </div>
                    <div className="h-1 rounded-full bg-surface-container-high overflow-hidden">
                      <div className="h-full rounded-full bg-primary" style={{ width: "87%" }} />
                    </div>
                  </div>
                ))}
              </div>
            </div>
          </div>
        </div>
      </section>

      {/* ── Social proof / mood grid ─────────────────────────────────────────── */}
      <section className="px-6 md:px-16 py-24 bg-surface-container-low">
        <div className="max-w-6xl mx-auto">
          <div className="grid grid-cols-1 md:grid-cols-2 gap-12 items-start mb-16">
            <div>
              <h2 className="font-headline text-4xl text-on-surface leading-snug mb-4">
                Built for creators who think in public
              </h2>
              <p className="text-secondary leading-relaxed" style={{ fontSize: 15 }}>
                Four steps. No templates. No generic output.
              </p>
            </div>
            <div className="md:pt-2">
              <p className="font-headline italic text-tertiary text-xl md:text-2xl leading-relaxed">
                &ldquo;The AI learns your writing style, your opinions, and your phrases — then drafts in your exact voice.&rdquo;
              </p>
            </div>
          </div>

          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            {Array.from({ length: 8 }).map((_, i) => (
              <div
                key={i}
                className={`rounded-lg h-56 md:h-64${i % 2 === 1 ? " mt-8" : ""}`}
                style={{ background: MOOD_GRADIENTS[i % 6] }}
              />
            ))}
          </div>
        </div>
      </section>

      {/* ── Final CTA ────────────────────────────────────────────────────────── */}
      <section className="relative py-32 md:py-48 px-6 text-center overflow-hidden bg-surface-container">
        {/* SVG dot grid overlay */}
        <div className="absolute inset-0 pointer-events-none" aria-hidden="true" style={{ opacity: 0.045 }}>
          <svg width="100%" height="100%" xmlns="http://www.w3.org/2000/svg">
            <defs>
              <pattern id="dot-grid" x="0" y="0" width="32" height="32" patternUnits="userSpaceOnUse">
                <circle cx="1" cy="1" r="1" fill="#2f3333" />
              </pattern>
            </defs>
            <rect width="100%" height="100%" fill="url(#dot-grid)" />
          </svg>
        </div>

        <div className="relative z-10 max-w-3xl mx-auto">
          <h2 className="font-headline text-5xl md:text-7xl text-on-surface leading-tight mb-6">
            Write posts that sound like{" "}
            <span className="italic">you</span>
          </h2>
          <p className="text-xl text-secondary font-light leading-relaxed mb-12 max-w-xl mx-auto">
            Contendo learns your knowledge base, your voice, and your style. Then it writes content that actually sounds like you wrote it.
          </p>
          {isLoaded && isSignedIn ? (
            <Link
              href="/"
              className="btn-primary text-white text-sm uppercase tracking-widest font-semibold rounded-lg px-10 py-4 hover:opacity-90 transition-opacity inline-block"
            >
              Open workspace
            </Link>
          ) : (
            <>
              <Link
                href="/sign-up"
                className="btn-primary text-white text-sm uppercase tracking-widest font-semibold rounded-lg px-10 py-4 hover:opacity-90 transition-opacity inline-block"
              >
                Start writing for free
              </Link>
              <p className="mt-5 uppercase text-xs tracking-widest text-outline">
                No credit card required
              </p>
            </>
          )}
        </div>
      </section>

      {/* ── Footer ───────────────────────────────────────────────────────────── */}
      <footer
        className="bg-background py-10 px-6 md:px-16 border-t"
        style={{ borderColor: "rgba(174,179,178,0.15)" }}
      >
        <div className="max-w-6xl mx-auto flex flex-col md:flex-row items-center justify-between gap-6">

          <div className="text-center md:text-left">
            <Link href="/welcome" className="font-headline italic text-on-surface text-lg">
              Contendo
            </Link>
            <p className="uppercase tracking-widest text-outline mt-1" style={{ fontSize: "0.68rem" }}>
              © 2026 Contendo. Built for creators who think in public.
            </p>
          </div>

          <div className="flex items-center gap-8">
            <a href="#" className="uppercase text-xs tracking-widest text-secondary hover:text-on-surface transition-colors">
              Privacy
            </a>
            <a href="#" className="uppercase text-xs tracking-widest text-secondary hover:text-on-surface transition-colors">
              Terms
            </a>
          </div>

          <div className="flex items-center gap-2">
            <button className="w-8 h-8 rounded-lg border border-outline-variant flex items-center justify-center text-secondary hover:text-on-surface transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <circle cx="12" cy="12" r="10" />
                <line x1="2" y1="12" x2="22" y2="12" />
                <path d="M12 2a15.3 15.3 0 0 1 4 10 15.3 15.3 0 0 1-4 10 15.3 15.3 0 0 1-4-10 15.3 15.3 0 0 1 4-10z" />
              </svg>
            </button>
            <button className="w-8 h-8 rounded-lg border border-outline-variant flex items-center justify-center text-secondary hover:text-on-surface transition-colors">
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M4 4h16c1.1 0 2 .9 2 2v12c0 1.1-.9 2-2 2H4c-1.1 0-2-.9-2-2V6c0-1.1.9-2 2-2z" />
                <polyline points="22,6 12,13 2,6" />
              </svg>
            </button>
          </div>
        </div>
      </footer>

    </div>
  );
}
