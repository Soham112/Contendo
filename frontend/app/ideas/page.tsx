"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";
import { useRouter } from "next/navigation";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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

const FORMAT_LABELS: Record<string, string> = {
  "linkedin post": "LinkedIn post",
  "medium article": "Medium article",
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

// ─── Idea Card ────────────────────────────────────────────────────────────────

function IdeaCard({
  idea,
  isSaved,
  showLeftBorder,
  onUseThis,
  onSave,
  onUnsave,
}: {
  idea: Idea;
  isSaved: boolean;
  showLeftBorder: boolean;
  onUseThis: () => void;
  onSave: () => void;
  onUnsave: () => void;
}) {
  return (
    <div
      style={{
        background: "#ffffff",
        border: "0.5px solid #e0dcd3",
        borderRadius: 10,
        padding: "18px 20px",
        display: "flex",
        justifyContent: "space-between",
        alignItems: "flex-start",
        gap: 20,
        borderLeft: showLeftBorder ? "2px solid #1a1918" : undefined,
      }}
    >
      {/* Left side */}
      <div style={{ flex: 1, minWidth: 0 }}>
        <p
          style={{
            fontSize: 14,
            fontWeight: 500,
            color: "#1a1918",
            lineHeight: 1.45,
            marginBottom: 6,
          }}
        >
          {idea.title}
        </p>
        <p
          style={{
            fontSize: 13,
            color: "#6b6862",
            lineHeight: 1.6,
            marginBottom: 10,
          }}
        >
          {idea.angle}
        </p>
        <div style={{ display: "flex", alignItems: "center", gap: 8, flexWrap: "wrap" }}>
          <span
            style={{
              fontSize: 11,
              borderRadius: 20,
              padding: "3px 10px",
              background: "#eeebe3",
              border: "0.5px solid #e0dcd3",
              color: "#6b6862",
            }}
          >
            {FORMAT_LABELS[idea.format] ?? idea.format}
          </span>
          <span
            style={{
              fontSize: 12,
              color: "#969288",
              fontStyle: "italic",
              lineHeight: 1.5,
            }}
          >
            {idea.reasoning}
          </span>
        </div>
      </div>

      {/* Right side */}
      <div
        style={{
          flexShrink: 0,
          display: "flex",
          flexDirection: "column",
          gap: 8,
          alignItems: "flex-end",
        }}
      >
        <button
          onClick={onUseThis}
          style={{
            background: "#1a1918",
            color: "#ffffff",
            padding: "8px 18px",
            fontSize: 13,
            fontWeight: 500,
            borderRadius: 8,
            border: "none",
            cursor: "pointer",
            whiteSpace: "nowrap",
          }}
          onMouseEnter={(e) => (e.currentTarget.style.opacity = "0.88")}
          onMouseLeave={(e) => (e.currentTarget.style.opacity = "1")}
        >
          Use this
        </button>
        <button
          onClick={isSaved ? onUnsave : onSave}
          style={{
            background: "none",
            border: "none",
            cursor: "pointer",
            fontSize: 12,
            color: isSaved ? "#1a1918" : "#969288",
            padding: 0,
          }}
        >
          {isSaved ? "Saved ✓" : "Save for later"}
        </button>
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function IdeasPage() {
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
      const params = new URLSearchParams({ count: String(count) });
      if (topic.trim()) params.set("topic", topic.trim());
      const res = await fetch(`${API}/suggestions?${params}`);
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

  return (
    <div className="-mx-8 -mt-10 -mb-10 min-h-screen bg-page flex flex-col">
      {/* Topbar */}
      <div
        style={{ borderBottom: "0.5px solid #e0dcd3", height: "52px" }}
        className="flex items-center px-8 bg-page shrink-0"
      >
        <div className="flex items-baseline gap-3">
          <span className="text-[15px] font-semibold text-text-primary tracking-tight">Get ideas</span>
          <span className="text-xs text-text-muted">Find your next post topic</span>
        </div>
      </div>

      {/* Page content */}
      <div className="flex-1 overflow-y-auto">
        <div style={{ maxWidth: 700, margin: "0 auto", padding: "32px 40px" }}>

          {/* Controls row */}
          <div className="flex items-end gap-3 mb-8">
            {/* Topic input */}
            <input
              type="text"
              value={topic}
              onChange={(e) => setTopic(e.target.value)}
              onKeyDown={(e) => e.key === "Enter" && !loading && handleGenerate()}
              placeholder="Any topic in mind? — e.g. 'production ML', 'RAG systems'  (optional)"
              style={{ fontSize: 14, flex: 1 }}
              className="rounded-xl border border-border-subtle bg-card px-4 py-3.5 text-[15px] font-medium text-text-primary shadow-sm focus-within:shadow-md focus-within:border-border transition-all duration-200 placeholder:text-text-hint outline-none"
            />

            {/* Counter */}
            <div className="flex flex-col items-center gap-1">
              <span style={{ fontSize: 11 }} className="text-text-muted">
                How many?
              </span>
              <input
                type="number"
                min={3}
                max={15}
                value={count}
                onChange={(e) =>
                  setCount(Math.min(15, Math.max(3, Number(e.target.value))))
                }
                style={{ width: 80 }}
                className="rounded-xl border border-border-subtle shadow-sm focus:shadow-md focus:border-border transition-all duration-200 bg-card px-3 py-3.5 text-[15px] font-medium text-text-primary outline-none text-center"
              />
            </div>

            {/* Generate button */}
            <button
              onClick={handleGenerate}
              disabled={loading}
              style={{ fontSize: 13.5 }}
              className="rounded-xl bg-amber text-white shadow-float hover:shadow-card-hover hover:-translate-y-0.5 px-6 py-3.5 font-bold tracking-wide transition-all duration-200 disabled:opacity-60 whitespace-nowrap"
            >
              {loading ? "Generating..." : "Generate ideas"}
            </button>
          </div>

          {/* Error */}
          {error && (
            <p
              className="text-score-red mb-6 -mt-4"
              style={{ fontSize: 13 }}
            >
              {error}
            </p>
          )}

          {/* Empty state */}
          {!hasIdeas && !hasSaved && (
            <div
              className="flex flex-col items-center text-center"
              style={{ padding: "60px 0" }}
            >
              <svg
                width="32"
                height="32"
                viewBox="0 0 32 32"
                fill="none"
                xmlns="http://www.w3.org/2000/svg"
                className="text-text-muted"
              >
                <path
                  d="M16 4a8 8 0 0 1 5 14.2V22H11v-3.8A8 8 0 0 1 16 4z"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinejoin="round"
                />
                <path
                  d="M11 24h10M13 27h6"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                />
              </svg>
              <p
                className="font-medium text-text-primary"
                style={{ fontSize: 15, marginTop: 16 }}
              >
                No ideas yet
              </p>
              <p className="text-text-muted" style={{ fontSize: 13, marginTop: 4 }}>
                Enter a topic above and click Generate ideas to get started.
              </p>
            </div>
          )}

          {/* Ideas list */}
          {hasIdeas && (
            <div>
              {/* Section header */}
              <div
                className="flex items-center justify-between"
                style={{ marginBottom: 16 }}
              >
                <div className="flex items-center gap-2">
                  <span
                    className="font-medium text-text-primary"
                    style={{ fontSize: 13 }}
                  >
                    {ideas.length} ideas
                  </span>
                  <span className="text-text-muted" style={{ fontSize: 13 }}>
                    from your knowledge base
                  </span>
                </div>
                <div style={{ fontSize: 12 }} className="text-text-muted">
                  {clearConfirm ? (
                    <span>
                      Clear all ideas?{" "}
                      <button
                        onClick={handleClearAll}
                        className="underline hover:text-text-primary"
                        style={{ marginLeft: 4 }}
                      >
                        Yes
                      </button>
                      {" / "}
                      <button
                        onClick={() => setClearConfirm(false)}
                        className="underline hover:text-text-primary"
                      >
                        No
                      </button>
                    </span>
                  ) : (
                    <button
                      onClick={() => setClearConfirm(true)}
                      className="underline hover:text-text-primary"
                    >
                      Clear all
                    </button>
                  )}
                </div>
              </div>

              {/* Cards */}
              <div className="flex flex-col" style={{ gap: 10 }}>
                {ideas.map((idea, i) => (
                  <IdeaCard
                    key={i}
                    idea={idea}
                    isSaved={savedTitles.has(idea.title)}
                    showLeftBorder={false}
                    onUseThis={() => handleUseThis(idea)}
                    onSave={() => handleSave(idea)}
                    onUnsave={() => handleUnsave(idea)}
                  />
                ))}
              </div>
            </div>
          )}

          {/* Saved ideas subsection */}
          {hasSaved && (
            <div style={{ marginTop: 32 }}>
              <p
                className="text-text-muted uppercase tracking-widest"
                style={{ fontSize: 11, marginBottom: 12 }}
              >
                SAVED
              </p>
              <div className="flex flex-col" style={{ gap: 10 }}>
                {savedIdeas.map((idea, i) => (
                  <IdeaCard
                    key={i}
                    idea={idea}
                    isSaved={true}
                    showLeftBorder={true}
                    onUseThis={() => handleUseThis(idea)}
                    onSave={() => handleSave(idea)}
                    onUnsave={() => handleUnsave(idea)}
                  />
                ))}
              </div>
            </div>
          )}

        </div>
      </div>
    </div>
  );
}
