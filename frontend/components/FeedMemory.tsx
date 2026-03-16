"use client";

import { useState, useEffect, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type SourceType = "article" | "youtube" | "image" | "note";

const TABS: { id: SourceType; label: string; description: string }[] = [
  {
    id: "article",
    label: "Article / Text",
    description: "Paste any article, blog post, or long-form text.",
  },
  {
    id: "youtube",
    label: "YouTube",
    description:
      "Paste the transcript manually. Open YouTube → click '...' → 'Show transcript', then copy and paste it here.",
  },
  {
    id: "image",
    label: "Image / Diagram",
    description: "Upload a screenshot, diagram, or whiteboard photo. Claude will extract the knowledge.",
  },
  {
    id: "note",
    label: "Note",
    description: "Freeform thoughts, ideas, or observations.",
  },
];

interface Stats {
  total_chunks: number;
  tags: string[];
}

export default function FeedMemory() {
  const [activeTab, setActiveTab] = useState<SourceType>("article");
  const [content, setContent] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string>("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ chunks_stored: number; tags: string[] } | null>(null);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);

  const fetchStats = async () => {
    try {
      const res = await fetch(`${API}/stats`);
      if (res.ok) setStats(await res.json());
    } catch {}
  };

  useEffect(() => {
    fetchStats();
  }, []);

  const handleTabChange = (tab: SourceType) => {
    setActiveTab(tab);
    setContent("");
    setImageFile(null);
    setImagePreview("");
    setResult(null);
    setError("");
  };

  const handleImageChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (!file) return;
    setImageFile(file);
    const reader = new FileReader();
    reader.onload = (ev) => setImagePreview(ev.target?.result as string);
    reader.readAsDataURL(file);
  };

  const handleSubmit = async () => {
    setError("");
    setResult(null);

    if (activeTab === "image") {
      if (!imageFile) {
        setError("Please select an image file.");
        return;
      }
    } else {
      if (!content.trim()) {
        setError("Please enter some content.");
        return;
      }
    }

    setLoading(true);
    try {
      const body: Record<string, string> = { source_type: activeTab };
      if (activeTab === "image") {
        body.raw_image = imagePreview;
        body.content = "";
      } else {
        body.content = content;
      }

      const res = await fetch(`${API}/ingest`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Ingest failed");
      }

      const data = await res.json();
      setResult(data);
      setContent("");
      setImageFile(null);
      setImagePreview("");
      if (fileInputRef.current) fileInputRef.current.value = "";
      await fetchStats();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const currentTab = TABS.find((t) => t.id === activeTab)!;

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Feed Memory</h1>
        <p className="mt-1 text-gray-500 text-sm">
          Add knowledge to your memory store. It will be chunked, embedded, and made available when you generate posts.
        </p>
      </div>

      {/* Stats bar */}
      {stats && (
        <div className="rounded-xl border border-gray-200 bg-white px-5 py-4 flex items-center justify-between shadow-sm">
          <span className="text-sm text-gray-500">
            <span className="text-gray-900 font-medium">{stats.total_chunks}</span> chunks in memory
          </span>
          {stats.tags.length > 0 && (
            <div className="flex flex-wrap gap-1.5 justify-end max-w-xs">
              {stats.tags.slice(0, 8).map((tag) => (
                <span
                  key={tag}
                  className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-600"
                >
                  {tag}
                </span>
              ))}
              {stats.tags.length > 8 && (
                <span className="text-xs text-gray-400">+{stats.tags.length - 8} more</span>
              )}
            </div>
          )}
        </div>
      )}

      {/* Tab selector */}
      <div className="flex gap-1 rounded-lg bg-gray-100 p-1 border border-gray-200">
        {TABS.map((tab) => (
          <button
            key={tab.id}
            onClick={() => handleTabChange(tab.id)}
            className={`flex-1 px-3 py-2 rounded-md text-sm font-medium transition-colors ${
              activeTab === tab.id
                ? "bg-white text-gray-900 shadow-sm"
                : "text-gray-500 hover:text-gray-700"
            }`}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {/* Description */}
      <p className="text-sm text-gray-400 -mt-4">{currentTab.description}</p>

      {/* Input area */}
      <div className="space-y-4">
        {activeTab === "image" ? (
          <div className="space-y-4">
            <div
              onClick={() => fileInputRef.current?.click()}
              className="border-2 border-dashed border-gray-200 rounded-xl p-10 text-center cursor-pointer hover:border-gray-400 transition-colors bg-white"
            >
              {imagePreview ? (
                <img
                  src={imagePreview}
                  alt="Preview"
                  className="max-h-64 mx-auto rounded-lg object-contain"
                />
              ) : (
                <div className="text-gray-400 text-sm">
                  <p className="text-lg mb-1 text-gray-500">Click to upload</p>
                  <p>PNG, JPG, or WEBP</p>
                </div>
              )}
            </div>
            <input
              ref={fileInputRef}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              onChange={handleImageChange}
              className="hidden"
            />
            {imageFile && (
              <p className="text-xs text-gray-400">{imageFile.name}</p>
            )}
          </div>
        ) : (
          <textarea
            value={content}
            onChange={(e) => setContent(e.target.value)}
            placeholder={
              activeTab === "youtube"
                ? "Paste the YouTube transcript here (use YouTube's transcript feature or otter.ai to get it)"
                : activeTab === "note"
                ? "Write your thoughts, ideas, or observations..."
                : "Paste article or text content here..."
            }
            rows={12}
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 resize-none shadow-sm"
          />
        )}

        {error && (
          <p className="text-sm text-red-500">{error}</p>
        )}

        {result && (
          <div className="rounded-xl border border-green-200 bg-green-50 px-5 py-4">
            <p className="text-sm font-medium text-green-700">
              Stored {result.chunks_stored} chunk{result.chunks_stored !== 1 ? "s" : ""}
            </p>
            {result.tags.length > 0 && (
              <div className="mt-2 flex flex-wrap gap-1.5">
                {result.tags.map((tag) => (
                  <span
                    key={tag}
                    className="text-xs px-2 py-0.5 rounded-full bg-green-100 text-green-700"
                  >
                    {tag}
                  </span>
                ))}
              </div>
            )}
          </div>
        )}

        <button
          onClick={handleSubmit}
          disabled={loading}
          className="w-full rounded-xl bg-gray-900 text-white font-medium py-3 text-sm hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? "Processing..." : "Add to memory"}
        </button>
      </div>
    </div>
  );
}
