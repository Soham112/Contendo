"use client";

import { useState, useEffect, useRef } from "react";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type SourceType = "article" | "file" | "youtube" | "image" | "note";

const TABS: { id: SourceType; label: string; description: string }[] = [
  {
    id: "article",
    label: "Article / Text",
    description: "Paste any article, blog post, or long-form text.",
  },
  {
    id: "file",
    label: "File",
    description: "Upload a PDF, DOCX, or TXT file. Text will be extracted and added to your knowledge base.",
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

const FILE_TYPE_LABELS: Record<string, string> = {
  "application/pdf": "PDF",
  "application/vnd.openxmlformats-officedocument.wordprocessingml.document": "DOCX",
  "text/plain": "TXT",
};

function formatBytes(bytes: number): string {
  if (bytes < 1024) return `${bytes} B`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(1)} KB`;
  return `${(bytes / (1024 * 1024)).toFixed(1)} MB`;
}

interface Stats {
  total_chunks: number;
  tags: string[];
}

export default function FeedMemory() {
  const [activeTab, setActiveTab] = useState<SourceType>("article");
  const [content, setContent] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string>("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ chunks_stored: number; tags: string[] } | null>(null);
  const [error, setError] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docFileInputRef = useRef<HTMLInputElement>(null);

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
    setUploadedFile(null);
    setIsDragging(false);
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

  const acceptDocFile = (file: File) => {
    const allowed = [
      "application/pdf",
      "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
      "text/plain",
    ];
    const extAllowed = file.name.match(/\.(pdf|docx|txt)$/i);
    if (!allowed.includes(file.type) && !extAllowed) {
      setError("Unsupported file type. Please upload a PDF, DOCX, or TXT file.");
      return;
    }
    setError("");
    setUploadedFile(file);
  };

  const handleDocFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    const file = e.target.files?.[0];
    if (file) acceptDocFile(file);
  };

  const handleDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(true);
  };

  const handleDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
  };

  const handleDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) acceptDocFile(file);
  };

  const handleSubmit = async () => {
    setError("");
    setResult(null);

    if (activeTab === "image") {
      if (!imageFile) {
        setError("Please select an image file.");
        return;
      }
    } else if (activeTab === "file") {
      if (!uploadedFile) {
        setError("Please upload a file.");
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
      let res: Response;

      if (activeTab === "file") {
        const formData = new FormData();
        formData.append("file", uploadedFile!);
        res = await fetch(`${API}/ingest-file`, {
          method: "POST",
          body: formData,
        });
      } else {
        const body: Record<string, string> = { source_type: activeTab };
        if (activeTab === "image") {
          body.raw_image = imagePreview;
          body.content = "";
        } else {
          body.content = content;
        }
        res = await fetch(`${API}/ingest`, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify(body),
        });
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Ingest failed");
      }

      const data = await res.json();
      setResult(data);
      setContent("");
      setImageFile(null);
      setImagePreview("");
      setUploadedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (docFileInputRef.current) docFileInputRef.current.value = "";
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
        ) : activeTab === "file" ? (
          <div className="space-y-4">
            {!uploadedFile ? (
              <div
                onDragOver={handleDragOver}
                onDragLeave={handleDragLeave}
                onDrop={handleDrop}
                onClick={() => docFileInputRef.current?.click()}
                className={`border-2 border-dashed rounded-xl p-10 text-center cursor-pointer transition-colors bg-white ${
                  isDragging
                    ? "border-gray-500 bg-gray-50"
                    : "border-gray-200 hover:border-gray-400"
                }`}
              >
                <div className="text-gray-400 text-sm">
                  <p className="text-lg mb-1 text-gray-500">
                    {isDragging ? "Drop file here" : "Click or drag a file here"}
                  </p>
                  <p>PDF, DOCX, or TXT · max 10 MB</p>
                </div>
              </div>
            ) : (
              <div className="rounded-xl border border-gray-200 bg-white px-4 py-3 flex items-center justify-between gap-4">
                <div className="flex items-center gap-3 min-w-0">
                  <span className="text-xs font-medium px-2 py-0.5 rounded-full bg-gray-100 text-gray-600 shrink-0">
                    {FILE_TYPE_LABELS[uploadedFile.type] ??
                      uploadedFile.name.split(".").pop()?.toUpperCase() ??
                      "FILE"}
                  </span>
                  <span className="text-sm text-gray-700 truncate">{uploadedFile.name}</span>
                  <span className="text-xs text-gray-400 shrink-0">{formatBytes(uploadedFile.size)}</span>
                </div>
                <button
                  onClick={() => {
                    setUploadedFile(null);
                    if (docFileInputRef.current) docFileInputRef.current.value = "";
                  }}
                  className="text-xs text-gray-400 hover:text-red-500 shrink-0 transition-colors"
                >
                  Remove
                </button>
              </div>
            )}
            <input
              ref={docFileInputRef}
              type="file"
              accept=".pdf,.docx,.txt"
              onChange={handleDocFileChange}
              className="hidden"
            />
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
          {loading
            ? activeTab === "file" && uploadedFile
              ? `Processing ${uploadedFile.name}…`
              : "Processing…"
            : "Add to memory"}
        </button>
      </div>
    </div>
  );
}
