"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi } from "@/lib/api";
import type { ClusterItem, ClusterSourceItem } from "@/lib/api";
import {
  DELETE_FAILED_MESSAGE, applyAuthorship, deleteOutcome, focusOn, needsAnswer, removeSource, sourceKey,
  type AuthorshipChoice,
} from "@/lib/library";
import { AuthorshipControl } from "@/components/library/AuthorshipControl";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { Skeleton } from "@/components/ui/card";
import { Input, Label } from "@/components/ui/field";
import { Select } from "@/components/ui/select";
import { EmptyState, ErrorState } from "@/components/ui/states";
import { chipClass } from "@/components/ui/chip";

interface Source {
  source_id: string;
  source_title: string;
  source_type: string;
  ingested_at: string;
  chunk_count: number;
  tags: string[];
  retrieval_count: number;
  authorship: string | null;
  authorship_set_by: string | null;
}

const TYPE_LABELS: Record<string, string> = {
  article: "Article",
  note: "Note",
  personal_note: "Personal Note",
  saved_content: "Saved Content",
  image: "Image",
  youtube: "YouTube",
};

const TYPE_COLORS: Record<string, string> = {
  article: "bg-surface-container text-secondary border-surface-container-high",
  note: "bg-surface-container text-secondary border-surface-container-high",
  personal_note: "bg-surface-container text-secondary border-surface-container-high",
  saved_content: "bg-surface-container text-secondary border-surface-container-high",
  image: "bg-surface-container text-secondary border-surface-container-high",
  youtube: "bg-surface-container text-secondary border-surface-container-high",
};

// ── Deterministic gradient per card title ──────────────────────────────────
const TITLE_GRADIENTS = [
  "bg-gradient-to-br from-primary-container to-secondary-container",
  "bg-gradient-to-br from-secondary-container to-primary-fixed-dim",
  "bg-gradient-to-br from-primary-fixed-dim to-surface-container-high",
  "bg-gradient-to-br from-tertiary-fixed to-secondary-container",
  "bg-gradient-to-br from-surface-container-high to-primary-container",
  "bg-gradient-to-br from-secondary-fixed-dim to-tertiary-fixed",
];

function getTitleGradient(title: string): string {
  const sum = title.split("").reduce((acc, ch) => acc + ch.charCodeAt(0), 0);
  return TITLE_GRADIENTS[sum % 6];
}

// ── Source-type illustration icons ─────────────────────────────────────────
function getSourceIcon(type: string): React.ReactNode {
  switch (type) {
    case "article":
      return (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#58614f" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20" />
          <path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z" />
          <line x1="9" y1="7" x2="15" y2="7" />
          <line x1="9" y1="11" x2="15" y2="11" />
          <line x1="9" y1="15" x2="13" y2="15" />
        </svg>
      );
    case "personal_note":
    case "saved_content":
    case "note":
      return (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#81543c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
          <path d="M12 20h9" />
          <path d="M16.5 3.5a2.121 2.121 0 0 1 3 3L7 19l-4 1 1-4L16.5 3.5z" />
        </svg>
      );
    case "youtube":
      return (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#81543c" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
          <circle cx="12" cy="12" r="10" />
          <polygon points="10 8 16 12 10 16 10 8" />
        </svg>
      );
    case "image":
      return (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#645e57" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
      );
    default:
      return (
        <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="#777c7b" strokeWidth="1.2" strokeLinecap="round" strokeLinejoin="round">
          <polygon points="12 2 2 7 12 12 22 7 12 2" />
          <polyline points="2 17 12 22 22 17" />
          <polyline points="2 12 12 17 22 12" />
        </svg>
      );
  }
}

type FilterType = "all" | "article" | "note" | "image" | "youtube";
type SortOrder = "newest" | "oldest" | "most-used";

function formatDate(iso: string): string {
  if (!iso) return "Unknown date";
  const date = new Date(iso);
  const now = new Date();
  const diffMs = now.getTime() - date.getTime();
  const diffDays = Math.floor(diffMs / (1000 * 60 * 60 * 24));
  if (diffDays === 0) return "Today";
  if (diffDays === 1) return "Yesterday";
  if (diffDays < 7) return `${diffDays} days ago`;
  return date.toLocaleDateString("en-US", { month: "short", day: "numeric", year: "numeric" });
}

