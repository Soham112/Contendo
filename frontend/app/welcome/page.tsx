"use client";

import Link from "next/link";
import { FormEvent, useMemo, useRef, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";

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

const HERO_DRAFT_KEY = "contentOS_last_topic";
const SHARED_TOPIC_KEY = "contendo_topic";

function TopNav({ isSignedIn, isLoaded }: { isSignedIn: boolean; isLoaded: boolean }) {
  return (
    <nav className="sticky top-0 z-50 bg-background/80 backdrop-blur-md">
      <div className="max-w-[1200px] mx-auto px-5 sm:px-8 py-4 flex items-center justify-between">
        <Link
          href="/welcome"
          className="font-headline italic text-on-surface text-xl tracking-tight"
        >
          Contendo
        </Link>

        {/* Center links — hidden on mobile */}
        <div className="hidden md:flex items-center gap-8">
          <a
            href="#how-it-works"
            className="text-[0.875rem] text-secondary hover:text-on-surface transition-colors"
          >
            How it works
          </a>
          <a
            href="/about"
            className="text-[0.875rem] text-secondary hover:text-on-surface transition-colors"
          >
            About
          </a>
          <a
            href="/careers"
            className="text-[0.875rem] text-secondary hover:text-on-surface transition-colors"
          >
            Careers
          </a>
          <a
            href="/pricing"
            className="text-[0.875rem] text-secondary hover:text-on-surface transition-colors"
          >
            Pricing
          </a>
        </div>

        {/* Right — auth-aware, unchanged */}
        <div className="flex items-center gap-2 sm:gap-3">
          {isLoaded && isSignedIn ? (
            <Link
              href="/"
              className="btn-primary text-white text-[11px] label-caps rounded-lg px-4 py-2.5 sm:px-5"
            >
              Open workspace
            </Link>
          ) : (
            <>
              <Link
                href="/sign-in?redirect_url=/welcome"
                className="hidden sm:inline-flex text-[12px] text-secondary hover:text-on-surface px-3 py-2 rounded-lg transition-colors"
              >
                Sign in
              </Link>
              <Link
                href="/first-post"
                className="btn-primary text-white text-[11px] label-caps rounded-lg px-4 py-2.5 sm:px-5"
              >
                Get started
              </Link>
            </>
          )}
        </div>
      </div>
    </nav>
  );
}

export default function WelcomePage() {
  const router = useRouter();
  const { isSignedIn, isLoaded } = useUser();
  const [topicInput, setTopicInput] = useState("");
  const [showInputError, setShowInputError] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const SUGGESTION_PILLS = [
    "Why I changed my mind on...",
    "What 3 years of X taught me",
    "The mistake most people make with...",
    "My honest take on...",
  ];

  const heroPrimaryCta = useMemo(() => {
    if (isLoaded && isSignedIn) {
      return { href: "/", label: "Open workspace" };
    }
    return { href: "/first-post", label: "Write your first post" };
  }, [isLoaded, isSignedIn]);

  // ── DO NOT TOUCH — routing + sessionStorage logic ──────────────────────────
  const handleHeroSubmit = (event: FormEvent) => {
    event.preventDefault();
    const topic = topicInput.trim();

    if (!topic) {
      setShowInputError(true);
      return;
    }

    setShowInputError(false);
    sessionStorage.setItem(SHARED_TOPIC_KEY, topic);

    if (isLoaded && isSignedIn) {
      sessionStorage.setItem(HERO_DRAFT_KEY, topic);
      router.push("/create");
      return;
    }

    router.push(`/first-post?topic=${encodeURIComponent(topic)}`);
  };
  // ── END DO NOT TOUCH ───────────────────────────────────────────────────────

  return (
    <div className="min-h-screen bg-background text-on-surface font-sans">
      <TopNav isSignedIn={!!isSignedIn} isLoaded={!!isLoaded} />

      <main>

        {/* ── Hero ──────────────────────────────────────────────────────────── */}
        <section
          className="px-5 sm:px-8 text-center flex flex-col items-center justify-center"
          style={{
            minHeight: "100vh",
            paddingTop: 120,
            paddingBottom: 72,
            background: "linear-gradient(to bottom, #faf9f8 85%, #f3f4f3 100%)",
          }}
        >
          <div className="max-w-[980px] mx-auto">
            <h1
              className="font-headline font-normal leading-[1.1] tracking-tight mb-5"
              style={{ fontSize: "clamp(2.8rem, 5vw, 3.8rem)", color: "#2f3333" }}
            >
              Write like yourself. At scale.
            </h1>

            <p
              className="text-secondary mx-auto"
              style={{
                fontSize: "1.1rem",
                lineHeight: 1.7,
                maxWidth: "500px",
                marginBottom: "48px",
              }}
            >
              Feed it your notes, articles, and opinions.
              It learns your voice and writes posts you&apos;d actually publish.
            </p>

            <form
              onSubmit={handleHeroSubmit}
              className="mx-auto rounded-xl flex flex-col sm:flex-row gap-2 sm:items-center"
              style={{
                maxWidth: "680px",
                background: "#ffffff",
                border: "1px solid rgba(174, 179, 178, 0.25)",
                padding: "8px 8px 8px 16px",
              }}
              aria-label="Start your first post"
            >
              <input
                ref={inputRef}
                value={topicInput}
                onChange={(event) => {
                  setTopicInput(event.target.value);
                  if (showInputError && event.target.value.trim()) {
                    setShowInputError(false);
                  }
                }}
                placeholder="What do you want to write about today?"
                className="flex-1 bg-transparent text-[14px] sm:text-[13px] text-on-surface placeholder:text-outline focus:outline-none focus:border-b-2 focus:border-b-[#58614f]"
                style={{ minHeight: "64px", paddingTop: "20px", paddingBottom: "20px" }}
                aria-label="Topic prompt"
              />
              <button
                type="submit"
                className="btn-primary text-white text-[13px] font-medium rounded-md px-5 py-3 sm:py-2.5 whitespace-nowrap self-center w-full sm:w-auto"
              >
                Start Writing
              </button>
            </form>

            {showInputError && (
              <p className="mt-2 text-[12px] text-secondary/80">Add a topic first to continue.</p>
            )}

            {/* ── Suggestion pills ──────────────────────────────────────────── */}
            <div style={{ marginTop: "20px" }}>
              <p
                className="text-center mb-3"
                style={{
                  fontSize: "0.7rem",
                  textTransform: "uppercase",
                  letterSpacing: "0.06rem",
                  color: "rgba(100, 94, 87, 0.5)",
                }}
              >
                Or start from a prompt
              </p>
              <div
                style={{
                  display: "flex",
                  flexWrap: "wrap",
                  gap: "10px",
                  justifyContent: "center",
                }}
              >
                {SUGGESTION_PILLS.map((pill) => (
                  <button
                    key={pill}
                    type="button"
                    onClick={() => {
                      setTopicInput(pill);
                      inputRef.current?.focus();
                    }}
                    style={{
                      background: "#ffffff",
                      border: "1px solid rgba(174, 179, 178, 0.35)",
                      borderRadius: "9999px",
                      padding: "8px 16px",
                      fontSize: "0.8rem",
                      color: "var(--color-text-secondary, #645e57)",
                      cursor: "pointer",
                      transition: "background 0.15s ease",
                    }}
                    onMouseEnter={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "#f3f4f3";
                    }}
                    onMouseLeave={(e) => {
                      (e.currentTarget as HTMLButtonElement).style.background = "#ffffff";
                    }}
                  >
                    {pill}
                  </button>
                ))}
              </div>
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
                  body: "Paste articles, upload PDFs, drop in notes. Contendo indexes everything into a private semantic library only you can access.",
                },
                {
                  num: "2.",
                  title: "Tell it your topic",
                  body: "Type what you want to write about. It retrieves the most relevant things you've actually read and thought about.",
                },
                {
                  num: "3.",
                  title: "Get a post worth publishing",
                  body: "A draft in your voice, grounded in your knowledge. Not generic. Not hallucinated. Yours.",
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
                  <br />You have things to say — but turning expertise
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
                  <br />A draft comes back in your voice —
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
              Contendo works from your actual knowledge — not from what it was trained on.
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
                  body: "Tell it what you actually believe. It injects your real takes into every draft — not hedged, not balanced, not generic.",
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
                alt="A quiet writer's desk — monitor, lamp, pencils, coffee"
                className="w-full h-full object-cover"
                style={{ display: "block", borderRadius: "1rem" }}
              />
            </div>

            <div>
              <p className="label-caps text-[10px] text-tertiary mb-3">The Philosophy</p>
              <h3 className="font-headline text-[2rem] sm:text-[2.7rem] leading-[1.05] mb-4">Beyond Content Generation</h3>
              <p className="text-[14px] text-secondary leading-relaxed mb-4">
                In an age of generic noise, we believe in the Digital Atelier. Rather than asking an AI to hallucinate, you feed Contendo your own library of notes, research, and sparks.
              </p>
              <p className="text-[14px] text-secondary leading-relaxed mb-6">
                Our engine doesn&apos;t just infer; it synthesizes your specific knowledge base to produce resonance that feels authentically yours.
              </p>

              <ul className="space-y-3 text-[12px] text-on-surface/80">
                <li className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  Personal Style Synthesis
                </li>
                <li className="flex items-center gap-2">
                  <span className="w-1.5 h-1.5 rounded-full bg-primary" />
                  Knowledge Graph Integration
                </li>
              </ul>
            </div>
          </div>
        </section>

        {/* ── Craftsman's Toolkit — NO CHANGES ─────────────────────────────── */}
        <section id="features" className="px-5 sm:px-8 py-16 sm:py-24 bg-surface-container-low">
          <div className="max-w-[1080px] mx-auto">
            <h2 className="font-headline text-[2rem] sm:text-[2.8rem] text-center mb-2">The Craftsman&apos;s Toolkit</h2>
            <div className="w-12 h-[1.5px] bg-tertiary/60 mx-auto mb-10" />

            <div className="grid grid-cols-1 md:grid-cols-12 gap-4">
              <article className="md:col-span-7 rounded-2xl bg-surface-container p-6 sm:p-7">
                <p className="font-headline text-[1.55rem] mb-2">The Living Archive</p>
                <p className="text-[13px] text-secondary leading-relaxed max-w-[560px] mb-5">
                  Input any source, from PDFs to raw voice notes. Contendo indexes your unique
                  world-view into a private semantic library.
                </p>
                <div className="h-[110px] rounded-xl bg-surface-container-high relative overflow-hidden">
                  <div className="absolute inset-0 opacity-50 bg-[radial-gradient(circle_at_70%_45%,#2f3333_0%,transparent_45%)]" />
                </div>
              </article>

              <article
                className="md:col-span-5 rounded-2xl p-6 sm:p-7 relative overflow-hidden"
                style={{ background: "linear-gradient(135deg,#58614f 0%,#4c5543 100%)" }}
              >
                <p className="font-headline text-[1.55rem] text-white mb-2">Endless Inspiration</p>
                <p className="text-[13px] text-white/75 leading-relaxed mb-6">
                  Break through writer&apos;s block with an ideation engine that suggests angles
                  based on the gaps in your existing archive.
                </p>
                <Link
                  href="/ideas"
                  className="inline-flex px-3.5 py-2 rounded-md text-[10px] label-caps bg-white/85 text-primary hover:bg-white transition-colors"
                >
                  Explore ideas
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
                    The AI acts as your editor — it checks tonal consistency against your voice
                    profile and scores how well the draft resonates with your intended audience.
                    Every suggestion is grounded in your own writing, not a template.
                  </p>
                </div>
                <div className="glass rounded-xl p-4">
                  <p className="font-headline italic text-[1.05rem] text-secondary mb-4">
                    &ldquo;The scent of old paper and the hum of creation...&rdquo;
                  </p>
                  <div className="space-y-2">
                    <div className="h-1.5 rounded-full bg-surface-container-high w-full" />
                    <div className="h-1.5 rounded-full bg-surface-container-high w-[88%]" />
                    <div className="h-1.5 rounded-full bg-surface-container-high w-[74%]" />
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
                  From analytical deep-dives to punchy contrarian takes — Contendo adapts
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

        {/* ── Testimonials ──────────────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 py-24 bg-background">
          <div className="max-w-[1080px] mx-auto">
            <h2
              className="font-headline text-center mb-3"
              style={{ fontSize: "1.8rem", color: "#2f3333" }}
            >
              Used by people who know what they&apos;re talking about.
            </h2>
            <p
              className="text-secondary text-center mx-auto mb-14"
              style={{ fontSize: "0.95rem", lineHeight: 1.6, maxWidth: "540px" }}
            >
              Not influencers. Researchers, engineers, and designers
              who had things to say and kept procrastinating.
            </p>

            <div className="grid grid-cols-1 md:grid-cols-3 gap-6">
              {[
                {
                  quote:
                    "I do serious AI research but I've always procrastinated on LinkedIn. Contendo pulls from my actual papers and thinking — the posts come out sounding like me, not like a press release.",
                  name: "Subho Majumdar",
                  role: "AI Faculty · IIM Bangalore",
                },
                {
                  quote:
                    "I had months of notes and project work sitting unused. Being able to feed all of it in and get posts that reflect how I actually think about data engineering — that's what got me posting consistently.",
                  name: "Sejal Jagtap",
                  role: "MS Data Science · Duke University",
                },
                {
                  quote:
                    "As a designer I'm particular about voice and detail. What surprised me was how specific the output was — it picked up on my actual opinions, not just generic design advice.",
                  name: "Riddhi Chaudhari",
                  role: "Product Designer · Ex-Dell",
                },
              ].map((t) => (
                <div
                  key={t.name}
                  className="rounded-2xl"
                  style={{
                    background: "#ffffff",
                    padding: "36px",
                    boxShadow:
                      "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)",
                  }}
                >
                  <p
                    className="font-headline italic mb-6"
                    style={{ fontSize: "1.05rem", color: "#2f3333", lineHeight: 1.8 }}
                  >
                    &ldquo;{t.quote}&rdquo;
                  </p>
                  <p
                    className="font-semibold"
                    style={{ fontSize: "0.9rem", color: "#2f3333" }}
                  >
                    {t.name}
                  </p>
                  <p
                    className="mt-1 text-secondary"
                    style={{
                      fontSize: "0.75rem",
                      letterSpacing: "0.04rem",
                      textTransform: "uppercase",
                    }}
                  >
                    {t.role}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Pull quote ────────────────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 py-20 text-center">
          <div className="max-w-[680px] mx-auto">
            <p
              className="font-headline italic"
              style={{ fontSize: "clamp(1.4rem, 3vw, 2rem)", color: "#2f3333", lineHeight: 1.6 }}
            >
              Most AI content sounds like AI wrote it.
              <br />Contendo sounds like you — because it starts
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

            <Link
              href={heroPrimaryCta.href}
              className="btn-primary text-white text-[11px] label-caps rounded-lg px-7 py-3 inline-flex"
            >
              {isLoaded && isSignedIn ? "Open workspace" : "Get started free"}
            </Link>
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
                href="/welcome"
                className="font-headline italic text-on-surface"
                style={{ fontSize: "1.1rem" }}
              >
                Contendo
              </Link>
              <p
                className="mt-2 text-secondary"
                style={{ fontSize: "0.875rem" }}
              >
                A personal writing atelier for builders and researchers.
              </p>
            </div>

            {/* Link groups */}
            <div className="flex flex-col sm:flex-row gap-10 sm:gap-12">

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
                    className="text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    About us
                  </a>
                  <a
                    href="/careers"
                    className="text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Careers
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
                    className="text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    How it works
                  </a>
                  <Link
                    href="/sign-in"
                    className="text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Sign in
                  </Link>
                  <Link
                    href="/first-post"
                    className="text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Get started
                  </Link>
                  <a
                    href="/pricing"
                    className="text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Pricing
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
                  Legal
                </p>
                <div className="flex flex-col gap-2.5">
                  <a
                    href="/privacy-policy"
                    className="text-secondary hover:text-on-surface transition-colors"
                    style={{ fontSize: "0.9rem" }}
                  >
                    Privacy Policy
                  </a>
                  <a
                    href="/terms-of-service"
                    className="text-secondary hover:text-on-surface transition-colors"
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
              © 2026 Contendo. Crafted for the Digital Atelier.
            </p>
          </div>
        </div>
      </footer>

    </div>
  );
}
