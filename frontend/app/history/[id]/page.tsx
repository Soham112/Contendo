"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";

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
  published_at: string | null;
  published_platform: string | null;
  published_content: string | null;
}

const PLATFORMS = [
  { id: "linkedin", label: "LinkedIn" },
  { id: "twitter", label: "X" },
  { id: "medium", label: "Medium" },
  { id: "other", label: "Other" },
];

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
  if (score === null) return "bg-surface border-border text-text-muted";
  if (score >= 80) return "bg-score-green-bg border-score-green text-score-green";
  return "bg-surface border-border text-text-secondary";
}

function scorePillSelectedColors(score: number | null): string {
  if (score === null) return "bg-text-primary border-text-primary text-card";
  if (score >= 80) return "bg-score-green-bg border-score-green text-score-green ring-1 ring-score-green";
  return "bg-text-primary border-text-primary text-card";
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
          `<html><body style="margin:0;background:#faf9f7;display:flex;justify-content:center;padding:24px">` +
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
            className="text-xs border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:border-text-primary hover:text-text-primary transition-colors"
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
  const api = useApi();
  const params = useParams();
  const router = useRouter();
  const { showToast } = useToast();
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

  // Publish modal state
  const [publishModalOpen, setPublishModalOpen] = useState(false);
  const [publishPlatform, setPublishPlatform] = useState("linkedin");
  const [publishContent, setPublishContent] = useState("");
  const [publishSaving, setPublishSaving] = useState(false);
  const [publishSuccessMsg, setPublishSuccessMsg] = useState("");

  useEffect(() => {
    if (!postId) return;
    api.getHistory()
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
      <Link href="/history" className="text-xs text-text-secondary mt-2 inline-block">← Back to History</Link>
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
      const res = await api.restoreVersion(post.id, activeVersion.id);
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
      await api.deletePost(post.id);
      router.push("/history");
    } catch {
      setDeleting(false);
      setConfirming(false);
    }
  };

  const handleOpenInEditor = () => {
    const content = activeContent;
    const score = activeVersion ? activeVersion.authenticity_score : post.authenticity_score;
    try {
      sessionStorage.setItem(SS_POST, content);
      sessionStorage.setItem(SS_SCORE, String(score ?? 0));
      sessionStorage.setItem(SS_FEEDBACK, JSON.stringify([]));
      sessionStorage.setItem(SS_ITERATIONS, "1");
      sessionStorage.setItem(SS_VISUALS, JSON.stringify([]));
      sessionStorage.setItem(SS_CURRENT_POST_ID, String(post.id));
      sessionStorage.setItem("contentOS_last_topic_meta", post.topic);
      sessionStorage.setItem("contentOS_last_format_meta", post.format);
      sessionStorage.setItem("contentOS_last_tone_meta", post.tone);
    } catch { /* ignore */ }
    router.push("/create");
  };

  const handlePublishSave = async () => {
    setPublishSaving(true);
    try {
      const res = await api.markAsPublished(post.id, publishPlatform, publishContent || undefined);
      if (!res.ok) throw new Error("Failed");
      setPost((prev) => prev ? { ...prev, published_at: new Date().toISOString(), published_platform: publishPlatform, published_content: publishContent || null } : prev);
      if (publishContent.trim()) {
        setPublishSuccessMsg("Added to your writing samples — your voice model just got sharper.");
        setTimeout(() => {
          setPublishModalOpen(false);
          setPublishSuccessMsg("");
        }, 1500);
      } else {
        setPublishModalOpen(false);
      }
      showToast("Post marked as published", "success");
    } catch {
      showToast("Failed to save — please try again", "error");
    } finally {
      setPublishSaving(false);
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
      <Link href="/history" className="text-xs text-text-muted hover:text-text-primary transition-colors">
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
          className="text-sm border border-border rounded-lg px-4 py-2 text-text-secondary hover:border-text-primary hover:text-text-primary transition-colors bg-card"
        >
          {copied ? "Copied!" : "Copy"}
        </button>
        <button
          onClick={handleOpenInEditor}
          className="text-sm border border-border rounded-lg px-4 py-2 text-text-secondary hover:border-text-primary hover:text-text-primary transition-colors bg-card flex items-center gap-1.5"
        >
          <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M11 4H4a2 2 0 0 0-2 2v14a2 2 0 0 0 2 2h14a2 2 0 0 0 2-2v-7"/>
            <path d="M18.5 2.5a2.121 2.121 0 0 1 3 3L12 15l-4 1 1-4 9.5-9.5z"/>
          </svg>
          Open in editor
        </button>
        {hasVersions && (
          <button
            onClick={handleRestore}
            disabled={restoring}
            className="text-sm border border-border rounded-lg px-4 py-2 text-text-secondary hover:border-text-primary hover:text-text-primary transition-colors bg-card disabled:opacity-50"
          >
            {restoring ? "Restoring…" : `Restore v${post.versions[selectedVersionIdx].version_number} to Create Post`}
          </button>
        )}
        {!post.published_at && (
          <button
            onClick={() => setPublishModalOpen(true)}
            className="text-sm border border-border rounded-lg px-4 py-2 text-text-secondary hover:border-text-primary hover:text-text-primary transition-colors bg-card flex items-center gap-1.5"
          >
            <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <polyline points="20 6 9 17 4 12"/>
            </svg>
            Mark as published
          </button>
        )}
        {post.published_at && (
          <span className="text-xs px-3 py-1.5 rounded-full font-semibold" style={{ background: "rgba(88,97,79,0.12)", color: "#58614f" }}>
            Published{post.published_platform ? ` · ${post.published_platform.charAt(0).toUpperCase() + post.published_platform.slice(1)}` : ""}
          </span>
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
        <p className="text-xs text-text-secondary">{restoredMsg}</p>
      )}

      {/* Publish modal */}
      {publishModalOpen && (
        <div
          className="fixed inset-0 z-50 flex items-center justify-center"
          style={{ background: "rgba(47,51,51,0.35)", backdropFilter: "blur(4px)" }}
          onClick={(e) => { if (e.target === e.currentTarget && !publishSaving) setPublishModalOpen(false); }}
        >
          <div
            className="bg-surface-container-lowest rounded-2xl px-8 py-7 w-full max-w-md mx-4"
            style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.08), 0px 24px 60px rgba(47,51,51,0.12)" }}
          >
            {publishSuccessMsg ? (
              <div className="flex items-center gap-3 py-2">
                <span style={{ color: "#58614f", fontSize: 18 }}>✓</span>
                <p className="text-[13px] text-on-surface">{publishSuccessMsg}</p>
              </div>
            ) : (
              <>
                <h2 className="font-headline text-[1.2rem] text-on-surface mb-1">Mark as published</h2>
                <p className="text-[12px] text-outline mb-5">Record where this post went live.</p>

                <p className="label-caps text-outline mb-2">Platform</p>
                <div className="flex gap-2 flex-wrap mb-5">
                  {PLATFORMS.map((p) => (
                    <button
                      key={p.id}
                      onClick={() => setPublishPlatform(p.id)}
                      className={`px-4 py-1.5 rounded-full text-[12px] font-semibold transition-all duration-150 ${
                        publishPlatform === p.id ? "text-white" : "bg-surface-container text-secondary hover:bg-surface-container-high"
                      }`}
                      style={publishPlatform === p.id ? { background: "linear-gradient(135deg, #58614f, #4c5543)" } : {}}
                    >
                      {p.label}
                    </button>
                  ))}
                </div>

                <p className="label-caps text-outline mb-2">Final version <span className="normal-case font-normal">(optional)</span></p>
                <textarea
                  value={publishContent}
                  onChange={(e) => setPublishContent(e.target.value)}
                  rows={4}
                  placeholder="Paste what you actually posted — your voice model will learn from it."
                  className="input-editorial w-full px-0 py-2 text-sm text-on-surface placeholder:text-outline-variant focus:outline-none resize-none mb-5"
                  style={{ borderBottom: "1px solid #dfe3e2" }}
                />

                <div className="flex items-center gap-3 justify-end">
                  <button
                    onClick={() => setPublishModalOpen(false)}
                    className="px-4 py-2 text-[13px] text-secondary hover:text-on-surface transition-colors ghost-border rounded-xl"
                  >
                    Cancel
                  </button>
                  <button
                    onClick={handlePublishSave}
                    disabled={publishSaving}
                    className="btn-primary px-5 py-2 text-[13px] text-white rounded-xl font-semibold disabled:opacity-50 transition-opacity"
                  >
                    {publishSaving ? "Saving…" : "Save"}
                  </button>
                </div>
              </>
            )}
          </div>
        </div>
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