function SourceCard({
  source,
  onDelete,
  onAuthorshipSaved,
}: {
  source: Source;
  onDelete: (source_id: string, chunks_removed: number) => void;
  onAuthorshipSaved: (source_id: string, authorship: AuthorshipChoice) => void;
}) {
  const api = useApi();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const { showToast } = useToast();

  const typeLabel = TYPE_LABELS[source.source_type] ?? source.source_type;
  const typeColor = TYPE_COLORS[source.source_type] ?? "bg-surface-container-low border-surface-container-high text-on-surface-variant";
  const handleDelete = async () => {
    setDeleting(true);
    setDeleteError("");
    // The card is removed only after the backend confirms; on any failure it
    // stays, with the confirm panel open to show the error.
    try {
      const outcome = await deleteOutcome(await api.deleteSource(source.source_id));
      if (outcome.ok) {
        onDelete(source.source_id, outcome.chunksRemoved);
        showToast("Source removed from memory", "success");
      } else {
        setDeleteError(outcome.message);
        showToast(outcome.message, "error");
      }
    } catch {
      setDeleteError(DELETE_FAILED_MESSAGE);
      showToast(DELETE_FAILED_MESSAGE, "error");
    } finally {
      setDeleting(false);
    }
  };

  return (
    <div className="group relative bg-surface-container-lowest rounded-2xl overflow-hidden shadow-card hover:shadow-card-hover transition-all duration-200 flex flex-col">
      {/* Cover image placeholder */}
      <div className={`relative h-44 ${getTitleGradient(source.source_title)} shrink-0 flex items-center justify-center`}>
        {/* Type badge */}
        <span className={`absolute top-3 left-3 text-[10px] font-semibold tracking-[0.06em] uppercase px-2 py-0.5 rounded-full border ${typeColor}`}>
          {typeLabel}
        </span>

        {/* Source-type illustration */}
        <div className="opacity-60">
          {getSourceIcon(source.source_type)}
        </div>

        {/* Remove: always visible, so touch and keyboard users can reach it */}
        <Button
          variant="ghost"
          size="icon"
          onClick={() => setConfirming(true)}
          aria-label={`Remove ${source.source_title || "this source"}`}
          className="absolute top-2 right-2 bg-surface-container-lowest/90 text-error hover:bg-surface-container-lowest hover:text-error"
        >
          <svg aria-hidden="true" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <polyline points="3 6 5 6 21 6"/>
            <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
            <path d="M10 11v6M14 11v6"/>
            <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
          </svg>
        </Button>
      </div>

      {/* Card body */}
      <div className="px-4 py-3.5 flex flex-col gap-2 flex-1">
        {/* Date + chunk count */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-on-surface-variant">{formatDate(source.ingested_at)}</span>
          <span className="flex items-center gap-1 text-[11px] text-on-surface-variant">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="7" width="20" height="14" rx="2"/>
              <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
              <line x1="12" y1="12" x2="12" y2="16"/>
              <line x1="10" y1="14" x2="14" y2="14"/>
            </svg>
            {source.chunk_count} {source.chunk_count === 1 ? "passage" : "passages"}
          </span>
        </div>

        {/* Retrieval count */}
        {source.retrieval_count === 0 ? (
          <span className="text-[11px] text-on-surface-variant">Not used in a post yet</span>
        ) : source.retrieval_count >= 5 ? (
          <span className="flex items-center gap-1 text-[11px]" style={{ color: "#58614f" }}>
            <span style={{ fontSize: "8px", lineHeight: 1 }}>●</span>
            Used {source.retrieval_count} times
          </span>
        ) : (
          <span className="text-[11px] text-on-surface-variant">
            Used {source.retrieval_count} time{source.retrieval_count === 1 ? "" : "s"}
          </span>
        )}

        {/* Title */}
        <p className="font-headline text-[14px] text-on-surface leading-snug line-clamp-2 font-semibold">
          {source.source_title || "Untitled"}
        </p>

        <AuthorshipControl source={source} onSaved={onAuthorshipSaved} />

        {/* Tags */}
        {source.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-auto pt-1">
            {source.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded-full border border-surface-container-high text-on-surface-variant bg-surface-container">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirm overlay */}
      {confirming && (
        <div role="alert" className="absolute inset-0 bg-surface-container-lowest/95 flex flex-col items-center justify-center gap-3 rounded-2xl p-4 text-center">
          <p className="text-sm font-medium text-on-surface">Remove this from your library?</p>
          <p className="text-xs text-on-surface-variant leading-relaxed">{source.source_title}</p>
          {deleteError && <p className="text-xs text-error">{deleteError}</p>}
          <div className="flex gap-2">
            <Button variant="destructive" size="sm" onClick={handleDelete} loading={deleting}>
              Yes, remove
            </Button>
            <Button variant="secondary" size="sm" onClick={() => { setConfirming(false); setDeleteError(""); }} disabled={deleting}>
              Cancel
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}

function AddSourceCard({ onClick }: { onClick: () => void }) {
  return (
    <button
      onClick={onClick}
      type="button"
      className="bg-surface-container-lowest rounded-2xl hover:bg-surface-container-low transition-colors duration-150 flex flex-col items-center justify-center gap-2 min-h-[200px] px-4 py-8 border border-dashed border-outline hover:border-primary group focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
    >
      <div className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center group-hover:bg-surface-container-high transition-colors">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-on-surface-variant group-hover:text-secondary transition-colors">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </div>
      <p className="text-sm font-medium text-on-surface">Add a source</p>
      <p className="text-xs text-on-surface-variant">A link, a file or a note</p>
    </button>
  );
}

// ── Topic Map View ─────────────────────────────────────────────────────────
function TopicMapView({
  clusters,
  unclustered,
  totalSources,
  totalTags,
  loading,
  onSourceClick,
}: {
  clusters: ClusterItem[];
  unclustered: ClusterSourceItem[];
  totalSources: number;
  totalTags: number;
  loading: boolean;
  onSourceClick: (sourceTitle: string) => void;
}) {
  const [openTags, setOpenTags] = useState<Set<string>>(new Set());
  const [showUnclustered, setShowUnclustered] = useState(false);

  const toggleCluster = (tag: string) => {
    setOpenTags(prev => {
      const next = new Set(prev);
      if (next.has(tag)) next.delete(tag); else next.add(tag);
      return next;
    });
  };

  const scrollToCluster = (tag: string) => {
    document.getElementById(`cluster-${tag.replace(/\s+/g, "-")}`)?.scrollIntoView({ behavior: "smooth", block: "start" });
    setOpenTags(prev => new Set(Array.from(prev).concat(tag)));
  };

  const getClusterColor = (index: number): string => {
    const colors = ["#58614f", "#81543c", "#4a6670", "#6b5e45", "#4d5a4d"];
    return colors[index % 5];
  };

  const getSourceTypeDotColor = (sourceType: string): string => {
    switch (sourceType) {
      case "note":
        return "#58614f";
      case "article":
        return "#81543c";
      case "image":
        return "#4a6670";
      default:
        return "#aeb3b2";
    }
  };

  const pillStyle = (sourceCount: number): { fontSize: string; padding: string; fontWeight: string; background: string; color: string } => {
    if (sourceCount >= 7) {
      return {
        fontSize: "15px",
        padding: "8px 16px",
        fontWeight: "600",
        background: "rgba(88, 97, 79, 0.12)",
        color: "#58614f",
      };
    }
    if (sourceCount >= 4) {
      return {
        fontSize: "13px",
        padding: "6px 12px",
        fontWeight: "500",
        background: "rgba(100, 94, 87, 0.10)",
        color: "#645e57",
      };
    }
    return {
      fontSize: "11px",
      padding: "4px 10px",
      fontWeight: "400",
      background: "#f3f4f3",
      color: "rgba(47, 51, 51, 0.6)",
    };
  };

  if (loading) {
    return (
      <div role="status" aria-label="Loading your topics" className="space-y-4">
        {[...Array(4)].map((_, i) => (
          <Skeleton key={i} className="h-16 w-full" />
        ))}
      </div>
    );
  }

  if (clusters.length === 0 && unclustered.length === 0) {
    return (
      <EmptyState
        title="No topics yet"
        body="Topics appear once two or more sources share a tag. Add a few more sources to see them."
        action={<Button asChild><Link href="/feed-memory">Add a source</Link></Button>}
      />
    );
  }

  return (
    <div className="space-y-8">
      {/* Summary stat pills */}
      <div className="flex gap-3 flex-wrap">
        <span className="label-caps rounded-full px-4 py-2" style={{ background: "rgba(88, 97, 79, 0.10)", color: "#58614f" }}>
          {totalTags} topic{totalTags !== 1 ? "s" : ""} in your knowledge base
        </span>
        <span className="label-caps rounded-full px-4 py-2" style={{ background: "rgba(129, 84, 60, 0.08)", color: "#81543c" }}>
          {totalSources} source{totalSources !== 1 ? "s" : ""} across {totalTags} tag{totalTags !== 1 ? "s" : ""}
        </span>
      </div>

      {/* Tag cloud */}
      {clusters.length > 0 && (
        <div className="flex flex-wrap gap-2">
          {clusters.map(cluster => {
            const { fontSize, padding, fontWeight, background, color } = pillStyle(cluster.source_count);
            return (
              <button
                key={cluster.tag}
                onClick={() => scrollToCluster(cluster.tag)}
                className="rounded-lg transition-all hover:opacity-80"
                style={{
                  fontSize,
                  padding,
                  fontWeight,
                  background,
                  color,
                  letterSpacing: "0.08em",
                  textTransform: "uppercase",
                }}
              >
                {cluster.tag}
                <span className="ml-1.5" style={{ opacity: 0.6 }}>
                  {cluster.source_count}
                </span>
              </button>
            );
          })}
        </div>
      )}

      {/* Cluster sections */}
      <div className="space-y-3">
        {clusters.map((cluster, clusterIndex) => {
          const isOpen = openTags.has(cluster.tag);
          const accentColor = getClusterColor(clusterIndex);
          return (
            <div
              key={cluster.tag}
              id={`cluster-${cluster.tag.replace(/\s+/g, "-")}`}
              className="bg-surface-container-low rounded-lg overflow-hidden"
              style={{
                borderLeft: `4px solid ${accentColor}`,
                paddingLeft: 0,
              }}
            >
              <button
                type="button"
                aria-expanded={isOpen}
                onClick={() => toggleCluster(cluster.tag)}
                className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-surface-container transition-colors"
              >
                <div className="flex items-center gap-3">
                  <span className="font-headline text-[1.1rem] text-on-surface" style={{ fontStyle: "italic" }}>
                    {cluster.tag}
                  </span>
                  <span className="label-caps text-on-surface-variant">
                    {cluster.source_count} source{cluster.source_count !== 1 ? "s" : ""} · {cluster.total_chunks} passage{cluster.total_chunks !== 1 ? "s" : ""}
                  </span>
                </div>
                <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                  className={`text-on-surface-variant transition-transform duration-200 ${isOpen ? "rotate-180" : ""}`}>
                  <polyline points="6 9 12 15 18 9" />
                </svg>
              </button>
              {isOpen && (
                <div className="px-5 pb-4 flex flex-col" style={{ gap: "1.4rem" }}>
                  {cluster.sources.map(source => (
                    <button
                      key={sourceKey(source)}
                      onClick={() => onSourceClick(source.source_title)}
                      className="flex items-center gap-3 text-left group"
                    >
                      <span
                        className="inline-block w-2 h-2 rounded-full shrink-0"
                        style={{ background: getSourceTypeDotColor(source.source_type), marginRight: 8 }}
                      />
                      <span className="text-[13px] text-on-surface group-hover:text-primary transition-colors flex-1 leading-snug">
                        {source.source_title}
                      </span>
                      <span className="label-caps text-on-surface-variant bg-surface-container rounded-full px-2 py-0.5 shrink-0">
                        {TYPE_LABELS[source.source_type] ?? source.source_type}
                      </span>
                      <span className="text-[11px] text-on-surface-variant shrink-0 w-20 text-right">
                        {formatDate(source.ingested_at)}
                      </span>
                    </button>
                  ))}
                </div>
              )}
            </div>
          );
        })}

        {/* Unclustered section */}
        {unclustered.length > 0 && (
          <div className="bg-surface-container rounded-lg overflow-hidden" style={{ borderLeft: `4px solid ${getClusterColor(clusters.length)}` }}>
            <button
              type="button"
              aria-expanded={showUnclustered}
              onClick={() => setShowUnclustered(v => !v)}
              className="w-full flex items-center justify-between px-5 py-4 text-left hover:bg-surface-container-high transition-colors"
            >
              <div className="flex items-center gap-3">
                <span className="font-headline text-[1.1rem] text-on-surface-variant" style={{ fontStyle: "italic" }}>Not in a topic yet</span>
                <span className="label-caps text-on-surface-variant">
                  {unclustered.length} source{unclustered.length !== 1 ? "s" : ""} · unique tags only
                </span>
              </div>
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"
                className={`text-on-surface-variant transition-transform duration-200 ${showUnclustered ? "rotate-180" : ""}`}>
                <polyline points="6 9 12 15 18 9" />
              </svg>
            </button>
            {showUnclustered && (
              <div className="px-5 pb-4 flex flex-col" style={{ gap: "1.4rem" }}>
                {unclustered.map(source => (
                  <button
                    key={sourceKey(source)}
                    onClick={() => onSourceClick(source.source_title)}
                    className="flex items-center gap-3 text-left group"
                  >
                    <span
                      className="inline-block w-2 h-2 rounded-full shrink-0"
                      style={{ background: getSourceTypeDotColor(source.source_type), marginRight: 8 }}
                    />
                    <span className="text-[13px] text-on-surface-variant group-hover:text-secondary transition-colors flex-1 leading-snug">
                      {source.source_title}
                    </span>
                    <span className="label-caps text-on-surface-variant bg-surface-container-high rounded-full px-2 py-0.5 shrink-0">
                      {TYPE_LABELS[source.source_type] ?? source.source_type}
                    </span>
                    <span className="text-[11px] text-on-surface-variant shrink-0 w-20 text-right">
                      {formatDate(source.ingested_at)}
                    </span>
                  </button>
                ))}
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

type MainView = "sources" | "topic-map";

export default function LibraryPage() {
  const api = useApi();
  const router = useRouter();

  const [sources, setSources] = useState<Source[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [filter, setFilter] = useState<FilterType>("all");
  const [sort, setSort] = useState<SortOrder>("newest");
  const [search, setSearch] = useState("");
  const [onlyNeedsAnswer, setOnlyNeedsAnswer] = useState(false);
  // ?source=<id>: show only that source (a link from a duplicate on Feed memory).
  const [focusId, setFocusId] = useState<string | null>(null);
  useEffect(() => {
    setFocusId(new URLSearchParams(window.location.search).get("source"));
  }, []);
  const clearFocus = () => {
    setFocusId(null);
    router.replace("/library");
  };


  // Main view toggle
  const [mainView, setMainView] = useState<MainView>("sources");

  // Topic Map state
  const [clusters, setClusters] = useState<ClusterItem[]>([]);
  const [unclusteredSources, setUnclusteredSources] = useState<ClusterSourceItem[]>([]);
  const [clusterTotalSources, setClusterTotalSources] = useState(0);
  const [clusterTotalTags, setClusterTotalTags] = useState(0);
  const [clustersLoading, setClustersLoading] = useState(false);
  const [clustersError, setClustersError] = useState("");
  const [clustersReload, setClustersReload] = useState(0);

  // Pure UI state
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [visibleCount, setVisibleCount] = useState(6);
  // Bumped by "Try again" to load the library again.
  const [reloadKey, setReloadKey] = useState(0);

  useEffect(() => {
    let active = true;
    const loadLibrary = () => api.getLibrary()
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load library");
        return r.json();
      })
      .then((data) => {
        if (!active) return;
        setSources(data.sources ?? []);
        setTotalChunks(data.total_chunks ?? 0);
        setError("");
      })
      .catch(() => { if (active) setError("We couldn't load your library. Check your connection and try again."); })
      .finally(() => { if (active) setLoading(false); });
    const refreshWhenVisible = () => {
      if (document.visibilityState === "visible") void loadLibrary();
    };
    void loadLibrary();
    window.addEventListener("focus", refreshWhenVisible);
    document.addEventListener("visibilitychange", refreshWhenVisible);
    return () => {
      active = false;
      window.removeEventListener("focus", refreshWhenVisible);
      document.removeEventListener("visibilitychange", refreshWhenVisible);
    };
  }, [reloadKey]);

  useEffect(() => {
    if (mainView !== "topic-map") return;
    setClustersLoading(true);
    setClustersError("");
    api.getLibraryClusters()
      .then(data => {
        setClusters(data.clusters);
        setUnclusteredSources(data.unclustered_sources);
        setClusterTotalSources(data.total_sources);
        setClusterTotalTags(data.total_tags);
      })
      .catch(() => setClustersError("We couldn't load your topics. Try again in a moment."))
      .finally(() => setClustersLoading(false));
  }, [mainView, clustersReload]);

  const handleClusterSourceClick = (sourceTitle: string) => {
    setMainView("sources");
    setSearch(sourceTitle);
  };

  const handleSourceDeleted = (source_id: string, chunks_removed: number) => {
    setSources((prev) => removeSource(prev, source_id));
    setTotalChunks((prev) => Math.max(0, prev - chunks_removed));
  };

  const handleAuthorshipSaved = (source_id: string, authorship: AuthorshipChoice) => {
    setSources((prev) => applyAuthorship(prev, source_id, authorship));
  };

  const needsAnswerCount = sources.filter(needsAnswer).length;

  const allTags = Array.from(new Set(sources.flatMap((s) => s.tags))).sort();

  const filtered = focusOn(sources, focusId)
    .filter((s) => filter === "all" || s.source_type === filter ||
      (filter === "note" && ["personal_note", "saved_content"].includes(s.source_type)))
    .filter((s) => !onlyNeedsAnswer || needsAnswer(s))
    .filter((s) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        s.source_title.toLowerCase().includes(q) ||
        s.tags.some((t) => t.toLowerCase().includes(q))
      );
    })
    .sort((a, b) => {
      if (sort === "most-used") return (b.retrieval_count ?? 0) - (a.retrieval_count ?? 0);
      const aT = a.ingested_at || "";
      const bT = b.ingested_at || "";
      return sort === "newest" ? bT.localeCompare(aT) : aT.localeCompare(bT);
    });

  const FILTER_TABS: { id: FilterType; label: string }[] = [
    { id: "all", label: "All" },
    { id: "article", label: "Articles" },
    { id: "note", label: "Notes" },
    { id: "image", label: "Images" },
    { id: "youtube", label: "Videos" },
  ];

  const visibleSources = filtered.slice(0, visibleCount);

  return (
    <div className="-mx-4 -mt-6 -mb-6 sm:-mx-6 md:-mx-10 md:-mt-10 md:-mb-10 min-h-screen bg-background flex flex-col">

      <div className="flex-1 overflow-y-auto px-4 md:px-10 py-8 md:py-10">
        <div className="flex flex-col md:flex-row items-start justify-between gap-6 md:gap-8 mb-8">
          <div>
            <h1 className="font-headline text-[2.2rem] md:text-[2.75rem] text-on-surface leading-tight">Library</h1>
            <p className="mt-2 max-w-lg text-[0.9375rem] leading-relaxed text-on-surface-variant">
              Everything you&apos;ve given Contendo to write from: articles, notes, videos and images.
            </p>
          </div>
          {!loading && !error && (
            <dl className="grid w-full grid-cols-3 gap-2 md:w-auto md:gap-3">
              {[
                { value: sources.length, label: "Sources" },
                { value: totalChunks >= 1000 ? `${(totalChunks / 1000).toFixed(1)}k` : totalChunks, label: "Passages" },
                { value: allTags.length, label: "Topics" },
              ].map(({ value, label }) => (
                <div key={label} className="rounded-xl bg-surface-container-lowest px-3 py-4 text-center md:min-w-[110px] md:px-5">
                  <dd className="font-headline text-2xl text-on-surface tabular-nums">{value}</dd>
                  <dt className="label-caps text-on-surface-variant mt-1.5">{label}</dt>
                </div>
              ))}
            </dl>
          )}
        </div>

        {loading && (
          <div role="status" aria-label="Loading your library" className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
            {[0, 1, 2].map((n) => (
              <div key={n} className="rounded-2xl bg-surface-container-lowest overflow-hidden">
                <Skeleton className="h-40 w-full rounded-none" />
                <div className="p-4"><Skeleton className="h-3 w-1/3" /><Skeleton className="mt-3 h-4 w-3/4" /></div>
              </div>
            ))}
          </div>
        )}
        {!loading && error && <ErrorState message={error} onRetry={() => { setLoading(true); setReloadKey((k) => k + 1); }} />}

        {!loading && !error && (
          <>
            <div className="mb-6 flex flex-col gap-3 md:flex-row md:flex-wrap md:items-end">
              <div className="md:w-72">
                <Label htmlFor="library-search">Search</Label>
                <Input id="library-search" type="search" placeholder="Search titles and topics" value={search} onChange={(e) => setSearch(e.target.value)} />
              </div>
              <div role="group" aria-label="View" className="flex w-fit gap-1 rounded-md bg-surface-container-low p-1">
                {(["sources", "topic-map"] as const).map((view) => (
                  <button key={view} type="button" aria-pressed={mainView === view} onClick={() => setMainView(view)}
                    className={`min-h-11 sm:min-h-9 rounded-[0.6rem] px-3.5 text-[0.875rem] whitespace-nowrap transition-colors ${mainView === view ? "bg-surface-container-lowest text-on-surface font-medium" : "text-on-surface-variant hover:text-on-surface"}`}>
                    {view === "sources" ? "Sources" : "Topic map"}
                  </button>
                ))}
              </div>
              {mainView === "sources" && (
                <>
                  <div className="md:w-44">
                    <Label htmlFor="library-sort">Sort by</Label>
                    <Select id="library-sort" value={sort} onValueChange={(v) => setSort(v as SortOrder)} options={[{ value: "newest", label: "Newest first" }, { value: "oldest", label: "Oldest first" }, { value: "most-used", label: "Most used" }]} />
                  </div>
                  <div role="group" aria-label="Layout" className="flex w-fit gap-1 rounded-md bg-surface-container-low p-1 md:ml-auto">
                    {(["grid", "list"] as const).map((mode) => (
                      <button key={mode} type="button" aria-pressed={viewMode === mode} aria-label={mode === "grid" ? "Grid" : "List"} onClick={() => setViewMode(mode)}
                        className={`grid h-11 w-11 sm:h-9 sm:w-9 place-items-center rounded-[0.6rem] transition-colors ${viewMode === mode ? "bg-surface-container-lowest text-on-surface" : "text-on-surface-variant hover:text-on-surface"}`}>
                        {mode === "grid" ? (
                          <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/></svg>
                        ) : (
                          <svg aria-hidden="true" width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/></svg>
                        )}
                      </button>
                    ))}
                  </div>
                </>
              )}
            </div>

            {mainView === "sources" && sources.length > 0 && (
              <div role="group" aria-label="Type" className="mb-6 flex gap-1 overflow-x-auto no-scrollbar">
                {FILTER_TABS.map((tab) => (
                  <button key={tab.id} type="button" aria-pressed={filter === tab.id} onClick={() => { setFilter(tab.id); setVisibleCount(6); }}
                    className={chipClass(filter === tab.id)}>
                    {tab.label}
                  </button>
                ))}
                {(needsAnswerCount > 0 || onlyNeedsAnswer) && (
                  <button type="button" aria-pressed={onlyNeedsAnswer}
                    onClick={() => { setOnlyNeedsAnswer((on) => !on); setVisibleCount(6); }}
                    className={chipClass(onlyNeedsAnswer, "sm:ml-auto")}>
                    Needs your answer ({needsAnswerCount})
                  </button>
                )}
              </div>
            )}

            {/* ── Topic Map view ─────────────────────────────────────────── */}
            {mainView === "topic-map" && (
              <>
                {clustersError && <div className="mb-4"><ErrorState message={clustersError} onRetry={() => setClustersReload((k) => k + 1)} /></div>}
                <TopicMapView
                  clusters={clusters}
                  unclustered={unclusteredSources}
                  totalSources={clusterTotalSources}
                  totalTags={clusterTotalTags}
                  loading={clustersLoading}
                  onSourceClick={handleClusterSourceClick}
                />
              </>
            )}

            {/* ── Sources view ───────────────────────────────────────────── */}
            {mainView === "sources" && (
              <>
                {/* Empty states */}
                {sources.length === 0 && (
                  <EmptyState
                    title="Your library is empty"
                    body="Add an article, a note or a video. Contendo writes your posts from what's in here."
                    action={<Button asChild><Link href="/feed-memory">Add your first source</Link></Button>}
                  />
                )}

                {focusId && sources.length > 0 && (
                  <div className="mb-4 flex items-center justify-between gap-3 rounded-xl bg-surface-container px-4 py-3 text-sm text-secondary">
                    <span>{filtered.length > 0 ? "Showing the source you tried to add again." : "That source is no longer in your library."}</span>
                    <Button variant="secondary" size="sm" onClick={clearFocus}>Show all sources</Button>
                  </div>
                )}

                {!focusId && sources.length > 0 && filtered.length === 0 && (
                  <EmptyState
                    title="Nothing matches"
                    body={search.trim() ? "Try a different search."
                      : onlyNeedsAnswer ? "Every source here has an answer."
                      : `You haven't added any ${(TYPE_LABELS[filter] ?? filter).toLowerCase()} sources yet.`}
                    action={<Button variant="secondary" onClick={() => { setSearch(""); setFilter("all"); setOnlyNeedsAnswer(false); }}>Show all sources</Button>}
                  />
                )}

                {/* Source grid */}
                {filtered.length > 0 && viewMode === "grid" && (
                  <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 gap-4">
                    {visibleSources.map((source) => (
                      <SourceCard
                        key={sourceKey(source)}
                        source={source}
                        onDelete={handleSourceDeleted}
                        onAuthorshipSaved={handleAuthorshipSaved}
                      />
                    ))}
                    <AddSourceCard onClick={() => router.push("/feed-memory")} />
                  </div>
                )}

                {/* Source list */}
                {filtered.length > 0 && viewMode === "list" && (
                  <div className="grid grid-cols-1 gap-3">
                    {visibleSources.map((source) => (
                      <SourceCard
                        key={sourceKey(source)}
                        source={source}
                        onDelete={handleSourceDeleted}
                        onAuthorshipSaved={handleAuthorshipSaved}
                      />
                    ))}
                    <AddSourceCard onClick={() => router.push("/feed-memory")} />
                  </div>
                )}

                {/* Pagination */}
                {filtered.length > 0 && (
                  <div className="flex flex-col items-center mt-10 gap-3">
                    <p className="label-caps text-on-surface-variant">
                      Showing {Math.min(visibleCount, filtered.length)} of {filtered.length} sources
                    </p>
                    {visibleCount < filtered.length && (
                      <Button variant="secondary" onClick={() => setVisibleCount(v => v + 6)}>
                        Show more
                      </Button>
                    )}
                  </div>
                )}
              </>
            )}
          </>
        )}
      </div>
    </div>
  );
}
