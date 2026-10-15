"use client";

import { useEffect, useState } from "react";
import { useParams, useRouter } from "next/navigation";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import { Button } from "@/components/ui/button";
import { Card, Skeleton } from "@/components/ui/card";
import { EmptyState, ErrorState } from "@/components/ui/states";
import MarkPublishedDialog from "@/components/history/MarkPublishedDialog";
import { DiagramCard } from "@/components/create/VisualCards";

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


const TONE_LABELS: Record<string, string> = {
  "casual": "Casual",
  "technical": "Technical",
  "storytelling": "Storytelling",
};

function scorePillColors(score: number | null): string {
  if (score === null) return "bg-surface border-border text-on-surface-variant";
  if (score >= 80) return "bg-score-green-bg border-score-green text-score-green";
  return "bg-surface border-border text-text-secondary";
}

function scorePillSelectedColors(score: number | null): string {
  if (score === null) return "bg-text-primary border-text-primary text-card";
  if (score >= 80) return "bg-score-green-bg border-score-green text-score-green ring-1 ring-score-green";
  return "bg-text-primary border-text-primary text-card";
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
  const [publishSaving, setPublishSaving] = useState(false);

  const loadPost = () => {
    if (!postId) return;
    setLoading(true);
    setError("");
    api.getHistory()
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load history");
        return r.json();
      })
      .then((data) => {
        const found: Post = (data.posts ?? []).find((p: Post) => p.id === Number(postId));
        if (!found) { setError("notfound"); return; }
        setPost(found);
        if (found.versions.length > 1) {
          setSelectedVersionIdx(bestVersionIndex(found.versions));
        }
      })
      .catch(() => setError("We couldn't load this post. Check your connection and try again."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadPost();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [postId]);

  const backLink = (
    <Link href="/history" className="inline-flex min-h-11 items-center text-[0.875rem] text-on-surface-variant hover:text-on-surface">
      ← History
    </Link>
  );
  if (loading) return (
    <div role="status" aria-label="Loading post" className="space-y-6">
      {backLink}
      <Skeleton className="h-7 w-2/3" />
      <Skeleton className="h-4 w-40" />
      <Skeleton className="h-64 w-full rounded-2xl" />
    </div>
  );
  if (error || !post) return (
    <div className="space-y-6">
      {backLink}
      {error === "notfound" || !error
        ? <EmptyState title="This post isn't here" body="It may have been deleted." action={<Button asChild><Link href="/history">See all posts</Link></Button>} />
        : <ErrorState message={error} onRetry={loadPost} />}
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
      setRestoredMsg(`Version ${data.version_number} restored. Open it in the editor to keep working on it.`);
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

  const handlePublishSave = async (publishPlatform: string, publishContent: string) => {
    setPublishSaving(true);
    try {
      const res = await api.markAsPublished(post.id, publishPlatform, publishContent || undefined);
      if (!res.ok) throw new Error("Failed");
      setPost((prev) => prev ? { ...prev, published_at: new Date().toISOString(), published_platform: publishPlatform, published_content: publishContent || null } : prev);
      setPublishModalOpen(false);
      showToast(publishContent.trim() ? "Marked as published. Contendo will learn your voice from this version." : "Marked as published", "success");
    } catch {
      showToast("We couldn't save that. Please try again.", "error");
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
      {backLink}

      <div>
        <h1 className="font-headline text-[1.75rem] leading-snug text-on-surface">{post.topic}</h1>
        <div className="mt-2 flex flex-wrap items-center gap-2">
          <span className="text-[0.75rem] px-2.5 py-1 rounded-full bg-surface-container text-on-surface-variant">{TONE_LABELS[post.tone] ?? post.tone}</span>
          <span className="text-[0.75rem] text-on-surface-variant">{date}</span>
          {post.published_at && (
            <span className="text-[0.75rem] px-2.5 py-1 rounded-full font-semibold bg-primary-container text-on-primary-fixed">
              Published{post.published_platform ? ` · ${post.published_platform.charAt(0).toUpperCase() + post.published_platform.slice(1)}` : ""}
            </span>
          )}
        </div>
      </div>

      {hasVersions && (
        <div role="group" aria-label="Versions" className="flex flex-wrap gap-2">
          {post.versions.map((v, i) => {
            const isSelected = i === selectedVersionIdx;
            const isBest = i === bestIdx;
            return (
              <button
                key={v.id}
                type="button"
                aria-pressed={isSelected}
                onClick={() => setSelectedVersionIdx(i)}
                className={`min-h-11 sm:min-h-8 text-[0.75rem] px-3 rounded-full border font-medium transition-colors ${
                  isSelected ? scorePillSelectedColors(v.authenticity_score) : scorePillColors(v.authenticity_score)
                }`}
              >
                v{v.version_number} · {v.authenticity_score ?? "—"}{isBest ? " ★" : ""}
              </button>
            );
          })}
        </div>
      )}

      <Card>
        {hasVersions && (
          <p className="text-[0.75rem] text-on-surface-variant mb-4">
            Version {post.versions[selectedVersionIdx].version_number} · {post.versions[selectedVersionIdx].version_type}
          </p>
        )}
        <p className="text-[0.9375rem] text-on-surface whitespace-pre-wrap leading-relaxed">{activeContent}</p>
      </Card>

      <div className="flex flex-wrap items-center gap-2">
        <Button variant="secondary" onClick={handleCopy}>{copied ? "Copied" : "Copy"}</Button>
        <Button variant="secondary" onClick={handleOpenInEditor}>Open in editor</Button>
        {hasVersions && (
          <Button variant="secondary" onClick={handleRestore} loading={restoring}>
            Restore version {post.versions[selectedVersionIdx].version_number}
          </Button>
        )}
        {!post.published_at && <Button variant="secondary" onClick={() => setPublishModalOpen(true)}>Mark as published</Button>}
        {!confirming && (
          <Button variant="tertiary" className="sm:ml-auto text-error decoration-error/40" onClick={() => setConfirming(true)}>
            Delete post
          </Button>
        )}
      </div>

      {confirming && (
        <div role="alert" className="flex flex-wrap items-center gap-3 rounded-xl bg-surface-container px-4 py-3">
          <span className="flex-1 text-[0.875rem] text-on-surface">Delete this post and all its versions? This can&apos;t be undone.</span>
          <Button variant="destructive" size="sm" onClick={handleDelete} loading={deleting}>Yes, delete</Button>
          <Button variant="secondary" size="sm" onClick={() => setConfirming(false)}>Cancel</Button>
        </div>
      )}

      {restoredMsg && <p role="status" className="text-[0.875rem] text-on-surface-variant">{restoredMsg}</p>}

      {publishModalOpen && (
        <MarkPublishedDialog onSave={handlePublishSave} onClose={() => setPublishModalOpen(false)} saving={publishSaving} />
      )}

      {activeDiagrams && activeDiagrams.length > 0 && (
        <div className="space-y-3">
          <p className="label-caps text-on-surface-variant">Diagrams</p>
          {activeDiagrams.map((d) => (
            <DiagramCard key={d.position} svg={d.svg_code} description={d.description} />
          ))}
        </div>
      )}
    </div>
  );
}
