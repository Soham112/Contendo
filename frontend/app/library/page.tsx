"use client";

import { useEffect, useState } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

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
  article: "bg-blue-100 text-blue-700",
  note: "bg-amber-100 text-amber-700",
  image: "bg-purple-100 text-purple-700",
  youtube: "bg-red-100 text-red-600",
};

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
  const [confirming, setConfirming] = useState(false);
  const [deleting, setDeleting] = useState(false);
  const [deleteError, setDeleteError] = useState("");

  const typeLabel = TYPE_LABELS[source.source_type] ?? source.source_type;
  const typeColor = TYPE_COLORS[source.source_type] ?? "bg-gray-100 text-gray-600";

  const handleDelete = async () => {
    setDeleting(true);
    setDeleteError("");
    try {
      const res = await fetch(`${API}/library/source`, {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_title: source.source_title }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Delete failed");
      }
      const data = await res.json();
      onDelete(source.source_title, data.chunks_removed);
    } catch (e: unknown) {
      setDeleteError(e instanceof Error ? e.message : "Something went wrong.");
      setDeleting(false);
      setConfirming(false);
    }
  };

  return (
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm px-5 py-4 space-y-3">
      <div className="flex items-start justify-between gap-4">
        <div className="flex-1 min-w-0">
          <p className="text-sm font-semibold text-gray-900 leading-snug">
            {source.source_title || "Untitled"}
          </p>
          <div className="mt-2 flex flex-wrap items-center gap-2">
            <span className={`text-xs font-medium px-2 py-0.5 rounded-full ${typeColor}`}>
              {typeLabel}
            </span>
            <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600">
              {source.chunk_count} chunk{source.chunk_count !== 1 ? "s" : ""}
            </span>
            <span className="text-xs text-gray-400">{formatDate(source.ingested_at)}</span>
          </div>
        </div>

        {/* Delete controls */}
        <div className="shrink-0 flex items-center gap-2">
          {confirming ? (
            <>
              <span className="text-xs text-gray-500">Remove from memory?</span>
              <button
                onClick={handleDelete}
                disabled={deleting}
                className="text-xs text-red-600 hover:text-red-700 font-medium disabled:opacity-50 transition-colors"
              >
                {deleting ? "Removing…" : "Yes, remove"}
              </button>
              <button
                onClick={() => { setConfirming(false); setDeleteError(""); }}
                disabled={deleting}
                className="text-xs text-gray-400 hover:text-gray-600 transition-colors"
              >
                Cancel
              </button>
            </>
          ) : (
            <button
              onClick={() => setConfirming(true)}
              className="text-xs text-gray-300 hover:text-red-400 transition-colors"
            >
              Delete
            </button>
          )}
        </div>
      </div>

      {deleteError && (
        <p className="text-xs text-red-500">{deleteError}</p>
      )}

      {source.tags.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {source.tags.map((tag) => (
            <span
              key={tag}
              className="text-xs px-2 py-0.5 rounded-full border border-gray-200 text-gray-500 bg-gray-50"
            >
              {tag}
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function LibraryPage() {
  const [sources, setSources] = useState<Source[]>([]);
  const [totalChunks, setTotalChunks] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");

  const [filter, setFilter] = useState<FilterType>("all");
  const [sort, setSort] = useState<SortOrder>("newest");

  useEffect(() => {
    fetch(`${API}/library`)
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
    .sort((a, b) => {
      const aT = a.ingested_at || "";
      const bT = b.ingested_at || "";
      return sort === "newest" ? bT.localeCompare(aT) : aT.localeCompare(bT);
    });

  const FILTER_TABS: { id: FilterType; label: string }[] = [
    { id: "all", label: "All" },
    { id: "article", label: "Article" },
    { id: "note", label: "Note" },
    { id: "image", label: "Image" },
    { id: "youtube", label: "YouTube" },
  ];

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Library</h1>
        <p className="mt-1 text-gray-500 text-sm">
          Everything you have fed into memory.
        </p>
      </div>

      {loading && <p className="text-sm text-gray-400">Loading...</p>}
      {error && <p className="text-sm text-red-500">{error}</p>}

      {!loading && !error && (
        <>
          {/* Stats bar */}
          <div className="grid grid-cols-3 gap-4">
            {[
              { label: "Sources", value: sources.length },
              { label: "Chunks in memory", value: totalChunks },
              { label: "Unique tags", value: allTags.length },
            ].map(({ label, value }) => (
              <div
                key={label}
                className="rounded-xl border border-gray-200 bg-white shadow-sm px-5 py-4 text-center"
              >
                <p className="text-2xl font-bold text-gray-900 tabular-nums">{value}</p>
                <p className="text-xs text-gray-400 mt-1">{label}</p>
              </div>
            ))}
          </div>

          {/* Filter + sort bar */}
          <div className="flex items-center justify-between gap-4 flex-wrap">
            <div className="flex gap-1.5">
              {FILTER_TABS.map((tab) => (
                <button
                  key={tab.id}
                  onClick={() => setFilter(tab.id)}
                  className={`text-xs px-3 py-1.5 rounded-lg border transition-colors ${
                    filter === tab.id
                      ? "border-gray-900 bg-gray-900 text-white"
                      : "border-gray-200 text-gray-500 hover:border-gray-400 hover:text-gray-800 bg-white"
                  }`}
                >
                  {tab.label}
                </button>
              ))}
            </div>
            <select
              value={sort}
              onChange={(e) => setSort(e.target.value as SortOrder)}
              className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600 bg-white focus:outline-none focus:border-gray-400"
            >
              <option value="newest">Newest first</option>
              <option value="oldest">Oldest first</option>
            </select>
          </div>

          {/* Empty state */}
          {sources.length === 0 && (
            <div className="rounded-xl border border-gray-200 bg-white px-6 py-12 text-center">
              <p className="text-gray-400 text-sm">Your library is empty.</p>
              <p className="text-gray-400 text-xs mt-1">
                Add articles, notes, and resources in Feed Memory.
              </p>
            </div>
          )}

          {/* No results after filter */}
          {sources.length > 0 && filtered.length === 0 && (
            <div className="rounded-xl border border-gray-200 bg-white px-6 py-8 text-center">
              <p className="text-gray-400 text-sm">
                No {TYPE_LABELS[filter] ?? filter} sources yet.
              </p>
            </div>
          )}

          {/* Source cards */}
          {filtered.length > 0 && (
            <div className="space-y-3">
              {filtered.map((source, i) => (
                <SourceCard
                  key={i}
                  source={source}
                  onDelete={handleSourceDeleted}
                />
              ))}
            </div>
          )}
        </>
      )}
    </div>
  );
}
