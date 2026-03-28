"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";

const LS_IDEAS = "contendo_ideas";
const LS_SAVED = "contendo_saved_ideas";
const LS_TOPIC = "contendo_ideas_topic";
const LS_COUNT = "contendo_ideas_count";

interface Idea {
  title: string;
  angle: string;
  format: string;
  reasoning: string;
}

// Display badge labels for format (uppercase pill)
const FORMAT_BADGE: Record<string, string> = {
  "linkedin post": "LinkedIn Post",
  "medium article": "Feature Story",
  thread: "Thread",
};

function lsGet(key: string): string | null {
  try { return localStorage.getItem(key); } catch { return null; }
}
function lsSet(key: string, value: string): void {
  try { localStorage.setItem(key, value); } catch { /* ignore */ }
}
function lsRemove(key: string): void {
  try { localStorage.removeItem(key); } catch { /* ignore */ }
}

// ─── Idea Grid Card ───────────────────────────────────────────────────────────

function IdeaCard({
  idea,
  isSaved,
  onUseThis,
  onSave,
  onUnsave,
}: {
  idea: Idea;
  isSaved: boolean;
  onUseThis: () => void;
  onSave: () => void;
  onUnsave: () => void;
}) {
  const badge = FORMAT_BADGE[idea.format] ?? idea.format;

  return (
    <div className="bg-surface-container-lowest rounded-xl flex flex-col gap-3 p-5 shadow-card hover:bg-surface-container-low transition-all duration-200">
      {/* Top row: badge + three-dot menu */}
      <div className="flex items-start justify-between gap-2">
        <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2 py-0.5 rounded-full bg-surface-container border border-surface-container-high text-outline">
          {badge}
        </span>
        <button className="w-6 h-6 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors shrink-0">
          <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="text-outline-variant">
            <circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>
          </svg>
        </button>
      </div>

      {/* Title */}
      <p className="font-headline text-[15px] text-on-surface leading-snug font-semibold flex-1">
        {idea.title}
      </p>

      {/* Angle/description */}
      <p className="text-[12.5px] text-secondary leading-relaxed">
        {idea.angle}
      </p>

      {/* Action row */}
      <div className="flex gap-2 mt-1">
        <button
          onClick={isSaved ? onUnsave : onSave}
          className={`flex-1 rounded-lg border text-[12px] font-medium py-2 transition-colors ${
            isSaved
              ? "border-primary/30 text-primary bg-surface-container-low"
              : "border-surface-container-high text-secondary hover:text-on-surface hover:border-outline-variant bg-surface-container-lowest"
          }`}
        >
          {isSaved ? "Saved ✓" : "Save for Later"}
        </button>
        <button
          onClick={onUseThis}
          className="flex-1 btn-primary text-white rounded-lg text-[12px] font-semibold py-2 hover:opacity-90 transition-opacity"
        >
          Use This
        </button>
      </div>
    </div>
  );
}

// ─── Curated Archive Row ──────────────────────────────────────────────────────

