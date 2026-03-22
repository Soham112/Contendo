import Link from "next/link";

export default function WelcomePage() {
  return (
    <div className="min-h-[80vh] flex flex-col justify-center space-y-12">
      {/* Hero */}
      <div className="space-y-4 max-w-xl">
        <div className="flex items-center gap-2.5">
          <div className="w-7 h-7 rounded bg-amber flex items-center justify-center shrink-0">
            <svg width="13" height="13" viewBox="0 0 12 12" fill="none" xmlns="http://www.w3.org/2000/svg">
              <path d="M2 9.5L4 3l4 5.5M5.5 7h3" stroke="white" strokeWidth="1.3" strokeLinecap="round" strokeLinejoin="round"/>
            </svg>
          </div>
          <span className="text-sm font-semibold text-text-primary tracking-tight">Contendo</span>
        </div>
        <h1 className="text-3xl font-semibold text-text-primary leading-tight">
          Content that sounds<br />like you wrote it.
        </h1>
        <p className="text-text-secondary text-base leading-relaxed">
          Feed your knowledge base. Generate posts in your voice. Publish without editing.
        </p>
        <div className="flex gap-3 pt-2">
          <Link
            href="/"
            className="rounded-lg bg-text-primary text-card font-medium px-5 py-2.5 text-sm hover:opacity-90 transition-opacity"
          >
            Feed memory
          </Link>
          <Link
            href="/create"
            className="rounded-lg border border-border bg-card text-text-secondary font-medium px-5 py-2.5 text-sm hover:bg-hover hover:text-text-primary transition-colors"
          >
            Create post
          </Link>
        </div>
      </div>

      {/* Feature rows */}
      <div className="grid grid-cols-2 gap-3 max-w-xl">
        {[
          {
            title: "Feed Memory",
            body: "Articles, URLs, PDFs, YouTube transcripts, Obsidian vaults, images. Everything goes in, chunked and embedded.",
            href: "/",
            label: "Open →",
          },
          {
            title: "Library",
            body: "See every source you have ingested. Filter by type, check tags, remove outdated content.",
            href: "/library",
            label: "Open →",
          },
          {
            title: "Create Post",
            body: "Pick a topic, format, and tone. The pipeline retrieves relevant knowledge, drafts, humanizes, and scores.",
            href: "/create",
            label: "Open →",
          },
          {
            title: "History",
            body: "Every generated post is auto-saved with full version history. Restore any version to continue editing.",
            href: "/history",
            label: "Open →",
          },
        ].map((f) => (
          <Link
            key={f.href}
            href={f.href}
            className="rounded-lg border border-border bg-card px-5 py-4 space-y-1.5 hover:bg-stat transition-colors group"
          >
            <div className="flex items-center justify-between">
              <p className="text-sm font-medium text-text-primary">{f.title}</p>
              <span className="text-xs text-text-hint group-hover:text-amber transition-colors">{f.label}</span>
            </div>
            <p className="text-xs text-text-muted leading-relaxed">{f.body}</p>
          </Link>
        ))}
      </div>

      {/* Setup note */}
      <div className="rounded-lg border border-amber-border bg-amber-light px-5 py-4 max-w-xl">
        <p className="text-sm font-medium text-amber">Before you start</p>
        <p className="text-xs text-amber opacity-80 mt-1 leading-relaxed">
          Copy <code className="bg-amber-light font-mono">backend/data/profile.template.json</code> to{" "}
          <code className="bg-amber-light font-mono">backend/data/profile.json</code> and fill in your name, topics,
          opinions, and writing samples. The system writes in your voice — the more specific you are, the better.
        </p>
      </div>
    </div>
  );
}
