"use client";

import { useEffect, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const SS_POST = "contentOS_last_post";
const SS_SCORE = "contentOS_last_score";
const SS_FEEDBACK = "contentOS_last_feedback";
const SS_ITERATIONS = "contentOS_last_iterations";
const SS_VISUALS = "contentOS_last_visuals";
const SS_CURRENT_POST_ID = "contentOS_current_post_id";

interface Diagram {
  position: number;
  description: string;
  svg_code: string;
}

interface Version {
  id: number;
  post_id: number;
  version_number: number;
  content: string;
  authenticity_score: number | null;
  version_type: "generated" | "refined";
  created_at: string;
  svg_diagrams: Diagram[] | null;
}

interface Post {
  id: number;
  created_at: string;
  topic: string;
  format: string;
  tone: string;
  content: string;
  authenticity_score: number;
  svg_diagrams: Diagram[] | null;
  versions: Version[];
}

function svgToDataURL(svgCode: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgCode, "image/svg+xml");
    const svgEl = doc.querySelector("svg");
    const viewBox = svgEl?.getAttribute("viewBox") ?? "0 0 680 400";
    const parts = viewBox.split(/[\s,]+/);
    const vbW = parseFloat(parts[2]) || 680;
    const vbH = parseFloat(parts[3]) || 400;

    const canvas = document.createElement("canvas");
    canvas.width = vbW * 2;
    canvas.height = vbH * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) { reject(new Error("No canvas context")); return; }

    const img = new Image();
    const blob = new Blob([svgCode], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);

    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Image load failed")); };
    img.src = url;
  });
}

function HistoryDiagramCard({ diagram }: { diagram: Diagram }) {
  const [pngState, setPngState] = useState<"idle" | "opened" | "blocked">("idle");
  const [fallbackDataURL, setFallbackDataURL] = useState<string | null>(null);

  const handleOpen = async () => {
    try {
      const dataURL = await svgToDataURL(diagram.svg_code);
      const win = window.open();
      if (win) {
        win.document.write(
          `<html><body style="margin:0;background:#faf9f8;display:flex;justify-content:center;padding:24px">` +
          `<img src="${dataURL}" style="max-width:100%;border-radius:8px" />` +
          `</body></html>`
        );
        win.document.close();
        setPngState("opened");
        setTimeout(() => setPngState("idle"), 5000);
      } else {
        setFallbackDataURL(dataURL);
        setPngState("blocked");
      }
    } catch {
      // conversion failed
    }
  };

  return (
    <div className="rounded-xl bg-surface-container overflow-hidden">
      <div className="px-4 py-2.5 border-b border-surface-container-high">
        <p className="text-xs font-medium text-secondary">
          Diagram —{" "}
          <span className="font-normal text-outline">
            {diagram.description.length > 60
              ? diagram.description.slice(0, 60) + "…"
              : diagram.description}
          </span>
        </p>
      </div>
      <div className="p-3 overflow-x-auto" dangerouslySetInnerHTML={{ __html: diagram.svg_code }} />
      <div className="px-4 py-2.5 border-t border-surface-container-high space-y-2">
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpen}
            className="text-xs border border-surface-container-high rounded-lg px-3 py-1.5 text-secondary hover:border-outline-variant hover:text-on-surface transition-colors"
          >
            Open as PNG
          </button>
          {pngState === "opened" && (
            <span className="text-xs text-outline">PNG opened — right-click and <strong>Save Image</strong></span>
          )}
          {pngState === "blocked" && (
            <span className="text-xs text-outline">Popup blocked — right-click image below to save</span>
          )}
        </div>
        {pngState === "blocked" && fallbackDataURL && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={fallbackDataURL} alt="diagram PNG" className="max-w-full rounded-lg border border-surface-container-high" />
        )}
      </div>
    </div>
  );
}

const FORMAT_LABELS: Record<string, string> = {
  "linkedin post": "LinkedIn",
  "medium article": "Medium",
  "thread": "Thread",
};

const TONE_LABELS: Record<string, string> = {
  "casual": "Casual",
  "technical": "Technical",
  "storytelling": "Storytelling",
};