function ArchiveRow({
  idea,
  onUseThis,
  onUnsave,
}: {
  idea: Idea;
  onUseThis: () => void;
  onUnsave: () => void;
}) {
  const badge = FORMAT_BADGE[idea.format] ?? idea.format;

  return (
    <div className="flex items-center gap-4 py-3.5 group">
      {/* Left color tile */}
      <div className="w-9 h-9 rounded-lg bg-primary/10 flex items-center justify-center shrink-0">
        <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-primary">
          <path d="M12 20h9"/><path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4 12.5-12.5z"/>
        </svg>
      </div>

      {/* Text */}
      <div className="flex-1 min-w-0">
        <p className="label-caps text-outline mb-0.5">{badge}</p>
        <p className="text-[13.5px] font-medium text-on-surface leading-snug truncate">{idea.title}</p>
      </div>

      {/* Right: timestamp + actions */}
      <div className="flex items-center gap-3 shrink-0">
        <span className="text-[11px] text-outline-variant hidden md:block">Saved recently</span>

        {/* Trash */}
        <button
          onClick={onUnsave}
          className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-error/10 transition-colors opacity-0 group-hover:opacity-100"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-error">
            <polyline points="3 6 5 6 21 6"/><path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/><path d="M10 11v6M14 11v6"/><path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        </button>

        {/* Arrow (use this) */}
        <button
          onClick={onUseThis}
          className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-surface-container-high transition-colors"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-secondary group-hover:text-on-surface transition-colors">
            <line x1="5" y1="12" x2="19" y2="12"/><polyline points="12 5 19 12 12 19"/>
          </svg>
        </button>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IdeasPage() {
  const api = useApi();
  const router = useRouter();

  const [ideas, setIdeas] = useState<Idea[]>([]);
  const [savedIdeas, setSavedIdeas] = useState<Idea[]>([]);
  const [savedTitles, setSavedTitles] = useState<Set<string>>(new Set());
  const [topic, setTopic] = useState("");
  const [count, setCount] = useState(8);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [clearConfirm, setClearConfirm] = useState(false);
  const { showToast } = useToast();

  // Restore from localStorage on mount
  useEffect(() => {
    const ideasStr = lsGet(LS_IDEAS);
    if (ideasStr) {
      try { setIdeas(JSON.parse(ideasStr)); } catch { /* ignore */ }
    }
    const topicStr = lsGet(LS_TOPIC);
    if (topicStr) setTopic(topicStr);
    const countStr = lsGet(LS_COUNT);
    if (countStr) setCount(parseInt(countStr));
    const savedStr = lsGet(LS_SAVED);
    if (savedStr) {
      try {
        const parsed: Idea[] = JSON.parse(savedStr);
        setSavedIdeas(parsed);
        setSavedTitles(new Set(parsed.map((i) => i.title)));
      } catch { /* ignore */ }
    }
  }, []);

  const handleGenerate = async () => {
    setLoading(true);
    setError("");
    try {
      const res = await api.getSuggestions(count, topic.trim() || undefined);
      if (!res.ok) throw new Error("Failed");
      const data = await res.json();
      const newIdeas: Idea[] = data.suggestions ?? [];
      setIdeas(newIdeas);
      showToast(`Generated ${newIdeas.length} ideas`, "success");
      lsSet(LS_IDEAS, JSON.stringify(newIdeas));
      lsSet(LS_TOPIC, topic);
      lsSet(LS_COUNT, String(count));
    } catch {
      setError("Couldn't load ideas — check that the backend is running and try again.");
      showToast("Failed to generate ideas", "error");
    } finally {
      setLoading(false);
    }
  };

  const handleSave = (idea: Idea) => {
    const current: Idea[] = JSON.parse(lsGet(LS_SAVED) || "[]");
    const updated = [...current, idea];
    lsSet(LS_SAVED, JSON.stringify(updated));
    setSavedIdeas(updated);
    setSavedTitles(new Set(updated.map((i) => i.title)));
    showToast("Idea saved to pinned list", "success");
  };

  const handleUnsave = (idea: Idea) => {
    const updated = savedIdeas.filter((s) => s.title !== idea.title);
    lsSet(LS_SAVED, JSON.stringify(updated));
    setSavedIdeas(updated);
    setSavedTitles(new Set(updated.map((i) => i.title)));
    showToast("Idea removed from pinned list", "info");
  };

  const handleClearAll = () => {
    lsRemove(LS_IDEAS);
    setIdeas([]);
    setClearConfirm(false);
  };

  const handleUseThis = (idea: Idea) => {
    try {
      sessionStorage.setItem("contentOS_last_topic", idea.title);
      sessionStorage.setItem("contentOS_prefill_format", idea.format);
    } catch { /* ignore */ }
    router.push("/create");
  };

  const hasIdeas = ideas.length > 0;
  const hasSaved = savedIdeas.length > 0;

  const COUNT_OPTIONS = [3, 5, 10];

  return (
    <div className="-mx-10 -mt-10 -mb-10 min-h-screen bg-background flex flex-col">

      {/* ── Top header bar ───────────────────────────────────────────────── */}
      <div
        style={{ borderBottom: "0.5px solid #dfe3e2", height: "56px" }}
        className="flex items-center px-10 bg-background shrink-0 gap-4"
      >
        <div className="flex-1" />

        {/* Search */}
        <div className="relative w-56">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-outline-variant" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            placeholder="Search Atelier..."
            className="w-full pl-8 pr-3 py-1.5 text-[12px] bg-surface-container-low rounded-full border border-surface-container-high focus:outline-none focus:border-outline-variant transition-all text-on-surface placeholder:text-outline-variant"
          />
        </div>

        {/* Bell */}
        <button className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-outline">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/><path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
        </button>

        {/* Avatar */}
        <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center">
          <span className="text-[10px] font-bold text-white">U</span>
        </div>
      </div>

      {/* ── Scrollable content ────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-10 py-10">

        {/* Breadcrumb */}
        <p className="label-caps text-outline mb-8">Workspace / Ideation</p>

        {/* ── Hero + Controls two-column row ─────────────────────────────── */}
        <div className="flex gap-10 mb-12 items-start">

          {/* Left: hero text (~55%) */}
          <div className="flex-1 min-w-0">
            <h1 className="font-headline text-[3rem] text-on-surface leading-[1.1] mb-4">
              Ignite your next<br />
              <em>literary masterpiece.</em>
            </h1>
            <p className="text-secondary text-[15px] leading-relaxed max-w-md">
              Input a theme or leave it to chance. Our atelier synthesizes global trends with your unique editorial voice.
            </p>
          </div>

          {/* Right: controls card (~45%) */}
          <div className="w-[400px] shrink-0 bg-surface-container-lowest rounded-2xl shadow-card p-6 flex flex-col gap-5">

            {/* Topic input */}
            <div>
              <label className="label-caps text-secondary block mb-2">Topic Filter (Optional)</label>
              <input
                type="text"
                value={topic}
                onChange={(e) => setTopic(e.target.value)}
                onKeyDown={(e) => e.key === "Enter" && !loading && handleGenerate()}
                placeholder="e.g. Minimalist Architecture, French..."
                className="input-editorial w-full px-0 py-2 text-[14px] font-medium text-on-surface placeholder:text-outline-variant focus:outline-none"
              />
            </div>

            {/* Count pills */}
            <div>
              <label className="label-caps text-secondary block mb-2">Idea Count</label>
              <div className="flex gap-2">
                {COUNT_OPTIONS.map((n) => (
                  <button
                    key={n}
                    onClick={() => setCount(n)}
                    className={`flex-1 py-2 rounded-full text-[13px] font-semibold transition-all duration-200 ${
                      count === n
                        ? "btn-primary text-white shadow-card"
                        : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
                    }`}
                  >
                    {n}
                  </button>
                ))}
              </div>
            </div>

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={loading}
              className="btn-primary w-full rounded-xl text-white text-[13px] font-bold tracking-widest uppercase py-3.5 hover:opacity-90 disabled:opacity-60 disabled:cursor-not-allowed shadow-card hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-200 flex items-center justify-center gap-2"
            >
              <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>
                <path d="M5 3l.5 2L7 6l-1.5.5L5 9l-.5-2.5L3 6l1.5-.5z"/>
              </svg>
              {loading ? "Generating..." : "Generate Ideas"}
            </button>

            {error && <p className="text-error text-xs -mt-2">{error}</p>}
          </div>
        </div>

        {/* ── Generated ideas grid ───────────────────────────────────────── */}
        {hasIdeas && (
          <div className="mb-12">
            {/* Section header */}
            <div className="flex items-baseline justify-between mb-5">
              <h2 className="font-headline text-2xl text-on-surface">Fresh Concepts</h2>
              <div className="flex items-center gap-4">
                <span className="label-caps text-outline">{ideas.length} Results Found</span>
                {clearConfirm ? (
                  <span className="text-xs text-outline">
                    Clear all?{" "}
                    <button onClick={handleClearAll} className="underline hover:text-on-surface">Yes</button>
                    {" / "}
                    <button onClick={() => setClearConfirm(false)} className="underline hover:text-on-surface">No</button>
                  </span>
                ) : (
                  <button onClick={() => setClearConfirm(true)} className="text-xs text-outline-variant hover:text-outline transition-colors underline">
                    Clear all
                  </button>
                )}
              </div>
            </div>

            <div className="grid grid-cols-3 gap-4">
              {ideas.map((idea, i) => (
                <IdeaCard
                  key={i}
                  idea={idea}
                  isSaved={savedTitles.has(idea.title)}
                  onUseThis={() => handleUseThis(idea)}
                  onSave={() => handleSave(idea)}
                  onUnsave={() => handleUnsave(idea)}
                />
              ))}
            </div>
          </div>
        )}

        {/* ── Empty state ────────────────────────────────────────────────── */}
        {!hasIdeas && !loading && (
          <div className="flex flex-col items-center text-center py-12 gap-3">
            <svg width="36" height="36" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round" className="text-outline-variant">
              <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>
            </svg>
            <p className="font-headline text-xl text-on-surface">No ideas yet</p>
            <p className="text-outline text-sm max-w-xs">Configure your filters above and hit Generate Ideas to spark your next piece.</p>
          </div>
        )}

        {/* ── Curated Archive ────────────────────────────────────────────── */}
        {hasSaved && (
          <div>
            {/* Section header */}
            <div className="flex items-center gap-3 mb-1">
              <span className="text-lg">📚</span>
              <h2 className="font-headline text-2xl text-on-surface">Curated Archive</h2>
            </div>
            <div className="h-px bg-surface-container-high mb-4" />

            {/* Archive rows */}
            <div className="divide-y divide-surface-container-high">
              {savedIdeas.map((idea, i) => (
                <ArchiveRow
                  key={i}
                  idea={idea}
                  onUseThis={() => handleUseThis(idea)}
                  onUnsave={() => handleUnsave(idea)}
                />
              ))}
            </div>

            {/* View full library link */}
            <div className="flex justify-center mt-6">
              <button
                onClick={() => router.push("/library")}
                className="label-caps text-outline hover:text-secondary transition-colors"
              >
                View Full Library »
              </button>
            </div>
          </div>
        )}
      </div>

      {/* ── Floating action button ────────────────────────────────────────── */}
      <button
        onClick={handleGenerate}
        disabled={loading}
        className="fixed bottom-8 right-8 w-14 h-14 rounded-full btn-primary shadow-card hover:shadow-card-hover hover:-translate-y-0.5 flex items-center justify-center transition-all duration-200 disabled:opacity-60 z-20"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
          <path d="M19 21l-7-5-7 5V5a2 2 0 0 1 2-2h10a2 2 0 0 1 2 2z"/>
        </svg>
      </button>
    </div>
  );
}
