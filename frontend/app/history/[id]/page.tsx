"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";

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
  if (score >= 65) return "bg-amber-light border-amber-border text-amber";
  return "bg-red-50 border-score-red text-score-red";
}

function scorePillSelectedColors(score: number | null): string {
  if (score === null) return "bg-hover border-border text-text-secondary";
  if (score >= 80) return "bg-score-green-bg border-score-green text-score-green ring-1 ring-score-green";
  if (score >= 65) return "bg-amber-light border-amber text-amber ring-1 ring-amber";
  return "bg-red-50 border-score-red text-score-red ring-1 ring-score-red";
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

function DiagramCard({ diagram }: { diagram: Diagram }) {
  const [pngState, setPngState] = useState<"idle" | "opened" | "blocked">("idle");
  const [fallbackDataURL, setFallbackDataURL] = useState<string | null>(null);

  const handleOpen = async () => {
    try {
      const dataURL = await svgToDataURL(diagram.svg_code);
      const win = window.open();
      if (win) {
        win.document.write(
          `<html><body style="margin:0;background:#fefcf8;display:flex;justify-content:center;padding:24px">` +
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
            {diagram.description.length > 80
              ? diagram.description.slice(0, 80) + "…"
              : diagram.description}
          </span>
        </p>
      </div>
      <div className="p-4 overflow-x-auto" dangerouslySetInnerHTML={{ __html: diagram.svg_code }} />
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
              Opened in new tab — right-click and <strong>Save Image</strong>
            </span>
          )}
          {pngState === "blocked" && (
            <span className="text-xs text-text-muted">Popup blocked — right-click below to save</span>
          )}
        </div>
        {pngState === "blocked" && fallbackDataURL && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={fallbackDataURL} alt="diagram PNG" className="max-w-full rounded-lg border border-border" />
        )}
      </div>
    </div>
  );
}

function bestVersionIndex(versions: Version[]): number {
  let best = 0;
  for (let i = 1; i < versions.length; i++) {
    if ((versions[i].authenticity_score ?? -1) > (versions[best].authenticity_score ?? -1)) best = i;
  }
  return best;
}

export default function PostDetailPage() {
  const params = useParams();
  const router = useRouter();
  const postId = params?.id;

  const [post, setPost] = useState<Post | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [selectedVersionIdx, setSelectedVersionIdx] = useState(0);
  const [copied, setCopied] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoredMsg, setRestoredMsg] = useState("");
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);

  useEffect(() => {
    if (!postId) return;
    fetch(`${API}/history`)
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load history");
        return r.json();
      })
      .then((data) => {
        const found: Post = (data.posts ?? []).find((p: Post) => p.id === Number(postId));
        if (!found) { setError("Post not found."); return; }
        setPost(found);
        if (found.versions.length > 1) {
          setSelectedVersionIdx(bestVersionIndex(found.versions));
        }
      })
      .catch(() => setError("Could not load post."))
      .finally(() => setLoading(false));
  }, [postId]);

  if (loading) return <p className="text-sm text-text-muted">Loading...</p>;
  if (error || !post) return (
    <div>
      <p className="text-sm text-score-red">{error || "Post not found."}</p>
      <Link href="/history" className="text-xs text-amber mt-2 inline-block">← Back to History</Link>
    </div>
  );

  const hasVersions = post.versions.length > 1;
  const bestIdx = hasVersions ? bestVersionIndex(post.versions) : 0;
  const activeVersion = hasVersions ? post.versions[selectedVersionIdx] : null;
  const activeContent = activeVersion ? activeVersion.content : post.content;
  const activeDiagrams = activeVersion ? (activeVersion.svg_diagrams ?? null) : post.svg_diagrams;

  const handleCopy = async () => {
    await navigator.clipboard.writeText(activeContent);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleRestore = async () => {
    if (!activeVersion) return;
    setRestoring(true);
    setRestoredMsg("");
    try {
      const res = await fetch(`${API}/history/${post.id}/restore/${activeVersion.id}`, { method: "POST" });
      if (!res.ok) throw new Error("Restore failed");
      const data = await res.json();
      try {
        sessionStorage.setItem(SS_POST, data.content);
        sessionStorage.setItem(SS_SCORE, String(data.authenticity_score ?? 0));
        sessionStorage.setItem(SS_FEEDBACK, JSON.stringify([]));
        sessionStorage.setItem(SS_ITERATIONS, "1");
        sessionStorage.setItem(SS_VISUALS, JSON.stringify([]));
        sessionStorage.setItem(SS_CURRENT_POST_ID, String(post.id));
      } catch { /* ignore */ }
      setRestoredMsg(`v${data.version_number} restored — go to Create Post to edit`);
    } catch {
      setRestoredMsg("Restore failed. Please try again.");
    } finally {
      setRestoring(false);
    }
  };

  const handleDelete = async () => {
    setDeleting(true);
    try {
      await fetch(`${API}/history/${post.id}`, { method: "DELETE" });
      router.push("/history");
    } catch {
      setDeleting(false);
      setConfirming(false);
    }
  };

  const date = new Date(post.created_at).toLocaleDateString("en-US", {
    month: "long",
    day: "numeric",
    year: "numeric",
  });

  return (
    <div className="space-y-7">
      {/* Back link */}
      <Link href="/history" className="text-xs text-text-muted hover:text-amber transition-colors">
        ← History
      </Link>

      {/* Header */}
      <div>
        <h1 className="text-xl font-semibold text-text-primary leading-snug">{post.topic}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-xs px-2 py-0.5 rounded-full bg-stat border border-border text-text-muted">
            {FORMAT_LABELS[post.format] ?? post.format}
          </span>
          <span className="text-xs px-2 py-0.5 rounded-full bg-stat border border-border text-text-muted">
            {TONE_LABELS[post.tone] ?? post.tone}
          </span>
          <span className="text-xs text-text-hint">{date}</span>
        </div>
      </div>

      {/* Version pills */}
      {hasVersions && (
        <div className="flex flex-wrap gap-1.5">
          {post.versions.map((v, i) => {
            const isSelected = i === selectedVersionIdx;
            const isBest = i === bestIdx;
            return (
              <button
                key={v.id}
                onClick={() => setSelectedVersionIdx(i)}
                className={`text-xs px-2.5 py-1 rounded-full border font-medium transition-colors ${
                  isSelected ? scorePillSelectedColors(v.authenticity_score) : scorePillColors(v.authenticity_score)
                }`}
              >
                v{v.version_number} · {v.authenticity_score ?? "—"}{isBest ? " ★" : ""}
              </button>
            );
          })}
        </div>
      )}

      {/* Post content */}
      <div className="rounded-lg border border-border bg-card px-6 py-5">
        {hasVersions && (
          <p className="text-xs text-text-muted mb-4">
            v{post.versions[selectedVersionIdx].version_number} · {post.versions[selectedVersionIdx].version_type}
          </p>
        )}
        <pre className="text-sm text-text-primary whitespace-pre-wrap leading-relaxed font-sans">
          {activeContent}
        </pre>
      </div>

      {/* Actions */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleCopy}
          className="text-sm border border-border rounded-lg px-4 py-2 text-text-secondary hover:border-amber hover:text-amber transition-colors bg-card"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
        {hasVersions && (
          <button
            onClick={handleRestore}
            disabled={restoring}
            className="text-sm border border-border rounded-lg px-4 py-2 text-text-secondary hover:border-amber hover:text-amber transition-colors bg-card disabled:opacity-50"
          >
            {restoring ? "Restoring…" : `Restore v${post.versions[selectedVersionIdx].version_number} to Create Post`}
          </button>
        )}
        {!confirming && (
          <button
            onClick={() => setConfirming(true)}
            className="text-sm text-text-hint hover:text-score-red transition-colors ml-auto"
          >
            Delete post
          </button>
        )}
        {confirming && (
          <div className="flex items-center gap-2 ml-auto">
            <span className="text-xs text-text-muted">Delete permanently?</span>
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-xs text-card bg-score-red hover:opacity-80 rounded-lg px-3 py-1.5 transition-opacity disabled:opacity-50"
            >
              {deleting ? "Deleting..." : "Yes, delete"}
            </button>
            <button
              onClick={() => setConfirming(false)}
              className="text-xs border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:text-text-primary transition-colors"
            >
              Cancel
            </button>
          </div>
        )}
      </div>

      {restoredMsg && (
        <p className="text-xs text-amber">{restoredMsg}</p>
      )}

      {/* Diagrams */}
      {activeDiagrams && activeDiagrams.length > 0 && (
        <div className="space-y-3">
          <p className="text-xs font-medium uppercase tracking-widest text-text-hint">Diagrams</p>
          {activeDiagrams.map((d) => (
            <DiagramCard key={d.position} diagram={d} />
          ))}
        </div>
      )}
    </div>
  );
}
