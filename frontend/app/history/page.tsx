"use client";

import { useEffect, useState } from "react";

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
          `<html><body style="margin:0;background:#fdfcfb;display:flex;justify-content:center;padding:24px">` +
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
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="px-4 py-2.5 border-b border-border-subtle">
        <p className="text-xs font-medium text-text-secondary">
          Diagram —{" "}
          <span className="font-normal text-text-muted">
            {diagram.description.length > 60
              ? diagram.description.slice(0, 60) + "…"
              : diagram.description}
          </span>
        </p>
      </div>
      <div
        className="p-3 overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: diagram.svg_code }}
      />
      <div className="px-4 py-2.5 border-t border-border-subtle space-y-2">
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpen}
            className="text-xs border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:border-amber hover:text-amber transition-colors"
          >
            Open as PNG
          </button>
          {pngState === "opened" && (
            <span className="text-xs text-text-muted">
              PNG opened in new tab — right-click and select <strong>Save Image</strong>
            </span>
          )}
          {pngState === "blocked" && (
            <span className="text-xs text-text-muted">
              Popup blocked — right-click the image below to save
            </span>
          )}
        </div>
        {pngState === "blocked" && fallbackDataURL && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={fallbackDataURL}
            alt="diagram PNG"
            className="max-w-full rounded-lg border border-border"
          />
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

function scorePillColors(score: number | null): string {
  if (score === null) return "bg-stat border-border text-text-muted";
  if (score >= 80) return "bg-score-green-bg border-score-green text-score-green";
  if (score >= 65) return "bg-score-amber-bg border-score-amber-border text-score-amber";
  return "bg-score-red-bg border-score-red text-score-red";
}

function scorePillSelectedColors(score: number | null): string {
  if (score === null) return "bg-hover border-border text-text-secondary";
  if (score >= 80) return "bg-score-green-bg border-score-green text-score-green ring-1 ring-score-green";
  if (score >= 65) return "bg-score-amber-bg border-score-amber text-score-amber ring-1 ring-score-amber";
  return "bg-score-red-bg border-score-red text-score-red ring-1 ring-score-red";
}

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) {
    return <span className="text-xs text-text-muted">—</span>;
  }
  const color =
    score >= 75
      ? "bg-score-green-bg text-score-green border-score-green"
      : score >= 50
      ? "bg-score-amber-bg text-score-amber border-score-amber-border"
      : "bg-score-red-bg text-score-red border-score-red";
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full border ${color}`}>
      {score}/100
    </span>
  );
}

function bestVersionIndex(versions: Version[]): number {
  let best = 0;
  for (let i = 1; i < versions.length; i++) {
    const a = versions[i].authenticity_score ?? -1;
    const b = versions[best].authenticity_score ?? -1;
    if (a > b) best = i;
  }
  return best;
}

function PostCard({
  post,
  onDelete,
  confirmingId,
  setConfirmingId,
}: {
  post: Post;
  onDelete: (id: number) => void;
  confirmingId: number | null;
  setConfirmingId: (id: number | null) => void;
}) {
  const hasVersions = post.versions.length > 1;
  const defaultIdx = hasVersions ? bestVersionIndex(post.versions) : 0;
  const [selectedVersionIdx, setSelectedVersionIdx] = useState(defaultIdx);
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoredMsg, setRestoredMsg] = useState("");

  const isConfirming = confirmingId === post.id;

  const activeVersion = hasVersions ? post.versions[selectedVersionIdx] : null;
  const activeContent = activeVersion ? activeVersion.content : post.content;
  const activeScore = activeVersion ? activeVersion.authenticity_score : post.authenticity_score;
  const activeDiagrams = activeVersion
    ? (activeVersion.svg_diagrams ?? null)
    : post.svg_diagrams;

  const bestIdx = hasVersions ? bestVersionIndex(post.versions) : 0;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await fetch(`${API}/history/${post.id}`, { method: "DELETE" });
      onDelete(post.id);
    } catch {
      setDeleting(false);
      setConfirmingId(null);
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
    } catch {
      setRestoredMsg("Restore failed. Please try again.");
    } finally {
      setRestoring(false);
    }
  };

  const date = new Date(post.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      {/* Card header */}
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            {/* Topic */}
            <p className="font-medium text-text-primary text-sm leading-snug truncate">
              {post.topic}
            </p>

            {/* Badges + date + version pills */}
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-stat border border-border text-text-muted">
                {FORMAT_LABELS[post.format] ?? post.format}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-stat border border-border text-text-muted">
                {TONE_LABELS[post.tone] ?? post.tone}
              </span>
              <span className="text-xs text-text-hint">{date}</span>

              {!hasVersions && <ScoreBadge score={post.authenticity_score} />}

              {hasVersions && post.versions.map((v, i) => {
                const isSelected = i === selectedVersionIdx;
                const isBest = i === bestIdx;
                const baseColors = isSelected
                  ? scorePillSelectedColors(v.authenticity_score)
                  : scorePillColors(v.authenticity_score);
                return (
                  <button
                    key={v.id}
                    onClick={() => setSelectedVersionIdx(i)}
                    className={`text-xs px-2 py-0.5 rounded-full border font-medium transition-colors ${baseColors}`}
                  >
                    v{v.version_number} · {v.authenticity_score ?? "—"}{isBest ? " ★" : ""}
                  </button>
                );
              })}
            </div>
          </div>

          {/* Actions */}
          <div className="flex items-center gap-3 pt-0.5 shrink-0">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-text-secondary hover:text-text-primary whitespace-nowrap transition-colors"
            >
              {expanded ? "Hide" : "See post"}
            </button>
            {!isConfirming && (
              <button
                onClick={() => setConfirmingId(post.id)}
                className="text-xs text-text-hint hover:text-score-red whitespace-nowrap transition-colors"
              >
                Delete
              </button>
            )}
            {isConfirming && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-text-muted whitespace-nowrap">Delete this post?</span>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="text-xs text-card bg-score-red hover:opacity-80 rounded-lg px-2.5 py-1 whitespace-nowrap transition-opacity disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Yes, delete"}
                </button>
                <button
                  onClick={() => setConfirmingId(null)}
                  className="text-xs text-text-secondary hover:text-text-primary border border-border rounded-lg px-2.5 py-1 whitespace-nowrap transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {/* Expanded content */}
      {expanded && (
        <div className="border-t border-border-subtle px-5 py-4 space-y-4">
          {hasVersions && (
            <p className="text-xs text-text-muted">
              Showing v{post.versions[selectedVersionIdx].version_number}
              {" · "}
              {post.versions[selectedVersionIdx].version_type}
            </p>
          )}
          <pre className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed font-sans">
            {activeContent}
          </pre>
          <div className="flex items-center gap-3">
            <button
              onClick={handleCopy}
              className="text-xs border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:border-amber hover:text-amber transition-colors"
            >
              {copied ? "Copied!" : "Copy"}
            </button>
            {hasVersions && (
              <button
                onClick={handleRestore}
                disabled={restoring}
                className="text-xs border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:border-amber hover:text-amber transition-colors disabled:opacity-50"
              >
                {restoring
                  ? "Restoring…"
                  : `Restore v${post.versions[selectedVersionIdx].version_number} to Create Post`}
              </button>
            )}
          </div>
          {restoredMsg && (
            <p className="text-xs text-amber">{restoredMsg}</p>
          )}
          {activeDiagrams && activeDiagrams.length > 0 && (
            <div className="space-y-3 pt-1">
              <p className="text-xs font-medium uppercase tracking-widest text-text-hint">Diagrams</p>
              {activeDiagrams.map((d) => (
                <HistoryDiagramCard key={d.position} diagram={d} />
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [confirmingId, setConfirmingId] = useState<number | null>(null);

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

  return (
    <div className="space-y-7">
      <div>
        <h1 className="text-xl font-semibold text-text-primary">History</h1>
        <p className="mt-1 text-text-secondary text-sm">
          Auto-saved posts. Newest first.
        </p>
      </div>

      {loading && (
        <p className="text-sm text-text-muted">Loading...</p>
      )}

      {error && (
        <p className="text-sm text-score-red">{error}</p>
      )}

      {!loading && !error && posts.length === 0 && (
        <div className="rounded-lg border border-border bg-card px-6 py-12 text-center">
          <p className="text-text-muted text-sm">No posts yet.</p>
          <p className="text-text-hint text-xs mt-1">
            Posts are auto-saved when you generate. They will appear here.
          </p>
        </div>
      )}

      {!loading && posts.length > 0 && (
        <div className="space-y-3">
          {posts.map((post) => (
            <PostCard
              key={post.id}
              post={post}
              onDelete={handleDeletePost}
              confirmingId={confirmingId}
              setConfirmingId={setConfirmingId}
            />
          ))}
        </div>
      )}
    </div>
  );
}
