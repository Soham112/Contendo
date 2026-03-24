import Link from "next/link";

const STEPS = [
  {
    title: "Feed your knowledge",
    description: "Paste articles, YouTube transcripts, PDFs, or raw notes into Contendo. The system chunks and embeds everything into a personal vector memory store — searchable by meaning, not just keywords.",
  },
  {
    title: "Set up your voice profile",
    description: "Fill in your profile once: your role, your opinions, phrases you use, words you avoid, and a few writing samples. This is what separates posts that sound like you from posts that sound like ChatGPT.",
  },
  {
    title: "Generate a draft",
    description: "Pick a topic, format, and tone. Contendo retrieves the most relevant chunks from your memory, feeds them into the draft alongside your voice profile, then runs a humanizer pass to strip AI patterns.",
  },
  {
    title: "Score, refine, publish",
    description: "Every post gets an authenticity score across 5 dimensions. If anything scores low, one click sends targeted feedback to the refiner — which fixes exactly what's flagged, nothing else.",
  },
];

export default function WelcomePage() {
  return (
    <div className="min-h-screen bg-page flex flex-col font-sans">
      {/* Top Navigation */}
      <nav className="h-16 px-6 md:px-12 flex items-center justify-between border-b border-border bg-page/80 backdrop-blur-md sticky top-0 z-50">
        <Link href="/welcome" className="flex items-center gap-2.5 text-base font-bold text-text-primary tracking-tight">
          <div className="w-6 h-6 rounded-md bg-[#e5e3db] flex items-center justify-center">
            <svg width="12" height="12" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 9.5L4 3l4 5.5M5.5 7h3" stroke="#1a1918" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          Contendo
        </Link>

        {/* Center links */}
        <div className="hidden md:flex items-center gap-8 h-full">
          {/* Features Dropdown */}
          <div className="relative group h-full flex items-center">
            <button className="text-sm font-medium text-text-secondary group-hover:text-text-primary transition-colors flex items-center gap-1.5 h-full cursor-pointer focus:outline-none">
              Features
              <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" strokeLinecap="round" strokeLinejoin="round" className="opacity-60 group-hover:rotate-180 transition-transform duration-200">
                <polyline points="6 9 12 15 18 9"></polyline>
              </svg>
            </button>
            <div className="absolute top-[calc(100%-12px)] left-1/2 -translate-x-1/2 w-44 opacity-0 invisible group-hover:opacity-100 group-hover:visible transition-all duration-200 pt-3 z-50">
              <div className="bg-card border border-border-subtle flex flex-col rounded-xl shadow-float overflow-hidden py-1.5">
                <Link href="/" className="px-4 py-2.5 text-[14px] text-text-secondary hover:text-text-primary hover:bg-hover transition-colors font-medium text-center">
                  Feed Memory
                </Link>
                <Link href="/library" className="px-4 py-2.5 text-[14px] text-text-secondary hover:text-text-primary hover:bg-hover transition-colors font-medium border-t border-border-subtle text-center">
                  Library
                </Link>
                <Link href="/create" className="px-4 py-2.5 text-[14px] text-text-secondary hover:text-text-primary hover:bg-hover transition-colors font-medium border-t border-border-subtle text-center">
                  Create Post
                </Link>
                <Link href="/ideas" className="px-4 py-2.5 text-[14px] text-text-secondary hover:text-text-primary hover:bg-hover transition-colors font-medium border-t border-border-subtle text-center">
                  Get Ideas
                </Link>
                <Link href="/history" className="px-4 py-2.5 text-[14px] text-text-secondary hover:text-text-primary hover:bg-hover transition-colors font-medium border-t border-border-subtle text-center">
                  History
                </Link>
              </div>
            </div>
          </div>
          
          <a href="#how-it-works" className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors flex items-center h-full">How it works</a>
          <a href="#" className="text-sm font-medium text-text-secondary hover:text-text-primary transition-colors flex items-center h-full">Pricing</a>
        </div>

        {/* Right buttons */}
        <div className="flex items-center gap-3">
          <Link href="/" className="px-4 py-2 text-sm font-medium text-text-secondary border border-border-input rounded-lg hover:bg-surface hover:text-text-primary transition-colors hidden sm:block">
            Log in
          </Link>
          <Link href="/" className="px-5 py-2 text-sm font-semibold text-white bg-amber rounded-lg hover:opacity-90 transition-opacity shadow-sm">
            Get started free
          </Link>
        </div>
      </nav>

      {/* Main content */}
      <main className="flex-1 px-6 md:px-12 pt-28 pb-16">
        <div className="flex flex-col items-center text-center max-w-4xl mx-auto">
          {/* Eyebrow */}
          <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface border border-border-subtle mb-8">
            <span className="w-1.5 h-1.5 rounded-full bg-text-primary opacity-80" />
            <p className="text-[11px] font-semibold tracking-widest uppercase text-text-secondary">
              Powered by your knowledge
            </p>
          </div>

          {/* H1 */}
          <h1 className="text-5xl md:text-[56px] font-bold text-text-primary leading-[1.12] tracking-tight mb-6 max-w-3xl text-balance">
            Write posts that sound like <span className="italic font-medium text-text-primary">you</span> — not like everyone else
          </h1>

          {/* Subheadline */}
          <p className="text-lg md:text-[19px] text-text-secondary leading-relaxed max-w-2xl mb-12 text-balance font-medium">
            Contendo learns your knowledge base, your voice, and your style. Then it writes content that actually sounds like you wrote it.
          </p>

          {/* CTA buttons */}
          <div className="flex flex-col sm:flex-row items-center gap-4 mb-28 w-full sm:w-auto">
            <Link href="/" className="w-full sm:w-auto px-8 py-4 text-[15px] font-semibold text-white bg-amber rounded-xl hover:opacity-90 transition-all shadow-float hover:shadow-card-hover hover:-translate-y-0.5">
              Start writing for free
            </Link>
            <a href="#how-it-works" className="w-full sm:w-auto px-8 py-4 text-[15px] font-semibold text-text-primary bg-surface border border-border-input rounded-xl hover:bg-hover hover:border-border transition-colors">
              See how it works
            </a>
          </div>

          {/* Feature cards */}
          <div id="features" className="grid grid-cols-1 md:grid-cols-3 gap-6 w-full">
            {/* Card 1 */}
            <div className="text-left p-8 bg-card rounded-2xl border border-border-subtle shadow-card hover:shadow-card-hover transition-all duration-300">
              <div className="w-11 h-11 rounded-xl bg-surface border border-border-subtle flex items-center justify-center mb-6">
                <svg width="20" height="20" viewBox="0 0 16 16" fill="none">
                  <rect x="8" y="1.5" width="7.5" height="7.5" rx="1.5" transform="rotate(45 8 1.5)" stroke="#1a1918" strokeWidth="1.5"/>
                </svg>
              </div>
              <h3 className="text-[17px] font-bold text-text-primary mb-3">Feed your knowledge</h3>
              <p className="text-[15px] text-text-secondary leading-relaxed">Articles, notes, YouTube videos, PDFs — anything you've read becomes fuel for your posts.</p>
            </div>

            {/* Card 2 */}
            <div className="text-left p-8 bg-card rounded-2xl border border-border-subtle shadow-card hover:shadow-card-hover transition-all duration-300">
              <div className="w-11 h-11 rounded-xl bg-surface border border-border-subtle flex items-center justify-center mb-6">
                <svg width="20" height="20" viewBox="0 0 16 16" fill="none">
                  <path d="M8 1.5L9.4 6.6L14.5 8L9.4 9.4L8 14.5L6.6 9.4L1.5 8L6.6 6.6L8 1.5Z" stroke="#1a1918" strokeWidth="1.5" strokeLinejoin="round"/>
                </svg>
              </div>
              <h3 className="text-[17px] font-bold text-text-primary mb-3">Generate in your voice</h3>
              <p className="text-[15px] text-text-secondary leading-relaxed">The AI learns your writing style, your opinions, and your phrases — then drafts in your exact voice.</p>
            </div>

            {/* Card 3 */}
            <div className="text-left p-8 bg-card rounded-2xl border border-border-subtle shadow-card hover:shadow-card-hover transition-all duration-300">
              <div className="w-11 h-11 rounded-xl bg-surface border border-border-subtle flex items-center justify-center mb-6">
                <svg width="20" height="20" viewBox="0 0 16 16" fill="none">
                  <circle cx="8" cy="8" r="5.5" stroke="#1a1918" strokeWidth="1.5"/>
                  <path d="M8 5V8.2L10 10" stroke="#1a1918" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <h3 className="text-[17px] font-bold text-text-primary mb-3">Score and refine</h3>
              <p className="text-[15px] text-text-secondary leading-relaxed">Every post gets an authenticity score. One-click refinement fixes what the AI flags before you publish.</p>
            </div>
          </div>
        </div>
      </main>

      {/* How it works */}
      <section id="how-it-works" className="bg-surface border-y border-border py-28 px-6 md:px-12">
        <div className="max-w-4xl mx-auto">
          <div className="text-center mb-20">
            <h2 className="text-3xl md:text-[34px] font-bold text-text-primary tracking-tight mb-4">From raw knowledge to published post</h2>
            <p className="text-[17px] font-medium text-text-secondary">Four steps. No templates. No generic output.</p>
          </div>

          <div className="max-w-[680px] mx-auto space-y-12">
            {STEPS.map((step, i) => (
              <div key={i} className="flex gap-7 relative group">
                {/* Number */}
                <div className="relative shrink-0 z-10 pt-1">
                  <div className="w-10 h-10 rounded-full bg-card border border-border shadow-sm flex items-center justify-center text-[15px] font-bold text-text-primary group-hover:border-text-primary transition-colors">
                    {i + 1}
                  </div>
                  {/* Line */}
                  {i < STEPS.length - 1 && (
                    <div className="absolute top-[52px] left-1/2 -ml-[1px] h-[calc(100%+16px)] w-[2px] bg-border" />
                  )}
                </div>
                {/* Content */}
                <div className="pt-2 pb-6">
                  <h3 className="text-[19px] font-bold text-text-primary mb-2.5">{step.title}</h3>
                  <p className="text-text-secondary leading-relaxed text-[16px] max-w-xl">{step.description}</p>
                </div>
              </div>
            ))}
          </div>
        </div>
      </section>

      {/* Footer */}
      <footer className="bg-page py-10 px-6 md:px-12 flex flex-col sm:flex-row items-center justify-between gap-6 border-t border-border">
        <p className="text-[14px] font-medium text-text-muted">© 2026 Contendo. Built for creators who think in public.</p>
        <div className="flex items-center gap-8">
          <a href="#" className="text-[14px] font-medium text-text-muted hover:text-text-primary transition-colors">Privacy</a>
          <a href="#" className="text-[14px] font-medium text-text-muted hover:text-text-primary transition-colors">Terms</a>
        </div>
      </footer>
    </div>
  );
}
