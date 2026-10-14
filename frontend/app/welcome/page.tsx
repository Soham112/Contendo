"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import supabase from "@/lib/supabase";
import { QuillIcon } from "@/components/ContendoLogo";
import Faq from "@/components/marketing/Faq";
import NicheLinks from "@/components/marketing/NicheLinks";
import { HOME_FAQ_HEADING, HOME_HERO, homeFaqs } from "@/content/home";
import { Button } from "@/components/ui/button";

const MOOD_GRADIENTS = [
  { label: "Analytical",   from: "#3a4a35", to: "#58614f", img: "/mood-analytical.png" },
  { label: "Poetic",       from: "#6b5b4e", to: "#8a7060", img: "/mood-poetic.png" },
  { label: "Technical",    from: "#2c3e50", to: "#4a6741", img: "/mood-technical.png" },
  { label: "Narrative",    from: "#5c4a3a", to: "#7a6550", img: "/mood-narrative.png" },
  { label: "Contrarian",   from: "#3d3d3d", to: "#5a5a5a", img: "/mood-contrarian.png" },
  { label: "Visionary",    from: "#4a3f5c", to: "#6b5b7a", img: "/mood-visionary.png" },
  { label: "Reflective",   from: "#4a5c4a", to: "#6b8a6b", img: "/mood-reflective.png" },
  { label: "Direct",       from: "#5c4a2a", to: "#8a7040", img: "/mood-direct.png" },
];


