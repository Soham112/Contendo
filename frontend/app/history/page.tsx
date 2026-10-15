"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi } from "@/lib/api";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Input, Label, Textarea } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState, ListSkeleton } from "@/components/ui/states";
import { ChoiceGroup } from "@/components/ui/choice-group";
import { Dialog, DialogActions } from "@/components/ui/dialog";
import MarkPublishedDialog from "@/components/history/MarkPublishedDialog";
import { DiagramCard } from "@/components/create/VisualCards";

const SS_POST = "contentOS_last_post";
const SS_SCORE = "contentOS_last_score";
const SS_FEEDBACK = "contentOS_last_feedback";
const SS_ITERATIONS = "contentOS_last_iterations";
const SS_VISUALS = "contentOS_last_visuals";
const SS_CURRENT_POST_ID = "contentOS_current_post_id";
const SS_TOPIC = "contentOS_last_topic_meta";
const SS_FORMAT = "contentOS_last_format_meta";
const SS_TONE = "contentOS_last_tone_meta";

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
  onMarkPublished,
  confirmingId,
  setConfirmingId,
  isExpanded,
  onToggle,
}: {
  post: Post;
  onDelete: (id: number) => void;
  onMarkPublished: (id: number) => void;
  confirmingId: number | null;
  setConfirmingId: (id: number | null) => void;
  isExpanded: boolean;
  onToggle: () => void;
}) {
  const api = useApi();
  const router = useRouter();
  const hasVersions = post.versions.length > 1;
  const defaultIdx = hasVersions ? bestVersionIndex(post.versions) : 0;
  const [selectedVersionIdx, setSelectedVersionIdx] = useState(defaultIdx);
  const [copied, setCopied] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [restoring, setRestoring] = useState(false);
  const [restoredMsg, setRestoredMsg] = useState("");
  const { showToast } = useToast();

  const isConfirming = confirmingId === post.id;

  const handleOpenInEditor = () => {
    const content = hasVersions ? post.versions[selectedVersionIdx].content : post.content;
    const score = hasVersions ? post.versions[selectedVersionIdx].authenticity_score : post.authenticity_score;
    try {
      sessionStorage.setItem(SS_POST, content);
      sessionStorage.setItem(SS_SCORE, String(score ?? 0));
      sessionStorage.setItem(SS_FEEDBACK, JSON.stringify([]));
      sessionStorage.setItem(SS_ITERATIONS, "1");
      sessionStorage.setItem(SS_VISUALS, JSON.stringify([]));
      sessionStorage.setItem(SS_CURRENT_POST_ID, String(post.id));
      sessionStorage.setItem(SS_TOPIC, post.topic);
      sessionStorage.setItem(SS_FORMAT, post.format);
      sessionStorage.setItem(SS_TONE, post.tone);
    } catch { /* ignore */ }
    router.push("/create");
  };

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
      await api.deletePost(post.id);
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
        role="button"
        tabIndex={0}
        aria-expanded={false}
        aria-label={`${post.topic}, ${date}. Show the full post`}
        className="bg-surface-container-lowest rounded-xl px-6 py-5 cursor-pointer hover:bg-surface-container transition-colors duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)" }}
        onClick={onToggle}
        onKeyDown={(e) => { if (e.key === "Enter" || e.key === " ") { e.preventDefault(); onToggle(); } }}
      >
        <div className="flex items-center gap-3 flex-wrap">
          {/* Badges */}
          <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full bg-secondary/10 text-secondary">
            {TONE_LABELS[post.tone] ?? post.tone}
          </span>
          {post.published_at && (
            <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full" style={{ background: "rgba(88,97,79,0.12)", color: "#58614f" }}>
              Published{post.published_platform ? ` · ${post.published_platform.charAt(0).toUpperCase() + post.published_platform.slice(1)}` : ""}
            </span>
          )}
          <span className="text-[11px] text-on-surface-variant ml-1">{date}</span>

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
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-on-surface-variant">
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </div>
        </div>

        {/* 2-line preview with fade */}
        <div className="relative mt-2 pl-1 overflow-hidden" style={{ maxHeight: "2.8em" }}>
          <p className="text-[12.5px] text-on-surface-variant leading-relaxed line-clamp-2 whitespace-pre-wrap">
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
        <div className="flex items-center gap-2 mb-4 flex-wrap">
          <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full bg-secondary/10 text-secondary">
            {TONE_LABELS[post.tone] ?? post.tone}
          </span>
          {post.published_at && (
            <span className="text-[10px] font-semibold tracking-[0.07em] uppercase px-2.5 py-1 rounded-full" style={{ background: "rgba(88,97,79,0.12)", color: "#58614f" }}>
              Published{post.published_platform ? ` · ${post.published_platform.charAt(0).toUpperCase() + post.published_platform.slice(1)}` : ""}
            </span>
          )}
          <span className="text-[11px] text-on-surface-variant ml-1">{date}</span>

          <div className="flex-1" />

          {/* Aesthetic score */}
          <div className="flex items-baseline gap-1.5 mr-2">
            <span className="label-caps text-on-surface-variant">Score</span>
            {displayScore !== null && (
              <span className="font-headline text-3xl font-semibold leading-none" style={{ color: scoreColor(displayScore) }}>
                {displayScore}
              </span>
            )}
          </div>

          {/* Collapse chevron */}
          <Button variant="ghost" size="icon" onClick={onToggle} aria-expanded aria-label="Collapse post">
            <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-on-surface-variant" style={{ transform: "rotate(180deg)" }}>
              <polyline points="6 9 12 15 18 9"/>
            </svg>
          </Button>
        </div>

        {/* Row 2: serif title */}
        <h2 className="font-headline text-[1.35rem] text-on-surface leading-snug mb-4">
          {post.topic}
        </h2>

        {/* Row 3: version pills */}
        {hasVersions && (
          <div className="flex items-center gap-2 mb-4 flex-wrap">
            <span className="label-caps text-on-surface-variant mr-1">Versions:</span>
            {post.versions.map((v, i) => {
              const isSelected = i === selectedVersionIdx;
              const isBest = i === bestIdx;
              return (
                <button
                  key={v.id}
                  type="button"
                  aria-pressed={isSelected}
                  onClick={() => setSelectedVersionIdx(i)}
                  className={`min-h-11 sm:min-h-8 text-[0.75rem] font-semibold px-3 rounded-full transition-colors duration-150 ${
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
              <span className="text-[11px] text-on-surface-variant ml-1">
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
        <div role="alert" className="mx-6 mb-4 rounded-xl bg-surface-container px-4 py-3 flex flex-wrap items-center gap-3">
          <span className="text-[0.8125rem] text-on-surface flex-1">Permanently delete this post and all its versions?</span>
          <Button variant="destructive" size="sm" onClick={handleDelete} loading={deleting}>
            Yes, delete
          </Button>
          <Button variant="secondary" size="sm" onClick={() => setConfirmingId(null)}>
            Cancel
          </Button>
        </div>
      )}

      {/* ── Restored message ────────────────────────────────────────────── */}
      {restoredMsg && (
        <p className="mx-6 mb-4 text-xs text-primary bg-primary/5 rounded-lg px-4 py-2.5">{restoredMsg}</p>
      )}

      {/* ── Copy feedback ───────────────────────────────────────────────── */}
      {copied && (
        <p role="status" className="mx-6 mb-4 text-xs text-secondary">Copied to clipboard.</p>
      )}

      {/* ── Diagrams ────────────────────────────────────────────────────── */}
      {activeDiagrams && activeDiagrams.length > 0 && (
        <div className="mx-6 mb-4 space-y-3">
          <p className="label-caps text-on-surface-variant">Diagrams</p>
          {activeDiagrams.map((d) => (
            <DiagramCard key={d.position} svg={d.svg_code} description={d.description} />
          ))}
        </div>
      )}

      {/* ── Card footer ─────────────────────────────────────────────────── */}
      <div
        className="px-6 py-4 flex items-center gap-2 flex-wrap"
        style={{ borderTop: "0.5px solid #dfe3e2" }}
      >
        <Button variant="secondary" size="sm" onClick={handleCopy}>
          {copied ? "Copied" : "Copy"}
        </Button>
        <Button variant="secondary" size="sm" onClick={handleOpenInEditor}>
          Open in editor
        </Button>
        {!post.published_at && (
          <Button variant="secondary" size="sm" onClick={() => onMarkPublished(post.id)}>
            Mark as published
          </Button>
        )}
        <Button
          variant="secondary"
          size="sm"
          className="text-error hover:text-error"
          aria-expanded={isConfirming}
          onClick={() => isConfirming ? setConfirmingId(null) : setConfirmingId(post.id)}
        >
          Delete
        </Button>

        <div className="flex-1" />

        {/* Restore Draft */}
        {hasVersions && (
          <Button onClick={handleRestore} loading={restoring}>
            Restore v{post.versions[selectedVersionIdx].version_number}
          </Button>
        )}
      </div>
    </div>
  );
}

// ─── Page ─────────────────────────────────────────────────────────────────────

export default function HistoryPage() {
  const api = useApi();
  const [posts, setPosts] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [confirmingId, setConfirmingId] = useState<number | null>(null);
  const [search, setSearch] = useState("");
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const { showToast } = useToast();

  // Pure UI sort state
  const [sort, setSort] = useState<"newest" | "oldest" | "score">("newest");
  const [publishFilter, setPublishFilter] = useState<"all" | "published">("all");

  // Publish modal state
  const [publishingPostId, setPublishingPostId] = useState<number | null>(null);
  const [publishSaving, setPublishSaving] = useState(false);
  const [publishSuccessMsg, setPublishSuccessMsg] = useState("");

  const handleDeletePost = (id: number) => {
    setPosts((prev) => prev.filter((p) => p.id !== id));
    setConfirmingId(null);
  };

  const handleMarkPublished = (id: number) => {
    setPublishingPostId(id);
    setPublishSuccessMsg("");
  };

  const handlePublishSave = async (platform: string, publishedContent: string) => {
    if (!publishingPostId) return;
    setPublishSaving(true);
    try {
      const res = await api.markAsPublished(publishingPostId, platform, publishedContent || undefined);
      if (!res.ok) throw new Error("Failed to mark as published");
      // Update local post state
      setPosts((prev) =>
        prev.map((p) =>
          p.id === publishingPostId
            ? { ...p, published_at: new Date().toISOString(), published_platform: platform, published_content: publishedContent || null }
            : p
        )
      );
      if (publishedContent.trim()) {
        setPublishSuccessMsg("Saved. Contendo will learn your voice from this version.");
        setTimeout(() => {
          setPublishingPostId(null);
          setPublishSuccessMsg("");
        }, 1500);
      } else {
        setPublishingPostId(null);
      }
      showToast("Post marked as published", "success");
    } catch {
      showToast("Failed to save — please try again", "error");
    } finally {
      setPublishSaving(false);
    }
  };

  const loadHistory = () => {
    setLoading(true);
    setError("");
    api.getHistory()
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load history");
        return r.json();
      })
      .then((data) => setPosts(data.posts ?? []))
      .catch(() => setError("We couldn't load your posts. Check your connection and try again."))
      .finally(() => setLoading(false));
  };

  useEffect(() => {
    loadHistory();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const filteredPosts = posts
    .filter(p => {
      if (publishFilter === "published" && !p.published_at) return false;
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
    { id: "score", label: "Highest score" },
  ];

  return (
    <div className="-mx-4 -mt-6 -mb-6 sm:-mx-6 md:-mx-10 md:-mt-10 md:-mb-10 min-h-screen bg-background flex flex-col">

      <div className="flex-1 overflow-y-auto px-4 md:px-10 py-8 md:py-10">
        <div className="mb-8">
          <h1 className="font-headline text-[2.2rem] md:text-[2.75rem] text-on-surface leading-tight mb-3">History</h1>
          <p className="text-on-surface-variant text-[0.9375rem] leading-relaxed max-w-lg">
            Every post you&apos;ve written, with its earlier versions. Open one to copy it, edit it or restore a version.
          </p>
        </div>

        {/* Search, filter and sort: on every screen size */}
        <div className="mb-8 flex flex-col gap-3 md:flex-row md:items-end">
          <div className="md:w-80">
            <Label htmlFor="history-search">Search</Label>
            <Input id="history-search" type="search" placeholder="Search your posts" value={search} onChange={(e) => setSearch(e.target.value)} />
          </div>
          <div role="group" aria-label="Show" className="flex gap-1 rounded-md bg-surface-container-low p-1">
            {(["all", "published"] as const).map((f) => (
              <button
                key={f}
                type="button"
                aria-pressed={publishFilter === f}
                onClick={() => setPublishFilter(f)}
                className={`min-h-11 sm:min-h-9 rounded-[0.6rem] px-4 text-[0.875rem] transition-colors ${
                  publishFilter === f ? "bg-surface-container-lowest text-on-surface font-medium" : "text-on-surface-variant hover:text-on-surface"
                }`}
              >
                {f === "all" ? "All posts" : "Published"}
              </button>
            ))}
          </div>
          <div className="md:ml-auto md:w-48">
            <Label htmlFor="history-sort">Sort by</Label>
            <Select id="history-sort" value={sort} onValueChange={(v) => setSort(v as typeof sort)} options={SORT_OPTIONS.map((o) => ({ value: o.id, label: o.label }))} />
          </div>
        </div>

        {loading && <ListSkeleton rows={3} />}

        {!loading && error && <ErrorState message={error} onRetry={loadHistory} />}

        {!loading && !error && posts.length === 0 && (
          <EmptyState
            title="No posts yet"
            body="Every post you write is saved here automatically."
            action={<Button asChild><Link href="/create">Write a post</Link></Button>}
          />
        )}

        {!loading && posts.length > 0 && filteredPosts.length === 0 && (
          <EmptyState
            title="No posts match"
            body={publishFilter === "published" ? "None of your published posts match. Try all posts or a different search." : "Try a different search."}
            action={<Button variant="secondary" onClick={() => { setSearch(""); setPublishFilter("all"); }}>Clear search</Button>}
          />
        )}

        {!loading && filteredPosts.length > 0 && (
          <div className="space-y-3">
            {filteredPosts.map((post) => (
              <PostCard
                key={post.id}
                post={post}
                onDelete={handleDeletePost}
                onMarkPublished={handleMarkPublished}
                confirmingId={confirmingId}
                setConfirmingId={setConfirmingId}
                isExpanded={expandedId === post.id}
                onToggle={() => setExpandedId(expandedId === post.id ? null : post.id)}
              />
            ))}
          </div>
        )}
      </div>

      {/* ── Publish modal ─────────────────────────────────────────────────── */}
      {publishingPostId !== null && (
        publishSuccessMsg ? (
          <div
            className="fixed inset-0 z-50 flex items-center justify-center"
            style={{ background: "rgba(47,51,51,0.35)", backdropFilter: "blur(4px)" }}
          >
            <div
              className="bg-surface-container-lowest rounded-2xl px-8 py-7 flex items-center gap-3"
              style={{ boxShadow: "0px 4px 20px rgba(47,51,51,0.08), 0px 24px 60px rgba(47,51,51,0.12)" }}
            >
              <span style={{ color: "#58614f", fontSize: 18 }}>✓</span>
              <p className="text-[13px] text-on-surface">{publishSuccessMsg}</p>
            </div>
          </div>
        ) : (
          <MarkPublishedDialog
            onSave={handlePublishSave}
            onClose={() => setPublishingPostId(null)}
            saving={publishSaving}
          />
        )
      )}
    </div>
  );
}
