"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

interface Diagram {
  position: number;
  description: string;
  svg_code: string;
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

function ScoreBadge({ score }: { score: number }) {
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

function PostCard({ post, onDelete }: { post: Post; onDelete: (id: number) => void }) {
  const [expanded, setExpanded] = useState(false);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);

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
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-xs text-gray-400 hover:text-red-500 whitespace-nowrap transition-colors disabled:opacity-50"
            >
              {deleting ? "Deleting..." : "Delete"}
            </button>
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
        </div>
      )}
    </div>
  );
}

export default function HistoryPage() {
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const handleDeletePost = (id: number) => {
    setPosts((prev) => prev.filter((p) => p.id !== id));
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
            <PostCard key={post.id} post={post} onDelete={handleDeletePost} />
          ))}
        </div>
      )}
    </div>
  );
}
