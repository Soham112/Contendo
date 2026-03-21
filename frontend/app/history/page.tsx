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
          `<html><body style="margin:0;background:#f5f5f5;display:flex;justify-content:center;padding:24px">` +
          `<img src="${dataURL}" style="max-width:100%;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.15)" />` +
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
    <div className="rounded-xl border border-gray-200 bg-white overflow-hidden">
      <div className="px-4 py-2.5 border-b border-gray-100">
        <p className="text-xs font-medium text-gray-600">
          Diagram —{" "}
          <span className="font-normal text-gray-400">
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
      <div className="px-4 py-2.5 border-t border-gray-100 space-y-2">
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpen}
            className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors"
          >
            Open as PNG
          </button>
          {pngState === "opened" && (
            <span className="text-xs text-gray-500">
              PNG opened in new tab — right-click and select <strong>Save Image</strong>
            </span>
          )}
          {pngState === "blocked" && (
            <span className="text-xs text-gray-500">
              Popup blocked — right-click the image below to save
            </span>
          )}
        </div>
        {pngState === "blocked" && fallbackDataURL && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={fallbackDataURL}
            alt="diagram PNG"
            className="max-w-full rounded-lg border border-gray-200"
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

function ScoreBadge({ score }: { score: number | null }) {
  if (score === null || score === undefined) {
    return <span className="text-xs text-gray-400">—</span>;
  }
  const color =
    score >= 75
      ? "bg-green-100 text-green-700"
      : score >= 50
      ? "bg-amber-100 text-amber-700"
      : "bg-red-100 text-red-600";
  return (
    <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${color}`}>
      {score}/100
    </span>
  );
}

function VersionsTable({ post }: { post: Post }) {
  const [expanded, setExpanded] = useState(false);
  const [restoringId, setRestoringId] = useState<number | null>(null);
  const [restoredMsg, setRestoredMsg] = useState("");

  if (post.versions.length <= 1) return null;

  const bestScore = Math.max(...post.versions.map((v) => v.authenticity_score ?? -1));

  const handleRestore = async (version: Version) => {
    setRestoringId(version.id);
    setRestoredMsg("");
    try {
      const res = await fetch(`${API}/history/${post.id}/restore/${version.id}`, {
        method: "POST",
      });
      if (!res.ok) throw new Error("Restore failed");
      const data = await res.json();

      // Write restored content into sessionStorage so Create Post picks it up
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
      setRestoringId(null);
    }
  };

  return (
    <div className="space-y-2 pt-1">
      <button
        onClick={() => setExpanded((v) => !v)}
        className="flex items-center gap-1.5 text-xs text-gray-400 hover:text-gray-700 transition-colors"
      >
        <span>{post.versions.length} versions</span>
        <span className={`transition-transform ${expanded ? "rotate-180" : ""}`}>▼</span>
      </button>

      {expanded && (
        <div className="rounded-xl border border-gray-200 overflow-hidden">
          <table className="w-full text-xs">
            <thead>
              <tr className="border-b border-gray-100 bg-gray-50">
                <th className="px-3 py-2 text-left font-medium text-gray-500">Version</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Score</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Type</th>
                <th className="px-3 py-2 text-left font-medium text-gray-500">Date</th>
                <th className="px-3 py-2 text-right font-medium text-gray-500"></th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {post.versions.map((v) => {
                const isBest = v.authenticity_score !== null && v.authenticity_score === bestScore;
                const date = new Date(v.created_at).toLocaleDateString("en-US", {
                  month: "short",
                  day: "numeric",
                });
                return (
                  <tr key={v.id} className="bg-white">
                    <td className="px-3 py-2 text-gray-700 font-medium">v{v.version_number}</td>
                    <td className="px-3 py-2">
                      <div className="flex items-center gap-1.5">
                        <ScoreBadge score={v.authenticity_score} />
                        {isBest && (
                          <span className="text-xs font-medium px-1.5 py-0.5 rounded-full bg-green-100 text-green-700">
                            Best
                          </span>
                        )}
                      </div>
                    </td>
                    <td className="px-3 py-2 capitalize text-gray-500">{v.version_type}</td>
                    <td className="px-3 py-2 text-gray-400">{date}</td>
                    <td className="px-3 py-2 text-right">
                      <button
                        onClick={() => handleRestore(v)}
                        disabled={restoringId === v.id}
                        className="text-xs border border-gray-200 rounded-lg px-2.5 py-1 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors disabled:opacity-50"
                      >
                        {restoringId === v.id ? "Restoring…" : "Restore"}
                      </button>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
          {restoredMsg && (
            <div className="px-4 py-2.5 border-t border-gray-100 bg-blue-50">
              <p className="text-xs text-blue-600">{restoredMsg}</p>
            </div>
          )}
        </div>
      )}
    </div>
  );
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
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);

  const isConfirming = confirmingId === post.id;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(post.content);
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

  const date = new Date(post.created_at).toLocaleDateString("en-US", {
    month: "short",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-4">
        <div className="flex items-start justify-between gap-4">
          <div className="flex-1 min-w-0">
            <p className="font-semibold text-gray-900 text-sm leading-snug truncate">
              {post.topic}
            </p>
            <div className="mt-2 flex flex-wrap items-center gap-2">
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                {FORMAT_LABELS[post.format] ?? post.format}
              </span>
              <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
                {TONE_LABELS[post.tone] ?? post.tone}
              </span>
              <ScoreBadge score={post.authenticity_score} />
              <span className="text-xs text-gray-400">{date}</span>
            </div>
          </div>
          <div className="flex items-center gap-3 pt-0.5">
            <button
              onClick={() => setExpanded((v) => !v)}
              className="text-xs text-gray-500 hover:text-gray-900 whitespace-nowrap transition-colors"
            >
              {expanded ? "Hide" : "See full post"}
            </button>
            {!isConfirming && (
              <button
                onClick={() => setConfirmingId(post.id)}
                className="text-xs text-gray-400 hover:text-red-500 whitespace-nowrap transition-colors"
              >
                Delete
              </button>
            )}
            {isConfirming && (
              <div className="flex items-center gap-2">
                <span className="text-xs text-gray-500 whitespace-nowrap">Delete this post?</span>
                <button
                  onClick={handleDelete}
                  disabled={deleting}
                  className="text-xs text-white bg-red-500 hover:bg-red-600 rounded-lg px-2.5 py-1 whitespace-nowrap transition-colors disabled:opacity-50"
                >
                  {deleting ? "Deleting..." : "Yes, delete"}
                </button>
                <button
                  onClick={() => setConfirmingId(null)}
                  className="text-xs text-gray-500 hover:text-gray-900 border border-gray-200 rounded-lg px-2.5 py-1 whitespace-nowrap transition-colors"
                >
                  Cancel
                </button>
              </div>
            )}
          </div>
        </div>
      </div>

      {expanded && (
        <div className="border-t border-gray-100 px-5 py-4 space-y-4">
          <pre className="text-sm text-gray-700 whitespace-pre-wrap leading-relaxed font-sans">
            {post.content}
          </pre>
          <button
            onClick={handleCopy}
            className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors"
          >
            {copied ? "Copied!" : "Copy"}
          </button>
          {post.svg_diagrams && post.svg_diagrams.length > 0 && (
            <div className="space-y-3 pt-1">
              <p className="text-xs uppercase tracking-widest text-gray-400">Diagrams</p>
              {post.svg_diagrams.map((d) => (
                <HistoryDiagramCard key={d.position} diagram={d} />
              ))}
            </div>
          )}
          <VersionsTable post={post} />
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
    <div className="space-y-8">
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">History</h1>
        <p className="mt-1 text-gray-500 text-sm">
          Auto-saved posts. Newest first.
        </p>
      </div>

      {loading && (
        <p className="text-sm text-gray-400">Loading...</p>
      )}

      {error && (
        <p className="text-sm text-red-500">{error}</p>
      )}

      {!loading && !error && posts.length === 0 && (
        <div className="rounded-xl border border-gray-200 bg-white px-6 py-12 text-center">
          <p className="text-gray-400 text-sm">No posts yet.</p>
          <p className="text-gray-400 text-xs mt-1">
            Posts are auto-saved when you generate. They will appear here.
          </p>
        </div>
      )}

      {!loading && posts.length > 0 && (
        <div className="space-y-4">
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
