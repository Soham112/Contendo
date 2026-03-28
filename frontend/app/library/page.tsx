"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi } from "@/lib/api";

interface Source {
  source_title: string;
  source_type: string;
  ingested_at: string;
  chunk_count: number;
  tags: string[];
}

const TYPE_LABELS: Record<string, string> = {
  article: "Article",
  note: "Note",
  image: "Image",
  youtube: "YouTube",
};

const TYPE_COLORS: Record<string, string> = {
  article: "bg-surface-container text-secondary border-surface-container-high",
  note: "bg-surface-container text-secondary border-surface-container-high",
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
type SortOrder = "newest" | "oldest";

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
}: {
  source: Source;
  onDelete: (source_title: string, chunks_removed: number) => void;
}) {
  const api = useApi();
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const { showToast } = useToast();

  const typeLabel = TYPE_LABELS[source.source_type] ?? source.source_type;
  const typeColor = TYPE_COLORS[source.source_type] ?? "bg-surface-container-low border-surface-container-high text-outline";
  const handleDelete = async () => {
    setDeleting(true);
    setDeleteError("");
    try {
      const res = await api.deleteSource(source.source_title);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Delete failed");
      }
      const data = await res.json();
      onDelete(source.source_title, data.chunks_removed);
      showToast("Source removed from memory", "success");
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : "Something went wrong.");
      showToast("Failed to remove source", "error");
      setConfirming(false);
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

        {/* Hover action row */}
        <div className="absolute inset-0 bg-on-surface/10 opacity-0 group-hover:opacity-100 transition-opacity duration-200 flex items-end justify-center gap-2 pb-3">
          {/* Sparkle */}
          <button className="w-8 h-8 rounded-full bg-surface-container-lowest/90 flex items-center justify-center shadow-card hover:bg-surface-container-low transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-secondary">
              <path d="M12 3l1.5 5.5L19 10l-5.5 1.5L12 17l-1.5-5.5L5 10l5.5-1.5z"/>
            </svg>
          </button>
          {/* Upload */}
          <button className="w-8 h-8 rounded-full bg-surface-container-lowest/90 flex items-center justify-center shadow-card hover:bg-surface-container-low transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-secondary">
              <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/>
              <polyline points="17 8 12 3 7 8"/>
              <line x1="12" y1="3" x2="12" y2="15"/>
            </svg>
          </button>
          {/* Arrow forward */}
          <button className="w-8 h-8 rounded-full bg-surface-container-lowest/90 flex items-center justify-center shadow-card hover:bg-surface-container-low transition-colors">
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-secondary">
              <line x1="5" y1="12" x2="19" y2="12"/>
              <polyline points="12 5 19 12 12 19"/>
            </svg>
          </button>
          {/* Trash */}
          <button
            onClick={() => setConfirming(true)}
            className="w-8 h-8 rounded-full bg-surface-container-lowest/90 flex items-center justify-center shadow-card hover:bg-error/10 transition-colors"
          >
            <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-error">
              <polyline points="3 6 5 6 21 6"/>
              <path d="M19 6l-1 14a2 2 0 0 1-2 2H8a2 2 0 0 1-2-2L5 6"/>
              <path d="M10 11v6M14 11v6"/>
              <path d="M9 6V4a1 1 0 0 1 1-1h4a1 1 0 0 1 1 1v2"/>
            </svg>
          </button>
        </div>
      </div>

      {/* Card body */}
      <div className="px-4 py-3.5 flex flex-col gap-2 flex-1">
        {/* Date + chunk count */}
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-outline-variant">{formatDate(source.ingested_at)}</span>
          <span className="flex items-center gap-1 text-[11px] text-outline">
            <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
              <rect x="2" y="7" width="20" height="14" rx="2"/>
              <path d="M16 7V5a2 2 0 0 0-2-2h-4a2 2 0 0 0-2 2v2"/>
              <line x1="12" y1="12" x2="12" y2="16"/>
              <line x1="10" y1="14" x2="14" y2="14"/>
            </svg>
            {source.chunk_count} Chunks
          </span>
        </div>

        {/* Title */}
        <p className="font-headline text-[14px] text-on-surface leading-snug line-clamp-2 font-semibold">
          {source.source_title || "Untitled"}
        </p>

        {/* Tags */}
        {source.tags.length > 0 && (
          <div className="flex flex-wrap gap-1 mt-auto pt-1">
            {source.tags.slice(0, 3).map((tag) => (
              <span key={tag} className="text-[10px] px-1.5 py-0.5 rounded-full border border-surface-container-high text-outline bg-surface-container">
                {tag}
              </span>
            ))}
          </div>
        )}
      </div>

      {/* Delete confirm overlay */}
      {confirming && (
        <div className="absolute inset-0 bg-surface-container-lowest/95 flex flex-col items-center justify-center gap-3 rounded-2xl p-4 text-center">
          <p className="text-sm font-medium text-on-surface">Remove from memory?</p>
          <p className="text-xs text-outline leading-relaxed">{source.source_title}</p>
          {deleteError && <p className="text-xs text-error">{deleteError}</p>}
          <div className="flex gap-2">
            <button
              onClick={handleDelete}
              disabled={deleting}
              className="text-xs text-white bg-error rounded-lg px-3 py-1.5 font-medium hover:opacity-80 disabled:opacity-50 transition-opacity"
            >
              {deleting ? "Removing…" : "Yes, remove"}
            </button>
            <button
              onClick={() => { setConfirming(false); setDeleteError(""); }}
              disabled={deleting}
              className="text-xs text-secondary border border-surface-container-high rounded-lg px-3 py-1.5 hover:text-on-surface transition-colors"
            >
              Cancel
            </button>
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
      className="bg-surface-container-lowest rounded-2xl shadow-card hover:shadow-card-hover transition-all duration-200 flex flex-col items-center justify-center gap-2 min-h-[260px] border border-dashed border-outline-variant/30 hover:border-outline-variant/60 group"
    >
      <div className="w-10 h-10 rounded-full bg-surface-container flex items-center justify-center group-hover:bg-surface-container-high transition-colors">
        <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-outline group-hover:text-secondary transition-colors">
          <line x1="12" y1="5" x2="12" y2="19"/>
          <line x1="5" y1="12" x2="19" y2="12"/>
        </svg>
      </div>
      <p className="text-sm font-medium text-secondary group-hover:text-on-surface transition-colors">Add New Source</p>
      <p className="text-xs text-outline-variant">Link, File, or Media</p>
    </button>
  );
}

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

  // Pure UI state
  const [viewMode, setViewMode] = useState<"grid" | "list">("grid");
  const [visibleCount, setVisibleCount] = useState(6);

  useEffect(() => {
    api.getLibrary()
      .then((r) => {
        if (!r.ok) throw new Error("Failed to load library");
        return r.json();
      })
      .then((data) => {
        setSources(data.sources ?? []);
        setTotalChunks(data.total_chunks ?? 0);
      })
      .catch(() => setError("Could not load library. Is the backend running?"))
      .finally(() => setLoading(false));
  }, []);

  const handleSourceDeleted = (source_title: string, chunks_removed: number) => {
    setSources((prev) => prev.filter((s) => s.source_title !== source_title));
    setTotalChunks((prev) => Math.max(0, prev - chunks_removed));
  };

  const allTags = Array.from(new Set(sources.flatMap((s) => s.tags))).sort();

  const filtered = sources
    .filter((s) => filter === "all" || s.source_type === filter)
    .filter((s) => {
      if (!search.trim()) return true;
      const q = search.toLowerCase();
      return (
        s.source_title.toLowerCase().includes(q) ||
        s.tags.some((t) => t.toLowerCase().includes(q))
      );
    })
    .sort((a, b) => {
      const aT = a.ingested_at || "";
      const bT = b.ingested_at || "";
      return sort === "newest" ? bT.localeCompare(aT) : aT.localeCompare(bT);
    });

  const FILTER_TABS: { id: FilterType; label: string }[] = [
    { id: "all", label: "All Sources" },
    { id: "article", label: "Articles" },
    { id: "note", label: "Notes" },
    { id: "image", label: "Images" },
    { id: "youtube", label: "Videos" },
  ];

  const visibleSources = filtered.slice(0, visibleCount);

  return (
    <div className="-mx-10 -mt-10 -mb-10 min-h-screen bg-background flex flex-col">

      {/* ── Top header bar ─────────────────────────────────────────────────── */}
      <div
        style={{ borderBottom: "0.5px solid #dfe3e2", height: "56px" }}
        className="flex items-center px-10 bg-background shrink-0 gap-4"
      >
        {/* Search */}
        <div className="relative flex-1 max-w-sm">
          <svg className="absolute left-3 top-1/2 -translate-y-1/2 text-outline-variant" width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <circle cx="11" cy="11" r="8"/><line x1="21" y1="21" x2="16.65" y2="16.65"/>
          </svg>
          <input
            type="text"
            placeholder="Search your library..."
            value={search}
            onChange={(e) => setSearch(e.target.value)}
            className="w-full pl-9 pr-4 py-1.5 text-[13px] bg-surface-container-low rounded-full border border-surface-container-high focus:outline-none focus:border-outline-variant transition-all text-on-surface placeholder:text-outline-variant"
          />
        </div>

        <div className="flex-1" />

        {/* Bell */}
        <button className="w-8 h-8 flex items-center justify-center rounded-full hover:bg-surface-container transition-colors">
          <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round" className="text-outline">
            <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9"/>
            <path d="M13.73 21a2 2 0 0 1-3.46 0"/>
          </svg>
        </button>

        {/* User pill */}
        <div className="flex items-center gap-2">
          <div className="w-7 h-7 rounded-full bg-primary flex items-center justify-center">
            <span className="text-[10px] font-bold text-white">U</span>
          </div>
          <span className="text-[13px] font-medium text-on-surface">User</span>
        </div>
      </div>

      {/* ── Main content ───────────────────────────────────────────────────── */}
      <div className="flex-1 overflow-y-auto px-10 py-8">

        {loading && <p className="text-sm text-outline">Loading...</p>}
        {error && <p className="text-sm text-error">{error}</p>}

        {!loading && !error && (
          <>
            {/* ── Title + stats row ──────────────────────────────────────── */}
            <div className="flex items-start justify-between gap-8 mb-8">
              {/* Left: breadcrumb + two-line title */}
              <div>
                <p className="label-caps text-outline mb-2">Workspace / Library</p>
                <h1 className="font-headline text-[2.75rem] text-on-surface leading-[1.1]">Collected</h1>
                <h1 className="font-headline text-[2.75rem] italic text-on-surface leading-[1.1]">Sources</h1>
              </div>

              {/* Right: stats tiles */}
              <div className="flex gap-3 shrink-0 pt-2">
                {[
                  { value: sources.length, label: "Total Sources" },
                  { value: totalChunks >= 1000 ? `${(totalChunks / 1000).toFixed(1)}k` : totalChunks, label: "AI Chunks" },
                  { value: allTags.length, label: "Active Tags" },
                ].map(({ value, label }) => (
                  <div
                    key={label}
                    className="rounded-xl bg-surface-container-lowest px-5 py-4 text-center min-w-[90px]"
                    style={{ outline: "1px solid rgba(174,179,178,0.15)" }}
                  >
                    <p className="font-headline text-2xl text-on-surface tabular-nums">{value}</p>
                    <p className="label-caps text-outline mt-1.5">{label}</p>
                  </div>
                ))}
              </div>
            </div>

            {/* ── Filter tabs + controls ─────────────────────────────────── */}
            <div className="flex items-end justify-between mb-6" style={{ borderBottom: "1px solid #dfe3e2" }}>
              {/* Underline tabs */}
              <div className="flex gap-6">
                {FILTER_TABS.map((tab) => (
                  <button
                    key={tab.id}
                    onClick={() => { setFilter(tab.id); setVisibleCount(6); }}
                    className={`pb-3 text-[13px] font-medium transition-colors relative whitespace-nowrap ${
                      filter === tab.id
                        ? "text-on-surface"
                        : "text-outline hover:text-secondary"
                    }`}
                  >
                    {tab.label}
                    {filter === tab.id && (
                      <span className="absolute bottom-0 left-0 right-0 h-[2px] bg-on-surface rounded-full" />
                    )}
                  </button>
                ))}
              </div>

              {/* Right controls */}
              <div className="flex items-center gap-2 pb-3">
                {/* Filters button */}
                <button className="flex items-center gap-1.5 text-[12px] text-secondary border border-surface-container-high rounded-lg px-3 py-1.5 hover:border-outline-variant hover:text-on-surface transition-colors bg-surface-container-lowest">
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="4" y1="6" x2="20" y2="6"/><line x1="8" y1="12" x2="16" y2="12"/><line x1="11" y1="18" x2="13" y2="18"/>
                  </svg>
                  Filters
                </button>

                {/* Sort */}
                <button
                  onClick={() => setSort(s => s === "newest" ? "oldest" : "newest")}
                  className="flex items-center gap-1.5 text-[12px] text-secondary border border-surface-container-high rounded-lg px-3 py-1.5 hover:border-outline-variant hover:text-on-surface transition-colors bg-surface-container-lowest"
                >
                  <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                    <line x1="12" y1="5" x2="12" y2="19"/><polyline points="19 12 12 19 5 12"/>
                  </svg>
                  {sort === "newest" ? "Date Added" : "Oldest First"}
                </button>

                {/* Grid / List toggle */}
                <div className="flex border border-surface-container-high rounded-lg overflow-hidden">
                  <button
                    onClick={() => setViewMode("grid")}
                    className={`px-2.5 py-1.5 transition-colors ${viewMode === "grid" ? "bg-surface-container text-on-surface" : "bg-surface-container-lowest text-outline hover:text-secondary"}`}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <rect x="3" y="3" width="7" height="7"/><rect x="14" y="3" width="7" height="7"/><rect x="14" y="14" width="7" height="7"/><rect x="3" y="14" width="7" height="7"/>
                    </svg>
                  </button>
                  <button
                    onClick={() => setViewMode("list")}
                    className={`px-2.5 py-1.5 transition-colors border-l border-surface-container-high ${viewMode === "list" ? "bg-surface-container text-on-surface" : "bg-surface-container-lowest text-outline hover:text-secondary"}`}
                  >
                    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
                      <line x1="8" y1="6" x2="21" y2="6"/><line x1="8" y1="12" x2="21" y2="12"/><line x1="8" y1="18" x2="21" y2="18"/><line x1="3" y1="6" x2="3.01" y2="6"/><line x1="3" y1="12" x2="3.01" y2="12"/><line x1="3" y1="18" x2="3.01" y2="18"/>
                    </svg>
                  </button>
                </div>
              </div>
            </div>

            {/* ── Empty states ───────────────────────────────────────────── */}
            {sources.length === 0 && (
              <div className="rounded-2xl bg-surface-container-lowest shadow-card px-6 py-12 text-center">
                <p className="text-outline text-sm">Your library is empty.</p>
                <p className="text-outline-variant text-xs mt-1">Add articles, notes, and resources in Feed Memory.</p>
              </div>
            )}

            {sources.length > 0 && filtered.length === 0 && (
              <div className="rounded-2xl bg-surface-container-lowest shadow-card px-6 py-8 text-center">
                <p className="text-outline text-sm">No {TYPE_LABELS[filter] ?? filter} sources yet.</p>
              </div>
            )}

            {/* ── Source grid ────────────────────────────────────────────── */}
            {filtered.length > 0 && viewMode === "grid" && (
              <div className="grid grid-cols-3 gap-4">
                {visibleSources.map((source, i) => (
                  <SourceCard
                    key={i}
                    source={source}
                    onDelete={handleSourceDeleted}
                  />
                ))}
                <AddSourceCard onClick={() => router.push("/feed-memory")} />
              </div>
            )}

            {/* ── Source list (list view) ─────────────────────────────────── */}
            {filtered.length > 0 && viewMode === "list" && (
              <div className="grid grid-cols-1 gap-3">
                {visibleSources.map((source, i) => (
                  <SourceCard
                    key={i}
                    source={source}
                    onDelete={handleSourceDeleted}
                  />
                ))}
                <AddSourceCard onClick={() => router.push("/feed-memory")} />
              </div>
            )}

            {/* ── Pagination ─────────────────────────────────────────────── */}
            {filtered.length > 0 && (
              <div className="flex flex-col items-center mt-10 gap-3">
                <p className="label-caps text-outline">
                  Showing {Math.min(visibleCount, filtered.length)} of {filtered.length} Sources
                </p>
                {visibleCount < filtered.length && (
                  <button
                    onClick={() => setVisibleCount(v => v + 6)}
                    className="rounded-full border border-outline-variant/30 bg-surface-container-lowest px-8 py-2.5 text-[13px] font-medium text-secondary hover:text-on-surface hover:border-outline-variant shadow-card hover:shadow-card-hover transition-all duration-200"
                  >
                    Load More Archives
                  </button>
                )}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
