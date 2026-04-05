"use client";

import Link from "next/link";
import { FormEvent, useMemo, useState } from "react";
import { useRouter } from "next/navigation";
import { useUser } from "@clerk/nextjs";

const MOOD_GRADIENTS = [
  { label: "Analytical",   from: "#3a4a35", to: "#58614f" },
  { label: "Poetic",       from: "#6b5b4e", to: "#8a7060" },
  { label: "Technical",    from: "#2c3e50", to: "#4a6741" },
  { label: "Narrative",    from: "#5c4a3a", to: "#7a6550" },
  { label: "Contrarian",   from: "#3d3d3d", to: "#5a5a5a" },
  { label: "Visionary",    from: "#4a3f5c", to: "#6b5b7a" },
  { label: "Reflective",   from: "#4a5c4a", to: "#6b8a6b" },
  { label: "Direct",       from: "#5c4a2a", to: "#8a7040" },
];

const HERO_DRAFT_KEY = "contentOS_last_topic";
const SHARED_TOPIC_KEY = "contendo_topic";

function TopNav({ isSignedIn, isLoaded }: { isSignedIn: boolean; isLoaded: boolean }) {
  return (
    <nav className="sticky top-0 z-50 bg-background/80 backdrop-blur-md">
      <div className="max-w-[1200px] mx-auto px-5 sm:px-8 py-4 flex items-center justify-between">
        <Link href="/welcome" className="font-headline italic text-on-surface text-xl tracking-tight">
          Contendo
        </Link>

        <div className="hidden md:flex items-center gap-8">
          <a
            href="#how-it-works"
            className="label-caps text-[10px] text-secondary hover:text-on-surface transition-colors"
          >
            How it works
          </a>
        </div>

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

  const heroPrimaryCta = useMemo(() => {
    if (isLoaded && isSignedIn) {
      return { href: "/", label: "Open workspace" };
    }
    return { href: "/first-post", label: "Write your first post" };
  }, [isLoaded, isSignedIn]);

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

  return (
    <div className="min-h-screen bg-background text-on-surface font-sans">
      <TopNav isSignedIn={!!isSignedIn} isLoaded={!!isLoaded} />

      <main>

        {/* ── Hero ──────────────────────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 pt-14 sm:pt-20 pb-16 sm:pb-20 text-center">
          <div className="max-w-[980px] mx-auto">
            <h1
              className="font-headline leading-[1.12] tracking-tight mb-5"
              style={{ fontSize: "clamp(2.2rem, 5vw, 3.2rem)", color: "#2f3333" }}
            >
              Finally, a LinkedIn post that sounds like you wrote it.
            </h1>
            <p
              className="mb-9 max-w-[640px] mx-auto text-secondary"
              style={{ fontSize: "1.1rem", lineHeight: 1.6 }}
            >
              Feed it your notes, articles, and opinions. Get posts that reflect your actual
              voice — not generic AI filler.
            </p>

            <form
              onSubmit={handleHeroSubmit}
              className="max-w-[760px] mx-auto rounded-xl flex flex-col sm:flex-row gap-2 sm:items-center"
              style={{
                background: "#ffffff",
                border: "1px solid rgba(174, 179, 178, 0.15)",
                padding: "8px 8px 8px 16px",
              }}
              aria-label="Start your first post"
            >
              <input
                value={topicInput}
                onChange={(event) => {
                  setTopicInput(event.target.value);
                  if (showInputError && event.target.value.trim()) {
                    setShowInputError(false);
                  }
                }}
                placeholder="What do you want to write about today?"
                className="flex-1 bg-transparent text-[14px] sm:text-[13px] text-on-surface placeholder:text-outline focus:outline-none py-1.5"
                aria-label="Topic prompt"
              />
              <button
                type="submit"
                className="btn-primary text-white text-[11px] label-caps rounded-lg px-5 py-3 sm:py-2.5 whitespace-nowrap"
              >
                Start Writing
              </button>
            </form>
            {showInputError && (
              <p className="mt-2 text-[12px] text-secondary/80">Add a topic first to continue.</p>
            )}
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

        {/* ── Philosophy ────────────────────────────────────────────────────── */}
        <section id="atelier" className="px-5 sm:px-8 py-16 sm:py-24">
          <div className="max-w-[1080px] mx-auto grid md:grid-cols-[1fr_1.05fr] gap-8 items-center">
            <div className="rounded-2xl bg-surface-container overflow-hidden shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] p-3">
              <div className="rounded-xl h-[250px] sm:h-[320px] bg-[linear-gradient(145deg,#233131_0%,#50695f_55%,#d8b486_100%)] relative overflow-hidden">
                <div className="absolute left-5 bottom-5 w-16 h-1.5 bg-white/70 rounded-full" />
                <div className="absolute left-5 bottom-9 w-24 h-1.5 bg-white/45 rounded-full" />
                <div className="absolute right-8 top-8 w-14 h-14 rounded-full bg-[#f4debe]/70 blur-sm" />
              </div>
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

        {/* ── Craftsman's Toolkit ───────────────────────────────────────────── */}
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

        {/* ── Mood grid ─────────────────────────────────────────────────────── */}
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
                  style={{
                    minHeight: 160,
                    background: `linear-gradient(135deg, ${tile.from} 0%, ${tile.to} 100%)`,
                  }}
                >
                  <span className="font-headline italic text-white" style={{ fontSize: "1rem" }}>
                    {tile.label}
                  </span>
                </div>
              ))}
            </div>
          </div>
        </section>

        {/* ── Final CTA ─────────────────────────────────────────────────────── */}
        <section className="px-5 sm:px-8 py-20 sm:py-28 text-center bg-surface-container-low">
          <div className="max-w-[780px] mx-auto">
            <h2 className="font-headline text-[2.5rem] sm:text-[4rem] leading-[1.05] mb-4">
              Craft Your Legacy
            </h2>
            <p className="text-[13px] text-secondary max-w-[540px] mx-auto mb-8">
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

      <footer className="px-5 sm:px-8 py-8 bg-background">
        <div className="max-w-[1200px] mx-auto flex flex-col md:flex-row gap-4 md:items-center md:justify-between">
          <div>
            <Link href="/welcome" className="font-headline italic text-[1.05rem]">Contendo</Link>
            <p className="mt-1 text-[10px] label-caps text-outline">© 2026 Contendo. Crafted for the Digital Atelier.</p>
          </div>

          <div className="flex gap-5 text-[10px] label-caps text-secondary">
            <a href="#" className="hover:text-on-surface transition-colors">Privacy policy</a>
            <a href="#" className="hover:text-on-surface transition-colors">Terms of service</a>
            <a href="#" className="hover:text-on-surface transition-colors">Journal</a>
            <a href="#" className="hover:text-on-surface transition-colors">Contact</a>
          </div>

          <div className="flex items-center gap-2 text-secondary">
            <button className="w-8 h-8 rounded-lg ghost-border hover:bg-surface-container-low transition-colors" aria-label="Visit social profile" />
            <button className="w-8 h-8 rounded-lg ghost-border hover:bg-surface-container-low transition-colors" aria-label="Email us" />
          </div>
        </div>
      </footer>
    </div>
  );
}