function TopNav({ isSignedIn, authLoaded }: { isSignedIn: boolean; authLoaded: boolean }) {
  return (
    <nav className="sticky top-0 z-50 bg-background/80 backdrop-blur-md">
      <div className="max-w-[1200px] mx-auto px-5 sm:px-8 py-4 flex items-center justify-between relative">
        <Link
          href="/"
          className="flex min-h-11 items-center gap-2.5 font-headline italic text-on-surface text-xl tracking-tight"
        >
          <QuillIcon size={22} />
          Contendo
        </Link>

        {/* Center links — absolutely centered in the nav */}
        <div
          className="hidden md:flex items-center gap-8 absolute left-1/2 -translate-x-1/2">
          <a href="#how-it-works" className="inline-flex min-h-11 items-center text-[0.875rem] text-secondary hover:text-on-surface transition-colors">How it works</a>
          <Link href="/about" className="inline-flex min-h-11 items-center text-[0.875rem] text-secondary hover:text-on-surface transition-colors">About</Link>
          
        </div>

        {/* Right — auth-aware */}
        <div className="flex items-center gap-2 sm:gap-3">
          {authLoaded && isSignedIn ? (
            <Button asChild variant="secondary" size="sm"><Link href="/create">Open workspace</Link></Button>
          ) : (
            <>
              <Button asChild variant="tertiary" size="sm" className="hidden sm:inline-flex"><Link href="/sign-in?redirect_url=/welcome">Sign in</Link></Button>
              <Button asChild variant="secondary" size="sm"><Link href="/first-post">Get started</Link></Button>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

export default function WelcomePage() {
  const [isSignedIn, setIsSignedIn] = useState(false);
  const [authLoaded, setAuthLoaded] = useState(false);

  useEffect(() => {
    supabase.auth.getSession().then(({ data: { session } }) => {
      setIsSignedIn(!!session);
      setAuthLoaded(true);
    });
  }, []);

  const heroPrimaryCta = useMemo(() => {
    if (isSignedIn) {
      return { href: "/create", label: "Open workspace" };
    }
    return { href: "/first-post", label: "Try it free" };
  }, [authLoaded, isSignedIn]);

  return (
    <div className="min-h-screen bg-background text-on-surface font-sans">
      <TopNav isSignedIn={isSignedIn} authLoaded={authLoaded} />

      <main>

        {/* ── Hero ──────────────────────────────────────────────────────────── */}
        <section
          className="px-4 py-4 flex flex-col items-center justify-center text-center"
          style={{
            minHeight: "100vh",
            background: "linear-gradient(to bottom, #faf9f8 85%, #f3f4f3 100%)",
          }}
        >
          <div className="w-full max-w-[560px] mx-auto flex flex-col items-center">

            {/* Illustration */}
            <img
              src="/images/landing-hero.png"
              alt={HOME_HERO.imageAlt}
              className="w-full object-contain mb-4"
              style={{ maxWidth: "400px", height: "auto" }}
            />

            {/* Tagline */}
            <h1
              className="font-headline font-normal leading-[1.1] tracking-tight text-on-surface text-center text-4xl sm:text-5xl mb-3"
            >
              {HOME_HERO.headline}
            </h1>

            {/* Tagline */}
            <p
              className="font-sans text-lg text-secondary/70 text-center mx-auto mb-3"
              style={{ maxWidth: "600px" }}
            >
              {HOME_HERO.tagline}
            </p>

            {/* Intro */}
            <p
              className="font-sans text-base leading-relaxed text-secondary text-center mx-auto mb-6"
              style={{ maxWidth: "520px" }}
            >
              {HOME_HERO.intro}
            </p>

            {/* CTA */}
            <Button asChild variant="cta" size="lg" className="mb-6">
              <Link href={heroPrimaryCta.href}>{heroPrimaryCta.label}</Link>
            </Button>

            {/* Trust chips */}
            <div className="flex flex-wrap gap-6 justify-center items-center">
              {["Free to start", "Written in your voice", "You edit every draft"].map((chip) => (
                <span key={chip} className="font-sans text-sm text-on-surface-variant text-center">
                  <span aria-hidden="true">✓ </span>{chip}
                </span>
              ))}
            </div>

          </div>
        </section>

        {/* ── How it works ──────────────────────────────────────────────────── */}
        <section id="how-it-works" className="px-5 sm:px-8 py-16 sm:py-24 bg-surface-container-low">
          <div className="max-w-[1080px] mx-auto">
            <h2 className="font-headline text-[2rem] sm:text-[2.8rem] text-center mb-14">
              Three steps. No blank page.
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-3 gap-10 md:gap-12">
              {[
                {
                  num: "1.",
                  title: "Feed your knowledge",
                  body: "Paste articles, upload PDFs, drop in notes. Contendo keeps it all in a private library only you can access.",
                },
                {
                  num: "2.",
                  title: "Tell it your topic",
                  body: "Type what you want to write about. It retrieves the most relevant things you've actually read and thought about.",
                },
                {
                  num: "3.",
                  title: "Get a post worth publishing",
                  body: "A draft in your voice, grounded in your knowledge. Not generic. Not made up. Yours.",
                },
              ].map((step) => (
                <div key={step.num}>
                  <p
                    className="font-headline italic mb-3"
                    style={{ fontSize: "3rem", color: "#58614f", lineHeight: 1 }}
                  >
                    {step.num}
                  </p>
                  <p className="font-semibold text-[1rem] text-on-surface mb-2">{step.title}</p>
                  <p className="text-[0.95rem] text-secondary leading-[1.7]">{step.body}</p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Before / After ────────────────────────────────────────────────── */}
        {/*
          Structural exception to the No-Line Rule:
          the vertical center divider is a layout separator, not a decorative border.
        */}
        <section className="px-5 sm:px-8 py-24" style={{ background: "#ffffff" }}>
          <div className="max-w-[900px] mx-auto">
            {/*
              On desktop: 3-column grid [1fr 1px 1fr].
              On mobile: 1-column, divider is display:none (no grid participation),
              gap-10 (40px) between the two content columns.
            */}
            <div className="grid md:grid-cols-[1fr_1px_1fr] gap-10 md:gap-0">

              {/* Left — Without */}
              <div className="md:pr-8">
                <p
                  style={{
                    fontSize: "0.75rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05rem",
                    color: "#81543c",
                    marginBottom: "24px",
                  }}
                >
                  Without Contendo
                </p>
                <p
                  className="font-headline italic"
                  style={{ fontSize: "1.15rem", color: "#2f3333", lineHeight: 1.8 }}
                >
                  You open LinkedIn. Stare at the blank box.
                  <br />You have things to say, but turning expertise
                  <br />into a post takes two hours of editing,
                  <br />rewriting, second-guessing.
                  <br />So you close the tab. Again.
                </p>
              </div>

              {/* Center divider — desktop only */}
              <div
                className="hidden md:block self-stretch"
                style={{ background: "#e8e8e6" }}
              />

              {/* Right — With */}
              <div className="md:pl-8">
                <p
                  style={{
                    fontSize: "0.75rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05rem",
                    color: "#58614f",
                    marginBottom: "24px",
                  }}
                >
                  With Contendo
                </p>
                <p
                  className="font-headline italic"
                  style={{ fontSize: "1.15rem", color: "#2f3333", lineHeight: 1.8 }}
                >
                  You type a topic. Contendo pulls from what
                  <br />you&apos;ve actually read and thought about.
                  <br />A draft comes back in your voice:
                  <br />specific, grounded, not generic.
                  <br />You edit two lines. You post.
                </p>
              </div>

            </div>
          </div>
        </section>

        {/* ── What You Feed It ──────────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 py-24">
          <div className="max-w-[1080px] mx-auto">
            <h2
              className="font-headline text-center mb-4"
              style={{ fontSize: "2rem", color: "#2f3333" }}
            >
              Everything you know. Finally useful.
            </h2>
            <p
              className="text-secondary text-center mx-auto mb-14"
              style={{ fontSize: "1rem", lineHeight: 1.7, maxWidth: "480px" }}
            >
              Contendo works from your actual knowledge, not from what it was trained on.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  num: "01",
                  title: "Articles & research",
                  body: "Paste URLs, upload PDFs, drop in anything you've read. Every source becomes searchable context for your next post.",
                },
                {
                  num: "02",
                  title: "Your own notes",
                  body: "Raw thoughts, Obsidian vaults, voice memo transcripts. Your unpolished thinking is the most valuable input Contendo has.",
                },
                {
                  num: "03",
                  title: "Your opinions",
                  body: "Tell it what you actually believe. It injects your real takes into every draft: not hedged, not balanced, not generic.",
                },
              ].map((card) => (
                <div
                  key={card.num}
                  className="rounded-2xl"
                  style={{ background: "#f3f4f3", padding: "36px" }}
                >
                  <p
                    className="font-headline italic mb-4"
                    style={{ fontSize: "2.5rem", color: "#58614f", lineHeight: 1 }}
                  >
                    {card.num}
                  </p>
                  <p className="font-semibold text-[1rem] text-on-surface mb-2">{card.title}</p>
                  <p
                    className="text-secondary"
                    style={{ fontSize: "0.95rem", lineHeight: 1.7 }}
                  >
                    {card.body}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Philosophy — NO CHANGES ───────────────────────────────────────── */}
        <section id="atelier" className="px-5 sm:px-8 py-16 sm:py-24">
          <div className="max-w-[1080px] mx-auto grid md:grid-cols-[1fr_1.05fr] gap-8 items-center">
            <div className="rounded-2xl overflow-hidden shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)]">
              <img
                src="/desk-atelier.png"
                alt="A quiet writer's desk with a monitor, lamp, pencils and coffee"
                className="w-full h-full object-cover"
                style={{ display: "block", borderRadius: "1rem" }}
              />
            </div>

            <div>
              <p className="label-caps text-[10px] text-tertiary mb-3">The Philosophy</p>
              <h3 className="font-headline text-[2rem] sm:text-[2.7rem] leading-[1.05] mb-4">Beyond Content Generation</h3>
              <p className="text-[14px] text-secondary leading-relaxed mb-4">
                Most AI tools write from whatever they were trained on. Contendo writes from your own notes, research and opinions instead.
              </p>
              <p className="text-[14px] text-secondary leading-relaxed mb-6">
                Every draft starts from what you&apos;ve added, so it says what you would say, the way you would say it.
              </p>

              <ul className="space-y-3 text-[12px] text-on-surface/80">
                <li className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  Learns from your writing samples
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  Draws on everything in your library
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ── Features ───────────────────────────────────────────────────────── */}
        <section id="features" className="px-5 sm:px-8 py-16 sm:py-24 bg-surface-container-low">
          <div className="max-w-[1080px] mx-auto">
            <h2 className="font-headline text-[2rem] sm:text-[2.8rem] text-center mb-2">What Contendo does</h2>
            <div className="w-12 h-[1.5px] bg-tertiary/60 mx-auto mb-10" />

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
              <article className="md:col-span-7 rounded-2xl bg-surface-container p-6 sm:p-7">
                <div
                  className="archive-card-inner"
                  style={{ display: "flex", flexDirection: "row", alignItems: "center", gap: "1.5rem" }}
                >
                  <div style={{ flex: 1 }}>
                    <p className="font-headline text-[1.55rem] mb-2">The Living Archive</p>
                    <p className="text-[13px] text-secondary leading-relaxed max-w-[560px]">
                      Add any source, from PDFs to rough notes. Contendo keeps what you know in a private library.
                    </p>
                  </div>
                  <img
                    src="/archive-card.png"
                    alt="The Living Archive"
                    className="archive-card-img"
                    style={{ flex: "0 0 45%", height: 140, borderRadius: 12, objectFit: "cover", display: "block", width: "100%" }}
                  />
                </div>
              </article>

              <article
                className="md:col-span-5 rounded-2xl p-6 sm:p-7 relative overflow-hidden"
                style={{ background: "linear-gradient(135deg,#58614f 0%,#4c5543 100%)" }}
              >
                <p className="font-headline text-[1.55rem] text-white mb-2">Endless Inspiration</p>
                <p className="text-[13px] text-white/75 leading-relaxed mb-6">
                  Stuck for a topic? Get post ideas drawn from what's already in your library.
                </p>
                <Link
                  href="/ideas"
                  className="inline-flex min-h-11 items-center px-4 rounded-md text-[0.875rem] font-medium bg-white text-primary hover:bg-white/90 transition-colors" > Explore ideas
                </Link>
                <div className="absolute right-2 bottom-2 opacity-20 text-white">
                  <svg width="88" height="88" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1">
                    <path d="M12 2l2.5 6.9L22 9.2l-6 4.5 2.2 7.1L12 16.5 5.8 20.8 8 13.7l-6-4.5 7.5-.3z" />
                  </svg>
                </div>
              </article>

              <article className="md:col-span-12 rounded-2xl bg-surface-container p-6 sm:p-7 grid md:grid-cols-[1.2fr_1fr] gap-6 items-center">
                <div>
                  <p className="font-headline text-[1.55rem] mb-2">Refinement, Not Replacement</p>
                  <p className="text-[13px] text-secondary leading-relaxed max-w-[540px]">
                    Contendo acts as your editor. It rewrites any passage you select, in your voice, and scores how much a draft sounds like you. Every change starts from your own writing, not a template.
                  </p>
                  <div style={{ marginTop: "1rem", display: "flex", flexDirection: "column", gap: 8 }}>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.875rem", color: "#645e57" }}>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <polyline points="2,7 5.5,10.5 12,4" stroke="#58614f" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      Refine any passage in place
                    </div>
                    <div style={{ display: "flex", alignItems: "center", gap: 8, fontSize: "0.875rem", color: "#645e57" }}>
                      <svg width="14" height="14" viewBox="0 0 14 14" fill="none">
                        <polyline points="2,7 5.5,10.5 12,4" stroke="#58614f" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" />
                      </svg>
                      A score for how much it sounds like you
                    </div>
                  </div>
                </div>
                <div aria-hidden="true" className="glass rounded-xl p-4">
                  <p className="font-headline italic text-[1.05rem] text-secondary mb-4">
                    &ldquo;The scent of old paper and the hum of creation...&rdquo;
                  </p>
                  <div className="space-y-2">
                    <div className="h-1.5 rounded-full bg-surface-container-high w-full" />
                    <div className="h-1.5 rounded-full bg-surface-container-high w-[88%]" />
                    <div className="h-1.5 rounded-full bg-surface-container-high w-[74%]" />
                  </div>
                  <div style={{ display: "flex", gap: 8, marginTop: 12 }}>
                    <span style={{ background: "#f0ede8", color: "#645e57", borderRadius: 9999, padding: "6px 14px", fontSize: "0.75rem", letterSpacing: "0.05em" }}>
                      MORE POETIC
                    </span>
                    <span style={{ background: "#f0ede8", color: "#645e57", borderRadius: 9999, padding: "6px 14px", fontSize: "0.75rem", letterSpacing: "0.05em" }}>
                      FORMALIZE
                    </span>
                  </div>
                </div>
              </article>
            </div>
          </div>
        </section>

        {/* ── Mood grid — NO CHANGES ────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 py-16 sm:py-24">
          <div className="max-w-[1080px] mx-auto">
            <div className="flex flex-col md:flex-row md:items-end md:justify-between gap-5 mb-8">
              <div>
                <h2 className="font-headline text-[2rem] sm:text-[2.5rem] leading-tight mb-2">
                  Write in any register.
                </h2>
                <p className="text-[13px] text-secondary">
                  From analytical deep-dives to punchy contrarian takes, Contendo adapts
                  to the voice the post needs.
                </p>
              </div>
            </div>

            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              {MOOD_GRADIENTS.map((tile) => (
                <div
                  key={tile.label}
                  className="rounded-2xl relative overflow-hidden flex items-end p-4"
                  style={{ minHeight: 160 }}
                >
                  <img
                    src={tile.img}
                    alt={tile.label}
                    className="absolute inset-0 w-full h-full object-cover"
                  />
                  {/* dark gradient scrim so label stays legible */}
                  <div
                    className="absolute inset-0"
                    style={{ background: "linear-gradient(to top, rgba(0,0,0,0.55) 0%, transparent 55%)" }}
                  />
                  <span className="relative font-headline italic text-white" style={{ fontSize: "1rem" }}>
                    {tile.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── FAQ ─────────────────────────────────────────────────────────────── */}
        <Faq id="faq" heading={HOME_FAQ_HEADING} faqs={homeFaqs()} className="bg-surface-container-low" />

        {/* ── Pull quote ────────────────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 py-20 text-center">
          <div className="max-w-[680px] mx-auto">
            <p
              className="font-headline italic"
              style={{ fontSize: "clamp(1.4rem, 3vw, 2rem)", color: "#2f3333", lineHeight: 1.6 }}
            >
              Most AI content sounds like AI wrote it.
              <br />Contendo sounds like you, because it starts
              <br />from what you actually know.
            </p>
          </div>
        </section>

        {/* ── Final CTA ─────────────────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 py-20 sm:py-28 text-center bg-surface-container-low">
          <div className="max-w-[780px] mx-auto">
            <h2 className="font-headline text-[2.5rem] sm:text-[4rem] leading-[1.05] mb-4">
              Craft Your Legacy
            </h2>
            <p
              className="text-secondary mx-auto mb-8"
              style={{ fontSize: "1.05rem", lineHeight: 1.7, maxWidth: "480px" }}
            >
              Stop procrastinating. Feed it what you know, and publish something that actually
              sounds like you wrote it.
            </p>

            <Button asChild variant="cta" size="lg">
              <Link href={heroPrimaryCta.href}>{isSignedIn ? "Open workspace" : "Get started free"}</Link>
            </Button>
          </div>
        </section>

      </main>

      {/* ── Footer ────────────────────────────────────────────────────────────── */}
      <footer style={{ background: "#f3f4f3", paddingTop: "64px", paddingBottom: "48px" }}>
        <div
          className="mx-auto px-5 sm:px-8"
          style={{ maxWidth: "1100px" }}
        >
          {/* Top row: brand + link groups */}
          <div className="flex flex-col md:flex-row md:justify-between gap-8 md:gap-16">

            {/* Brand */}
            <div className="shrink-0">
              <Link
                href="/"
                className="font-headline italic text-on-surface"
                style={{ fontSize: "1.1rem" }}
              >
                Contendo
              </Link>
              <p
                className="mt-2 text-secondary"
                style={{ fontSize: "0.875rem" }}
              >
                Posts in your own voice, written from what you know.
              </p>
            </div>

            {/* Link groups */}
            <div className="flex flex-col sm:flex-row gap-10 sm:gap-12">

              <NicheLinks />

              <div>
                <p
                  className="text-primary mb-3"
                  style={{
                    fontSize: "0.75rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05rem",
                  }}
                >
                  Company
                </p>
                <div className="flex flex-col gap-2.5">
                  <a
                    href="/about"
                    className="inline-flex min-h-11 items-center text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    About us
                  </a>
                  
                </div>
              </div>

              <div>
                <p
                  className="text-primary mb-3"
                  style={{
                    fontSize: "0.75rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05rem",
                  }}
                >
                  Product
                </p>
                <div className="flex flex-col gap-2.5">
                  <a
                    href="#how-it-works"
                    className="inline-flex min-h-11 items-center text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    How it works
                  </a>
                  <Link
                    href="/sign-in"
                    className="inline-flex min-h-11 items-center text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Sign in
                  </Link>
                  <Link
                    href="/first-post"
                    className="inline-flex min-h-11 items-center text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Get started
                  </Link>
                  
                </div>
              </div>

              <div>
                <p
                  className="text-primary mb-3"
                  style={{
                    fontSize: "0.75rem",
                    textTransform: "uppercase",
                    letterSpacing: "0.05rem",
                  }}
                >
                  Legal
                </p>
                <div className="flex flex-col gap-2.5">
                  <a
                    href="/privacy-policy"
                    className="inline-flex min-h-11 items-center text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Privacy Policy
                  </a>
                  <a
                    href="/terms-of-service"
                    className="inline-flex min-h-11 items-center text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Terms of Service
                  </a>
                </div>
              </div>

            </div>
          </div>

          {/* Bottom strip */}
          <div className="mt-12">
            <p
              className="text-secondary"
              style={{ fontSize: "0.8rem" }}
            >
              © 2026 Contendo.
            </p>
          </div>
        </div>
      </footer>

    </div>
  );
}