function bestVersionIndex(versions: Version[]): number {
  let best = 0;
  for (let i = 1; i < versions.length; i++) {
    const a = versions[i].authenticity_score ?? -1;
    const b = versions[best].authenticity_score ?? -1;
    if (a > b) best = i;
  }
  return best;
}

function scoreColor(score: number | null): string {
  if (score === null) return "#777c7b";
  if (score >= 80) return "#58614f";
  if (score >= 60) return "#645e57";
  return "#777c7b";
}

// ─── Post Card ────────────────────────────────────────────────────────────────

function PostCard({
  post,
  onDelete,
  confirmingId,
  setConfirmingId,
  isExpanded,
  onToggle,
}: {
  post: Post;
  onDelete: (id: number) => void;
  confirmingId: number | null;
  setConfirmingId: (id: number | null) => void;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const hasVersions = post.versions.length > 1;
  const defaultIdx = hasVersions ? bestVersionIndex(post.versions) : 0;
  const [selectedVersionIdx, setSelectedVersionIdx] = useState(defaultIdx);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoredMsg, setRestoredMsg] = useState("");
  const { showToast } = useToast();

  const isConfirming = confirmingId === post.id;

  const activeVersion = hasVersions ? post.versions[selectedVersionIdx] : null;
  const activeContent = activeVersion ? activeVersion.content : post.content;
  const activeScore = activeVersion ? activeVersion.authenticity_score : post.authenticity_score;
  const activeDiagrams = activeVersion ? (activeVersion.svg_diagrams ?? null) : post.svg_diagrams;
  const bestIdx = hasVersions ? bestVersionIndex(post.versions) : 0;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(activeContent);
    setCopied(true);
    showToast("Post content copied", "success");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await fetch(`${API}/history/${post.id}`, { method: "DELETE" });
      onDelete(post.id);
      showToast("Post deleted from history", "success");
    } catch {
      setDeleting(false);
      setConfirmingId(null);
      showToast("Failed to delete post", "error");
    }
  };

  const handleRestore = async () => {
    if (!activeVersion) return;
    setRestoring(true);
    setRestoredMsg("");
    try {
      const res = await fetch(`${API}/history/${post.id}/restore/${activeVersion.id}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Restore failed");
      const data = await res.json();
      try {
        sessionStorage.setItem(SS_POST, data.content);
        sessionStorage.setItem(SS_SCORE, String(data.authenticity_score ?? 0));
        sessionStorage.setItem(SS_FEEDBACK, JSON.stringify([]));
        sessionStorage.setItem(SS_ITERATIONS, "1");
        sessionStorage.setItem(SS_VISUALS, JSON.stringify([]));
        sessionStorage.setItem(SS_CURRENT_POST_ID, String(post.id));
      } catch {
        // ignore
      }
      setRestoredMsg(`v${data.version_number} restored — go to Create Post to edit and repost`);
      showToast(`v${data.version_number} restored to Create Post`, "info");
    } catch {
      setRestoredMsg("Restore failed. Please try again.");
      showToast("Restore failed", "error");
    } finally {
      setRestoring(false);
    }
  };

  const date = new Date(post.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  const displayScore = activeScore ?? post.authenticity_score ?? null;

  // Collapsed card
  if (!isExpanded) {
    return (
      <div
        className="bg-surface-container-lowest rounded-xl px-6 py-5 cursor-pointer hover:bg-surface-container transition-colors duration-200"
        style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)" }}
        onClick={onToggle}
      >
        <div className="flex items-center gap-3">
          {/* Badges */}
          <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full bg-primary/10 text-primary">
            {FORMAT_LABELS[post.format] ?? post.format}
          </span>
          <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full bg-secondary/10 text-secondary">
            {TONE_LABELS[post.tone] ?? post.tone}
          </span>
          <span className="text-[11px] text-outline-variant ml-1">{date}</span>

          <div className="flex-1 min-w-0 ml-2">
            <p className="text-[13px] font-medium text-on-surface truncate">{post.topic}</p>
          </div>

          {/* Score + chevron */}
          <div className="flex items-center gap-3 shrink-0">
            {displayScore !== null && (
              <span className="font-headline text-xl font-semibold" style={{ color: scoreColor(displayScore) }}>
                {displayScore}
              </span>
            )}
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-outline-variant">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
        </div>

        {/* 2-line preview with fade */}
        <div className="relative mt-2 pl-1 overflow-hidden" style={{ maxHeight: "2.8em" }}>
          <p className="text-[12.5px] text-outline leading-relaxed line-clamp-2 whitespace-pre-wrap">
            {activeContent}
          </p>
          <div className="absolute bottom-0 left-0 right-0 h-5 bg-gradient-to-t from-surface-container-lowest to-transparent pointer-events-none" />
        </div>
      </div>
    );
  }

  // Expanded card
  return (
    <div
      className="bg-surface-container-lowest rounded-xl overflow-hidden"
      style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)" }}
    >
      {/* ── Card header ─────────────────────────────────────────────────── */}
      <div className="px-6 pt-6 pb-4">

        {/* Row 1: badges + date + score + three-dot */}
        <div className="flex items-center gap-2 mb-4">
          <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full bg-primary/10 text-primary">
            {FORMAT_LABELS[post.format] ?? post.format}
          </span>
          <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full bg-secondary/10 text-secondary">
            {TONE_LABELS[post.tone] ?? post.tone}
          </span>
          <span className="text-[11px] text-outline-variant ml-1">{date}</span>

          <div className="flex-1" />

          {/* Aesthetic score */}
          <div className="flex items-baseline gap-1.5 mr-2">
            <span className="label-caps text-outline">Aesthetic Score</span>
            {displayScore !== null && (
              <span className="font-headline text-3xl font-semibold leading-none" style={{ color: scoreColor(displayScore) }}>
                {displayScore}
              </span>
            )}
          </div>

          {/* Three-dot menu */}
          <button className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="currentColor" className="text-outline-variant">
              <circle cx="5" cy="12" r="1.5"/><circle cx="12" cy="12" r="1.5"/><circle cx="19" cy="12" r="1.5"/>
            </svg>
          </button>

          {/* Collapse chevron */}
          <button
            onClick={onToggle}
            className="w-7 h-7 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-outline-variant" style={{ transform: "rotate(180deg)" }}>
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </button>
        </div>

        {/* Row 2: serif title */}
        <h2 className="font-headline text-[1.35rem] text-on-surface leading-snug mb-4">
          {post.topic}
        </h2>

        {/* Row 3: version pills */}
        {hasVersions && (
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <span className="label-caps text-outline mr-1">Versions:</span>
            {post.versions.map((v, i) => {
              const isSelected = i === selectedVersionIdx;
              const isBest = i === bestIdx;
              return (
                <button
                  key={v.id}
                  onClick={() => setSelectedVersionIdx(i)}
                  className={`text-[11px] font-semibold px-3 py-1 rounded-full transition-all duration-200 ${
                    isSelected
                      ? "bg-on-surface text-white"
                      : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
                  }`}
                >
                  v{v.version_number} · {v.authenticity_score ?? "—"}{isBest ? " ★" : ""}
                </button>
              );
            })}
            {hasVersions && (
              <span className="text-[11px] text-outline ml-1">
                {post.versions[selectedVersionIdx].version_type}
              </span>
            )}
          </div>
        )}

        {/* Row 4: full post content — no truncation */}
        <p className="text-[14px] text-on-surface leading-[1.8] whitespace-pre-wrap">
          {activeContent}
        </p>
      </div>

      {/* ── Delete confirm bar ──────────────────────────────────────────── */}
      {isConfirming && (
        <div className="mx-6 mb-4 rounded-xl bg-surface-container px-4 py-3 flex items-center gap-3">
          <span className="text-xs text-outline flex-1">Permanently delete this post and all its versions?</span>
          <button
            onClick={handleDelete}
            disabled={deleting}
            className="text-xs text-white bg-error rounded-lg px-3 py-1.5 hover:opacity-80 disabled:opacity-50 transition-opacity font-medium"
          >
            {deleting ? "Deleting..." : "Yes, delete"}
          </button>
          <button
            onClick={() => setConfirmingId(null)}
            className="text-xs text-secondary border border-surface-container-high rounded-lg px-3 py-1.5 hover:text-on-surface transition-colors"
          >
            Cancel
          </button>
        </div>
      )}

      {/* ── Restored message ────────────────────────────────────────────── */}
      {restoredMsg && (
        <p className="mx-6 mb-4 text-xs text-primary bg-primary/5 rounded-lg px-4 py-2.5">{restoredMsg}</p>
      )}

      {/* ── Copy feedback ───────────────────────────────────────────────── */}
      {copied && (
        <p className="mx-6 mb-4 text-xs text-secondary">Copied to clipboard.</p>
      )}

      {/* ── Diagrams ────────────────────────────────────────────────────── */}
      {activeDiagrams && activeDiagrams.length > 0 && (
        <div className="mx-6 mb-4 space-y-3">
          <p className="label-caps text-outline-variant">Diagrams</p>
          {activeDiagrams.map((d) => (
            <HistoryDiagramCard key={d.position} diagram={d} />
          ))}
        </div>
      )}

      {/* ── Card footer ─────────────────────────────────────────────────── */}
      <div
        className="px-6 py-4 flex items-center gap-4"
        style={{ borderTop: "0.5px solid #dfe3e2" }}
      >
        {/* View Revision History */}
        <button
          onClick={handleCopy}
          className="flex items-center gap-1.5 text-[12px] text-secondary hover:text-on-surface transition-colors"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="12" cy="12" r="10"/>
            <polyline points="12 6 12 12 16 14"/>
          </svg>
          {copied ? "Copied!" : "View Revision History"}
        </button>

        {/* Delete */}
        <button
          onClick={() => isConfirming ? setConfirmingId(null) : setConfirmingId(post.id)}
          className="flex items-center gap-1.5 text-[12px] text-outline-variant hover:text-error transition-colors ml-2"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
          Delete
        </button>

        <div className="flex-1" />

        {/* Restore Draft */}
        {hasVersions ? (
          <button
            onClick={handleRestore}
            disabled={restoring}
            className="btn-primary flex items-center gap-2 text-white rounded-xl px-5 py-2.5 text-[12px] font-semibold hover:opacity-90 disabled:opacity-50 transition-opacity shadow-card"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="1 4 1 10 7 10"/>
              <path d="M3.51 15a9 9 0 1 0 .49-3.74"/>
            </svg>
            {restoring ? "Restoring…" : `Restore v${post.versions[selectedVersionIdx].version_number}`}
          </button>
        ) : (
          <button
            onClick={handleCopy}
            className="btn-primary flex items-center gap-2 text-white rounded-xl px-5 py-2.5 text-[12px] font-semibold hover:opacity-90 transition-opacity shadow-card"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="9" y="9" width="13" height="13" rx="2"/><path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"/>
            </svg>
            {copied ? "Copied!" : "Copy Draft"}
          </button>
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);

  // Pure UI sort state
  const [sort, setSort] = useState<"newest" | "oldest" | "score">("newest");

  const handleDeletePost = (id: number) => {
    setPosts((prev) => prev.filter((p) => p.id !== id));
    setConfirmingId(null);
  };

  useEffect(() => {
    fetch(`${API}/history`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load history");
        return r.json();
      })
      .then((data) => setPosts(data.posts ?? []))
      .catch(() => setError("Could not load post history. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const filteredPosts = posts
    .filter(p => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return p.topic.toLowerCase().includes(q) || p.content.toLowerCase().includes(q);
    })
    .sort((a, b) => {
      if (sort === "oldest") return a.created_at.localeCompare(b.created_at);
      if (sort === "score") return (b.authenticity_score ?? 0) - (a.authenticity_score ?? 0);
      return b.created_at.localeCompare(a.created_at); // newest
    });

  const SORT_OPTIONS: { id: "newest" | "oldest" | "score"; label: string }[] = [
    { id: "newest", label: "Newest" },
    { id: "oldest", label: "Oldest" },
    { id: "score", label: "By Score" },
  ];

  return (
    <div className="-mx-10 -mt-10 -mb-10 min-h-screen bg-background flex flex-col">

      {/* ── Top header bar ───────────────────────────────────────────────── */}
      <div
        style={{ borderBottom: "0.5px solid #dfe3e2", height: "56px" }}
        className="flex items-center px-10 bg-background shrink-0 gap-4"
      >
        {/* Search */}
        <div className="relative w-72">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-outline-variant" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            placeholder="Search past drafts..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-8 pr-4 py-1.5 text-[13px] bg-surface-container-low rounded-full border border-surface-container-high focus:outline-none focus:border-outline-variant transition-all text-on-surface placeholder:text-outline-variant"
          />
        </div>

        <div className="flex-1" />

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

        {/* ── Title row ──────────────────────────────────────────────────── */}
        <div className="flex items-start justify-between gap-8 mb-10">
          {/* Left: title + subtitle */}
          <div className="flex-1 min-w-0">
            <h1 className="font-headline text-[2.75rem] text-on-surface leading-tight mb-3">
              History Archive
            </h1>
            <p className="text-secondary text-[14px] leading-relaxed max-w-lg">
              A chronological collection of your creative output. Review, refine, and restore past versions of your stories.
            </p>
          </div>

          {/* Right: sort pills */}
          <div className="flex items-center gap-2 pt-3 shrink-0">
            {SORT_OPTIONS.map((opt) => (
              <button
                key={opt.id}
                onClick={() => setSort(opt.id)}
                className={`px-4 py-2 rounded-full text-[12px] font-semibold transition-all duration-200 ${
                  sort === opt.id
                    ? "btn-primary text-white shadow-card"
                    : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
                }`}
              >
                {opt.label}
              </button>
            ))}
          </div>
        </div>

        {/* ── States ─────────────────────────────────────────────────────── */}
        {loading && (
          <div className="flex items-center gap-3 py-12 justify-center">
            <div className="w-5 h-5 rounded-full border-2 border-surface-container-high border-t-primary animate-spin" />
            <p className="text-sm text-outline">Loading archive…</p>
          </div>
        )}

        {error && <p className="text-sm text-error mb-6">{error}</p>}

        {!loading && !error && posts.length === 0 && (
          <div className="rounded-2xl bg-surface-container-lowest px-6 py-16 text-center" style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)" }}>
            <p className="font-headline text-xl text-on-surface mb-2">No drafts yet</p>
            <p className="text-outline text-sm">Posts are auto-saved when you generate. They will appear here.</p>
          </div>
        )}

        {!loading && posts.length > 0 && filteredPosts.length === 0 && (
          <div className="rounded-2xl bg-surface-container-lowest px-6 py-12 text-center" style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)" }}>
            <p className="text-outline text-sm">No posts match your search.</p>
          </div>
        )}

        {/* ── Post cards ─────────────────────────────────────────────────── */}
        {!loading && filteredPosts.length > 0 && (
          <div className="space-y-3">
            {filteredPosts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                onDelete={handleDeletePost}
                confirmingId={confirmingId}
                setConfirmingId={setConfirmingId}
                isExpanded={expandedId === post.id}
                onToggle={() => setExpandedId(expandedId === post.id ? null : post.id)}
              />
            ))}
          </div>
        )}

        {/* ── Show older entries ─────────────────────────────────────────── */}
        {!loading && filteredPosts.length > 0 && (
          <div className="flex flex-col items-center mt-12 gap-2">
            <span className="label-caps text-outline-variant">Show Older Entries</span>
            <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round" className="text-outline-variant">
              <polyline points="7 13 12 18 17 13"/>
              <polyline points="7 7 12 12 17 7"/>
            </svg>
          </div>
        )}
      </div>

      {/* ── Floating action button ────────────────────────────────────────── */}
      <button
        className="fixed bottom-8 right-8 w-14 h-14 rounded-full btn-primary shadow-card hover:shadow-card-hover hover:-translate-y-0.5 flex items-center justify-center transition-all duration-200 z-20"
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-white">
          <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>
        </svg>
      </button>
    </div>
  );
}
