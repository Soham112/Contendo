"use client";

import { useState, useEffect, useRef } from "react";
import { Puzzle } from "lucide-react";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi } from "@/lib/api";
import ExtensionInstallModal from "@/components/ExtensionInstallModal";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

const isLocalBackend =
  process.env.NEXT_PUBLIC_API_URL?.includes("localhost") ||
  process.env.NEXT_PUBLIC_API_URL?.includes("127.0.0.1");

type SourceType = "article" | "url" | "file" | "youtube" | "image" | "note" | "obsidian";

const ALL_TABS: { id: SourceType; label: string; description: string; localOnly?: boolean }[] = [
  {
    id: "article",
    label: "Article",
    description: "Paste any article, blog post, or long-form text.",
  },
  {
    id: "url",
    label: "URL",
    description:
      "Works with most blogs, news sites, and research pages. Paywalled content and sites requiring login cannot be scraped.",
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
      "Paste a YouTube URL and the transcript is fetched automatically — no manual copying needed.",
  },
  {
    id: "image",
    label: "Image",
    description: "Upload a screenshot, diagram, or whiteboard photo. Claude will extract the knowledge.",
  },
  {
    id: "note",
    label: "Note",
    description: "Freeform thoughts, ideas, or observations.",
  },
  {
    id: "obsidian",
    label: "Obsidian",
    description:
      "Connect your Obsidian vault. All notes will be chunked, embedded, and added to your knowledge base.",
  },
];

// Show all tabs (Obsidian tab now works everywhere)
const TABS = ALL_TABS;

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

interface VaultStats {
  vault_name: string;
  total_files: number;
  total_words: number;
  estimated_chunks: number;
  skipped_files: number;
}

interface ObsidianIngestResult {
  total_files_processed: number;
  total_chunks_stored: number;
  total_words_processed: number;
  skipped_files: number;
  all_tags: string[];
}

const SOURCE_ICONS: Record<SourceType, React.ReactNode> = {
  article: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="2" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M5 6h6M5 9h4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  url: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M6.5 9.5a3.5 3.5 0 0 0 4.95 0l2-2a3.5 3.5 0 0 0-4.95-4.95l-1 1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
      <path d="M9.5 6.5a3.5 3.5 0 0 0-4.95 0l-2 2a3.5 3.5 0 0 0 4.95 4.95l1-1" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  youtube: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="1" y="4" width="14" height="8" rx="2" stroke="currentColor" strokeWidth="1.5"/>
      <path d="M7 6.5l3 1.5-3 1.5V6.5z" fill="currentColor"/>
    </svg>
  ),
  image: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <rect x="2" y="2" width="12" height="12" rx="1.5" stroke="currentColor" strokeWidth="1.5"/>
      <circle cx="5.5" cy="5.5" r="1" fill="currentColor"/>
      <path d="M2 11l4-3 3 2.5 2-1.5 3 3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
    </svg>
  ),
  note: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M3 3h10v8l-3 3H3z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M10 11v3M10 11h3" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
    </svg>
  ),
  file: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M4 2h6l4 4v9H4z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M10 2v4h4" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  ),
  obsidian: (
    <svg width="14" height="14" viewBox="0 0 16 16" fill="none" xmlns="http://www.w3.org/2000/svg">
      <path d="M8 2L2 6v8h12V6z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
      <path d="M8 2l6 4M8 2v12" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
    </svg>
  ),
};

const TOUR_STEPS: { id: SourceType; label: string; description: string }[] = [
  {
    id: "article",
    label: "Article",
    description: "Paste anything you've been reading — blog posts, essays, research, your own notes. This is the fastest way to start.",
  },
  {
    id: "url",
    label: "URL",
    description: "Drop any link. We'll scrape the full article and store it automatically — no copy-paste needed.",
  },
  {
    id: "file",
    label: "File",
    description: "Upload a PDF, Word doc, or plain text file. Good for whitepapers, reports, or saved long-reads.",
  },
  {
    id: "youtube",
    label: "YouTube",
    description: "Paste any YouTube URL — the transcript is fetched automatically. No manual copying needed.",
  },
  {
    id: "image",
    label: "Image",
    description: "Upload a screenshot, slide, or diagram. We'll extract the text and knowledge from it automatically.",
  },
  {
    id: "note",
    label: "Note",
    description: "Write something directly — a half-formed thought, a takeaway, an opinion. Your own words are the strongest signal.",
  },
  {
    id: "obsidian",
    label: "Obsidian",
    description:
      "Import your entire Obsidian vault by uploading a zipped vault file. Preview how many notes will be ingested before committing.",
  },
];

export default function FeedMemory() {
  const api = useApi();
  const [isExtensionModalOpen, setIsExtensionModalOpen] = useState(false);
  const [activeTab, setActiveTab] = useState<SourceType>("article");
  const [content, setContent] = useState("");
  const [imageFile, setImageFile] = useState<File | null>(null);
  const [imagePreview, setImagePreview] = useState<string>("");
  const [uploadedFile, setUploadedFile] = useState<File | null>(null);
  const [isDragging, setIsDragging] = useState(false);
  const [urlInput, setUrlInput] = useState("");
  const [vaultPath, setVaultPath] = useState("");
  const [vaultPreview, setVaultPreview] = useState<VaultStats | null>(null);
  const [obsidianPhase, setObsidianPhase] = useState<"input" | "preview" | "ingesting" | "done">("input");
  const [obsidianResult, setObsidianResult] = useState<ObsidianIngestResult | null>(null);
  const [obsidianMode, setObsidianMode] = useState<"local" | "zip">(isLocalBackend ? "local" : "zip");
  const [zipFile, setZipFile] = useState<File | null>(null);
  const [zipPreview, setZipPreview] = useState<VaultStats | null>(null);
  const [zipIsDragging, setZipIsDragging] = useState(false);
  const [loadingMessage, setLoadingMessage] = useState("Reading vault notes...");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ chunks_stored: number; tags: string[]; title?: string; word_count?: number; duplicate?: boolean } | null>(null);
  const [error, setError] = useState("");
  // YouTube two-path state
  const [ytUrl, setYtUrl] = useState("");
  const [ytTranscript, setYtTranscript] = useState("");
  const [ytVideoId, setYtVideoId] = useState("");
  const [ytFetching, setYtFetching] = useState(false);
  const [ytFetchError, setYtFetchError] = useState("");
  const [ytManualText, setYtManualText] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docFileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  // ── Tooltip tour ─────────────────────────────────────────────────────────────
  const [tourStep, setTourStep] = useState(-1);
  const [tourActive, setTourActive] = useState(false);
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number } | null>(null);
  const tabBarRef = useRef<HTMLDivElement>(null);
  const tabButtonRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Start tour 800ms after mount — only when localStorage key is absent
  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("contendo_feed_tour_done")) return;
    const timer = setTimeout(() => {
      setTourActive(true);
      setTourStep(0);
    }, 800);
    return () => clearTimeout(timer);
  }, []);

  // When tour step changes: switch active tab and measure fixed position for the tooltip
  useEffect(() => {
    if (!tourActive || tourStep < 0) return;
    setActiveTab(TOUR_STEPS[tourStep].id);
    requestAnimationFrame(() => {
      const tabIdx = TABS.findIndex((t) => t.id === TOUR_STEPS[tourStep].id);
      const btn = tabButtonRefs.current[tabIdx];
      const bar = tabBarRef.current;
      if (btn && bar) {
        const barRect = bar.getBoundingClientRect();
        const btnRect = btn.getBoundingClientRect();
        setTooltipPos({
          top: barRect.bottom + 8,
          left: btnRect.left + btnRect.width / 2,
        });
      }
    });
  }, [tourStep, tourActive]);

  const dismissTour = () => {
    setTourActive(false);
    setTourStep(-1);
    if (typeof window !== "undefined") localStorage.setItem("contendo_feed_tour_done", "1");
  };

  const advanceTour = () => {
    if (tourStep < TOUR_STEPS.length - 1) {
      setTourStep(tourStep + 1);
    } else {
      dismissTour();
    }
  };

  // ── YouTube auto-fetch ────────────────────────────────────────────────────

  function isYouTubeUrl(url: string): boolean {
    return /^https?:\/\/(youtu\.be\/|(?:www\.)?youtube\.com\/(watch\?|shorts\/))/i.test(url.trim());
  }

  const handleYtFetch = async (url: string) => {
    const trimmed = url.trim();
    if (!trimmed) return;
    if (!isYouTubeUrl(trimmed)) {
      setYtFetchError("Please paste a YouTube video URL");
      return;
    }
    setYtFetchError("");
    setYtTranscript("");
    setYtVideoId("");
    setYtFetching(true);
    try {
      const res = await api.fetchYoutubeTranscript(trimmed);
      if (!res.ok) {
        const err = await res.json();
        setYtFetchError(err.detail ?? "Failed to fetch transcript");
        return;
      }
      const data = await res.json();
      setYtTranscript(data.transcript);
      setYtVideoId(data.video_id);
    } catch (e: unknown) {
      setYtFetchError(e instanceof Error ? e.message : "Something went wrong");
    } finally {
      setYtFetching(false);
    }
  };

  const fetchStats = async () => {
    try {
      const res = await api.getStats();
      if (res.ok) setStats(await res.json());
    } catch {}
  };

  useEffect(() => {
    fetchStats();
  }, []);

  useEffect(() => {
    if (obsidianPhase !== "ingesting") return;
    setLoadingMessage("Reading vault notes...");
    const t1 = setTimeout(() => setLoadingMessage("Chunking and embedding..."), 5000);
    const t2 = setTimeout(() => setLoadingMessage("Storing in memory..."), 15000);
    return () => { clearTimeout(t1); clearTimeout(t2); };
  }, [obsidianPhase]);

  const handleTabChange = (tab: SourceType) => {
    setActiveTab(tab);
    setContent("");
    setUrlInput("");
    setVaultPath("");
    setVaultPreview(null);
    setObsidianPhase("input");
    setObsidianResult(null);
    setLoadingMessage("Reading vault notes...");
    setImageFile(null);
    setImagePreview("");
    setUploadedFile(null);
    setIsDragging(false);
    setResult(null);
    setError("");
    setYtUrl("");
    setYtTranscript("");
    setYtVideoId("");
    setYtFetching(false);
    setYtFetchError("");
    setYtManualText("");
    // If tour is active, sync to the clicked tab's step
    if (tourActive) {
      const stepIdx = TOUR_STEPS.findIndex((s) => s.id === tab);
      if (stepIdx >= 0 && stepIdx !== tourStep) setTourStep(stepIdx);
    }
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

  const handleVaultPreview = async () => {
    setError("");
    setVaultPreview(null);
    if (!vaultPath.trim()) {
      setError("Please enter your vault folder path.");
      return;
    }
    setLoading(true);
    try {
      const res = await api.obsidianPreview(vaultPath.trim());
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Preview failed");
      }
      const data: VaultStats = await res.json();
      if (data.total_files === 0) {
        setError("No markdown files found in that folder. Make sure you entered the correct vault path.");
        return;
      }
      setVaultPreview(data);
      setObsidianPhase("preview");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleVaultIngest = async () => {
    setError("");
    setObsidianPhase("ingesting");
    setLoading(true);
    try {
      const res = await api.obsidianIngest(vaultPath.trim());
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Ingest failed");
      }
      const data: ObsidianIngestResult = await res.json();
      setObsidianResult(data);
      setObsidianPhase("done");
      await fetchStats();
    } catch (e: unknown) {
      setObsidianPhase("preview");
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleZipPreview = async (file: File) => {
    setError("");
    setZipPreview(null);
    if (file.size > 50 * 1024 * 1024) {
      setError("Zip file exceeds 50 MB limit.");
      return;
    }
    setZipFile(file);
    setLoading(true);
    try {
      const res = await api.obsidianPreviewZip(file);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Preview failed");
      }
      const data: VaultStats = await res.json();
      if (data.total_files === 0) {
        setError("No markdown files found in the zip. Make sure you uploaded a valid Obsidian vault.");
        return;
      }
      setZipPreview(data);
      setObsidianPhase("preview");
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleZipIngest = async () => {
    if (!zipFile) return;
    setError("");
    setObsidianPhase("ingesting");
    setLoading(true);
    try {
      const res = await api.obsidianIngestZip(zipFile);
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Ingest failed");
      }
      const data: ObsidianIngestResult = await res.json();
      setObsidianResult(data);
      setObsidianPhase("done");
      await fetchStats();
    } catch (e: unknown) {
      setObsidianPhase("preview");
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleZipDragOver = (e: React.DragEvent) => {
    e.preventDefault();
    setZipIsDragging(true);
  };

  const handleZipDragLeave = (e: React.DragEvent) => {
    e.preventDefault();
    setZipIsDragging(false);
  };

  const handleZipDrop = (e: React.DragEvent) => {
    e.preventDefault();
    setZipIsDragging(false);
    const file = e.dataTransfer.files?.[0];
    if (file) {
      handleZipPreview(file);
    }
  };

  const resetObsidianZip = () => {
    setError("");
    setZipFile(null);
    setZipPreview(null);
    setObsidianPhase("input");
  };

  const handleSubmit = async () => {
    setError("");
    setResult(null);

    if (activeTab === "image") {
      if (!imageFile) { setError("Please select an image file."); return; }
    } else if (activeTab === "file") {
      if (!uploadedFile) { setError("Please upload a file."); return; }
    } else if (activeTab === "url") {
      if (!urlInput.trim()) { setError("Please enter a URL."); return; }
      if (!urlInput.startsWith("http://") && !urlInput.startsWith("https://")) {
        setError("URL must start with http:// or https://"); return;
      }
    } else if (activeTab === "youtube") {
      if (!ytUrl.trim() && !ytManualText.trim()) {
        setError("Paste a YouTube URL or enter the transcript manually.");
        return;
      }
      if (ytUrl.trim() && !isYouTubeUrl(ytUrl)) {
        setYtFetchError("Please paste a valid YouTube video URL.");
        return;
      }
    } else {
      if (!content.trim()) { setError("Please enter some content."); return; }
    }

    setLoading(true);
    try {
      let res: Response;

      if (activeTab === "file") {
        const formData = new FormData();
        formData.append("file", uploadedFile!);
        res = await api.ingestFile(formData);
      } else if (activeTab === "url") {
        res = await api.scrapeAndIngest(urlInput.trim());
      } else {
        const body: { source_type: string; raw_image?: string; content?: string; source_title?: string } = { source_type: activeTab };
        if (activeTab === "image") { body.raw_image = imagePreview; body.content = ""; }
        else if (activeTab === "youtube") {
          let transcript = ytTranscript; // may already be set by manual textarea
          if (ytUrl.trim()) {
            setYtFetching(true);
            const fetchRes = await api.fetchYoutubeTranscript(ytUrl.trim());
            setYtFetching(false);
            if (!fetchRes.ok) {
              const errData = await fetchRes.json().catch(() => ({})) as { detail?: string };
              setYtFetchError(errData.detail ?? "Failed to fetch transcript");
              return;
            }
            const fetchData = await fetchRes.json();
            transcript = fetchData.transcript;
            setYtTranscript(transcript);
            body.source_title = fetchData.title;
          }
          body.content = transcript;
        }
        else { body.content = content; }
        res = await api.ingestContent(body);
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Ingest failed");
      }

      const data = await res.json();
      setResult(data);
      showToast(`Ingested successfully! Added ${data.chunks_added ?? 0} chunks.`, "success");
      setContent("");
      setUrlInput("");
      setImageFile(null);
      setImagePreview("");
      setUploadedFile(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (docFileInputRef.current) docFileInputRef.current.value = "";
      setYtUrl("");
      setYtTranscript("");
      setYtVideoId("");
      setYtFetchError("");
      setYtManualText("");
      await fetchStats();
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const currentTab = TABS.find((t) => t.id === activeTab)!;
  const effectiveObsidianMode: "local" | "zip" = isLocalBackend ? obsidianMode : "zip";

  const inputLabel =
    activeTab === "url" ? "SOURCE URL" :
    activeTab === "file" ? "DOCUMENT FILE" :
    activeTab === "image" ? "IMAGE / DIAGRAM" :
    activeTab === "obsidian" ? "VAULT PATH" :
    "CONTENT FRAGMENT";

  return (
    <div className="flex flex-col md:flex-row gap-8 max-w-7xl max-md:!max-w-none w-full max-md:!w-full px-4 md:px-0">
      {/* ── Left: main form ───────────────────────────────────── */}
      <div className="flex-1 min-w-0 w-full max-md:!w-full space-y-7">

        {/* Header */}
        <div>
          <h1 className="font-headline text-4xl text-on-surface leading-tight">Feed Memory</h1>
          <p className="mt-2 text-secondary text-[15px] leading-relaxed">
            Transform raw fragments into editorial wisdom. Select a medium to store your inspiration.
          </p>
        </div>

        <div
          role="button"
          tabIndex={0}
          onClick={() => setIsExtensionModalOpen(true)}
          onKeyDown={(e) => {
            if (e.key === "Enter" || e.key === " ") {
              e.preventDefault();
              setIsExtensionModalOpen(true);
            }
          }}
          className="hidden md:flex w-full rounded-xl bg-surface-container-low px-4 py-2.5 items-center gap-2 cursor-pointer hover:bg-surface-container transition-colors text-secondary"
        >
          <Puzzle size={16} className="shrink-0" />
          <span className="text-[13px] font-normal truncate">Install Chrome Extension</span>
        </div>

        {/* Tab selector */}
        <div className="hidden md:flex flex-wrap gap-2" ref={tabBarRef}>
          {TABS.map((tab, idx) => (
            <button
              key={tab.id}
              ref={(el) => { tabButtonRefs.current[idx] = el; }}
              onClick={() => handleTabChange(tab.id)}
              className={`flex items-center gap-1.5 px-4 py-2 rounded-full text-[12.5px] font-medium tracking-wide transition-all duration-150 ${
                activeTab === tab.id
                  ? "btn-primary text-white shadow-card"
                  : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
              }`}
            >
              <span className={activeTab === tab.id ? "text-white/80" : "text-outline"}>
                {SOURCE_ICONS[tab.id]}
              </span>
              {tab.label}
            </button>
          ))}
        </div>

        <div className="md:hidden flex gap-2 overflow-x-auto no-scrollbar pb-1" ref={tabBarRef}>
          {TABS.map((tab, idx) => (
            <button
              key={tab.id}
              ref={(el) => { tabButtonRefs.current[idx] = el; }}
              onClick={() => handleTabChange(tab.id)}
              className={`shrink-0 flex items-center gap-1.5 px-3.5 py-2 rounded-full text-[12px] font-medium tracking-wide transition-all duration-150 ${
                activeTab === tab.id
                  ? "btn-primary text-white shadow-card"
                  : "bg-surface-container text-secondary"
              }`}
            >
              <span className={activeTab === tab.id ? "text-white/80" : "text-outline"}>
                {SOURCE_ICONS[tab.id]}
              </span>
              {tab.label}
            </button>
          ))}
        </div>

        {/* Main input card */}
        <div className="w-full max-md:!w-full bg-surface-container-lowest rounded-2xl shadow-card overflow-hidden">
          {/* Card body */}
          <div className="p-8 max-md:!px-4 space-y-6 w-full max-md:!w-full">

            {activeTab === "obsidian" ? (
              /* ── Obsidian flow ── */
              <div className="space-y-5">
                {isLocalBackend && (
                  <div className="flex gap-2">
                    <button
                      onClick={() => setObsidianMode("local")}
                      className={`px-4 py-2 rounded-full text-[12.5px] font-medium label-caps transition-all ${
                        obsidianMode === "local"
                          ? "bg-primary text-white"
                          : "border border-ghost-border text-secondary hover:text-on-surface"
                      }`}
                    >
                      Local path
                    </button>
                    <button
                      onClick={() => setObsidianMode("zip")}
                      className={`px-4 py-2 rounded-full text-[12.5px] font-medium label-caps transition-all ${
                        obsidianMode === "zip"
                          ? "bg-primary text-white"
                          : "border border-ghost-border text-secondary hover:text-on-surface"
                      }`}
                    >
                      Upload zip
                    </button>
                  </div>
                )}

                {/* Local path flow */}
                {effectiveObsidianMode === "local" ? (
                  <div className="space-y-5">
                    {obsidianPhase === "done" && obsidianResult ? (
                      <div className="space-y-3">
                        <p className="label-caps text-secondary">Vault ingested</p>
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shrink-0">
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                              <path d="M3 8.5l3.5 3.5 6.5-7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          </div>
                          <div>
                            <p className="text-[15px] font-medium text-on-surface">
                              {obsidianResult.total_files_processed} notes ingested
                            </p>
                            <p className="text-sm text-secondary mt-0.5">
                              {obsidianResult.total_chunks_stored} chunks · {obsidianResult.total_words_processed.toLocaleString()} words
                            </p>
                          </div>
                        </div>
                        {obsidianResult.all_tags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {obsidianResult.all_tags.slice(0, 10).map((tag) => (
                              <span key={tag} className="text-[11px] px-2.5 py-1 rounded-full bg-primary-container text-on-primary-container font-medium">
                                #{tag}
                              </span>
                            ))}
                            {obsidianResult.all_tags.length > 10 && (
                              <span className="text-xs text-outline self-center">+{obsidianResult.all_tags.length - 10} more</span>
                            )}
                          </div>
                        )}
                      </div>
                    ) : obsidianPhase === "ingesting" ? (
                      <div className="py-8 text-center space-y-3">
                        <p className="text-[15px] text-muted">Ingesting vault — this may take a minute…</p>
                      </div>
                    ) : (
                      <>
                        <div className="space-y-2">
                          <label className="label-caps text-secondary">Vault folder path</label>
                          <input
                            type="text"
                            value={vaultPath}
                            onChange={(e) => { setVaultPath(e.target.value); setVaultPreview(null); setObsidianPhase("input"); }}
                            onKeyDown={(e) => { if (e.key === "Enter" && obsidianPhase === "input") handleVaultPreview(); }}
                            placeholder="/Users/yourname/Documents/ObsidianVault"
                            className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-outline rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary transition-colors"
                          />
                          <p className="text-xs text-outline">
                            Open Obsidian → Settings → About to find your vault path.
                          </p>
                        </div>
                        {vaultPreview && obsidianPhase === "preview" && (
                          <div className="rounded-xl bg-surface-container-low px-5 py-4 space-y-1">
                            <p className="text-[15px] font-medium text-on-surface">{vaultPreview.vault_name}</p>
                            <p className="text-sm text-secondary">
                              {vaultPreview.total_files} notes · {vaultPreview.total_words.toLocaleString()} words
                            </p>
                            <p className="text-xs text-outline">
                              ~{vaultPreview.estimated_chunks} chunks to store
                            </p>
                            {vaultPreview.skipped_files > 0 && (
                              <p className="text-xs text-outline">{vaultPreview.skipped_files} short notes will be skipped</p>
                            )}
                            {vaultPreview.total_files > 500 && (
                              <p className="text-xs text-secondary mt-2">Large vault — ingestion may take 2–3 minutes. Do not close this tab.</p>
                            )}
                          </div>
                        )}
                      </>
                    )}
                  </div>
                ) : (
                  /* Zip upload flow */
                  <div className="space-y-5">
                    {obsidianPhase === "done" && obsidianResult ? (
                      <div className="space-y-3">
                        <p className="label-caps text-secondary">Vault ingested</p>
                        <div className="flex items-center gap-4">
                          <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shrink-0">
                            <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                              <path d="M3 8.5l3.5 3.5 6.5-7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                            </svg>
                          </div>
                          <div>
                            <p className="text-[15px] font-medium text-on-surface">
                              {obsidianResult.total_files_processed} notes ingested
                            </p>
                            <p className="text-sm text-secondary mt-0.5">
                              {obsidianResult.total_chunks_stored} chunks · {obsidianResult.total_words_processed.toLocaleString()} words
                            </p>
                          </div>
                        </div>
                        {obsidianResult.all_tags.length > 0 && (
                          <div className="flex flex-wrap gap-1.5 pt-1">
                            {obsidianResult.all_tags.slice(0, 10).map((tag) => (
                              <span key={tag} className="text-[11px] px-2.5 py-1 rounded-full bg-primary-container text-on-primary-container font-medium">
                                #{tag}
                              </span>
                            ))}
                            {obsidianResult.all_tags.length > 10 && (
                              <span className="text-xs text-outline self-center">+{obsidianResult.all_tags.length - 10} more</span>
                            )}
                          </div>
                        )}
                      </div>
                    ) : obsidianPhase === "ingesting" ? (
                      <div className="py-8 text-center">
                        <p className="text-[15px] text-muted">Ingesting vault — this may take a minute…</p>
                      </div>
                    ) : zipPreview && obsidianPhase === "preview" ? (
                      <div className="space-y-3">
                        <div className="rounded-xl bg-surface-container-low px-5 py-4 space-y-1">
                          <p className="text-[15px] font-medium text-on-surface">{zipPreview.vault_name}</p>
                          <p className="text-sm text-secondary">
                            {zipPreview.total_files} notes · {zipPreview.total_words.toLocaleString()} words
                          </p>
                          <p className="text-xs text-outline">
                            ~{zipPreview.estimated_chunks} chunks to store
                          </p>
                          {zipPreview.skipped_files > 0 && (
                            <p className="text-xs text-outline">{zipPreview.skipped_files} short notes will be skipped</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <label className="label-caps text-secondary">Vault zip file</label>
                        <div
                          onDragOver={handleZipDragOver}
                          onDragLeave={handleZipDragLeave}
                          onDrop={handleZipDrop}
                          onClick={() => docFileInputRef.current?.click()}
                          className={`rounded-lg border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
                            zipIsDragging
                              ? "border-primary bg-surface-container"
                              : "border-ghost-border bg-surface-container-low hover:border-primary/30"
                          }`}
                        >
                          <p className="text-[15px] text-secondary">
                            Drop your vault.zip here or click to browse
                          </p>
                          <p className="text-xs text-outline mt-1">Max 50 MB</p>
                        </div>
                        <input
                          ref={docFileInputRef}
                          type="file"
                          accept=".zip"
                          onChange={(e) => {
                            const file = e.currentTarget.files?.[0];
                            if (file) handleZipPreview(file);
                          }}
                          className="hidden"
                        />
                      </div>
                    )}
                  </div>
                )}
              </div>

            ) : activeTab === "url" ? (
              /* ── URL ── */
              <div className="space-y-2">
                <label className="label-caps text-secondary">{inputLabel}</label>
                <input
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
                  placeholder="https://example.com/article"
                  className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-outline rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary transition-colors"
                />
              </div>

            ) : activeTab === "image" ? (
              /* ── Image ── */
              <div className="space-y-4">
                <label className="label-caps text-secondary">{inputLabel}</label>
                <div
                  onClick={() => fileInputRef.current?.click()}
                  className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
                    imagePreview
                      ? "border-outline-variant"
                      : isDragging
                      ? "border-primary bg-primary-container/20"
                      : "border-outline-variant hover:border-primary"
                  }`}
                >
                  {imagePreview ? (
                    <img src={imagePreview} alt="Preview" className="max-h-56 mx-auto rounded-lg object-contain" />
                  ) : (
                    <div className="space-y-1">
                      <p className="text-[15px] text-secondary">Click to upload</p>
                      <p className="text-xs text-outline">PNG, JPG, or WEBP</p>
                    </div>
                  )}
                </div>
                <input ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={handleImageChange} className="hidden" />
                {imageFile && <p className="text-xs text-outline">{imageFile.name}</p>}
              </div>

            ) : activeTab === "file" ? (
              /* ── File ── */
              <div className="space-y-4">
                <label className="label-caps text-secondary">{inputLabel}</label>
                {!uploadedFile ? (
                  <div
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => docFileInputRef.current?.click()}
                    className={`rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors ${
                      isDragging
                        ? "border-primary bg-primary-container/20"
                        : "border-outline-variant hover:border-primary"
                    }`}
                  >
                    <div className="space-y-1">
                      <p className="text-[15px] text-secondary">
                        {isDragging ? "Drop file here" : "Click or drag a file here"}
                      </p>
                      <p className="text-xs text-outline">PDF, DOCX, or TXT · max 10 MB</p>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-xl bg-surface-container-low px-5 py-4 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="label-caps px-2.5 py-1 rounded-full bg-surface-container text-on-surface-variant shrink-0 text-[10px]">
                        {FILE_TYPE_LABELS[uploadedFile.type] ?? uploadedFile.name.split(".").pop()?.toUpperCase() ?? "FILE"}
                      </span>
                      <span className="text-sm text-on-surface truncate">{uploadedFile.name}</span>
                      <span className="text-xs text-outline shrink-0">{formatBytes(uploadedFile.size)}</span>
                    </div>
                    <button
                      onClick={() => { setUploadedFile(null); if (docFileInputRef.current) docFileInputRef.current.value = ""; }}
                      className="text-xs text-outline hover:text-error shrink-0 transition-colors"
                    >
                      Remove
                    </button>
                  </div>
                )}
                <input ref={docFileInputRef} type="file" accept=".pdf,.docx,.txt" onChange={handleDocFileChange} className="hidden" />
              </div>

            ) : activeTab === "youtube" ? (
              /* ── YouTube — two-path layout ── */
              <div className="space-y-5">

                {/* PATH A — URL, fetched on submit */}
                <div className="space-y-2">
                  <label className="label-caps text-secondary">YOUTUBE URL</label>
                  <input
                    type="url"
                    value={ytUrl}
                    onChange={(e) => {
                      setYtUrl(e.target.value);
                      setYtFetchError("");
                    }}
                    placeholder="Paste a YouTube URL..."
                    className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-outline rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary transition-colors"
                  />
                  {ytFetchError && (
                    <p className="text-sm text-error">{ytFetchError}</p>
                  )}
                </div>

                {/* OR separator — text only, no line (No-Line Rule) */}
                <div className="text-center">
                  <span className="label-caps text-outline">or</span>
                </div>

                {/* PATH B — Manual paste */}
                <div className="space-y-2">
                  <label className="label-caps text-secondary">PASTE TRANSCRIPT</label>
                  <textarea
                    value={ytManualText}
                    onChange={(e) => {
                      const val = e.target.value;
                      setYtManualText(val);
                      setYtTranscript(val);
                      // Manual input wins — clear URL-path result indicators
                      if (val && ytVideoId) { setYtVideoId(""); }
                    }}
                    placeholder="Already have the transcript? Paste it here..."
                    rows={6}
                    className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-outline rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary resize-none transition-colors leading-relaxed"
                  />
                </div>

              </div>

            ) : (
              /* ── Article / Note ── */
              <div className="space-y-2 w-full max-md:!w-full max-md:!max-w-none max-md:mx-0">
                <label className="label-caps text-secondary">{inputLabel}</label>
                <textarea
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  placeholder={
                    activeTab === "note"
                      ? "Write your thoughts, ideas, or observations..."
                      : "Paste your article or thoughts here. We'll automatically structure it for your editorial needs..."
                  }
                  rows={10}
                  className="w-full max-md:w-full max-md:!w-full box-border bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-outline rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary resize-none transition-colors leading-relaxed"
                />
              </div>
            )}

            {/* Error */}
            {error && (
              <div>
                <p className="text-sm text-error">{error}</p>
                {activeTab === "url" && (
                  <p className="text-xs text-outline mt-1">You can paste the text manually in the Article tab instead.</p>
                )}
              </div>
            )}
          </div>

          {/* Card footer / action bar */}
          <div className="px-8 py-5 bg-surface-container-low flex items-center justify-between gap-4">
            <div className="flex items-center gap-4 text-outline">
              <button className="hover:text-secondary transition-colors" title="Format options">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M3 4h10M3 8h7M3 12h5" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </button>
              <button className="hover:text-secondary transition-colors" title="Translate">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M2 4h7M5.5 2v2M4 4c.5 2.5 2.5 5 4 5.5M7 4c-.5 2 .5 4 2 5.5M9 8l5 6M11.5 8l-2.5 6" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </button>
              <button className="hover:text-secondary transition-colors" title="AI assist">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M8 2l1.5 3.5L13 7l-3.5 1.5L8 12l-1.5-3.5L3 7l3.5-1.5z" stroke="currentColor" strokeWidth="1.5" strokeLinejoin="round"/>
                </svg>
              </button>
            </div>

            {activeTab === "obsidian" ? (
              effectiveObsidianMode === "local" ? (
                // Local path flow buttons
                obsidianPhase === "done" ? (
                  <button
                    onClick={() => { setObsidianPhase("input"); setVaultPreview(null); setObsidianResult(null); setVaultPath(""); setError(""); }}
                    className="px-6 py-2.5 rounded-lg bg-surface-container text-secondary text-[13px] font-medium hover:bg-surface-container-high transition-colors"
                  >
                    Add another vault
                  </button>
                ) : obsidianPhase === "ingesting" ? null : obsidianPhase === "preview" ? (
                  <div className="flex gap-3">
                    <button
                      onClick={() => { setObsidianPhase("input"); setVaultPreview(null); setError(""); }}
                      disabled={loading}
                      className="px-4 py-2.5 rounded-lg bg-surface-container text-secondary text-[13px] font-medium hover:bg-surface-container-high disabled:opacity-50 transition-colors"
                    >
                      Cancel
                    </button>
                    <button
                      onClick={handleVaultIngest}
                      disabled={loading}
                      className="btn-primary px-6 py-2.5 rounded-lg text-white text-[13px] font-semibold uppercase tracking-widest shadow-card hover:opacity-90 disabled:opacity-50 transition-all"
                    >
                      Ingest all notes
                    </button>
                  </div>
                ) : (
                  <button
                    onClick={handleVaultPreview}
                    disabled={loading}
                    className="btn-primary px-6 py-2.5 rounded-lg text-white text-[13px] font-semibold uppercase tracking-widest shadow-card hover:opacity-90 disabled:opacity-50 transition-all"
                  >
                    {loading ? "Scanning vault…" : "Preview vault"}
                  </button>
                )
              ) : (
                // Zip upload flow buttons
                obsidianPhase === "done" ? (
                  <button
                    onClick={() => resetObsidianZip()}
                    className="px-6 py-2.5 rounded-lg bg-surface-container text-secondary text-[13px] font-medium hover:bg-surface-container-high transition-colors"
                  >
                    Upload another vault
                  </button>
                ) : obsidianPhase === "ingesting" ? null : zipPreview && obsidianPhase === "preview" ? (
                  <div className="flex gap-3">
                    <button
                      onClick={() => resetObsidianZip()}
                      disabled={loading}
                      className="px-4 py-2.5 rounded-lg bg-surface-container text-secondary text-[13px] font-medium hover:bg-surface-container-high disabled:opacity-50 transition-colors"
                    >
                      Choose different file
                    </button>
                    <button
                      onClick={handleZipIngest}
                      disabled={loading}
                      className="btn-primary px-6 py-2.5 rounded-lg text-white text-[13px] font-semibold uppercase tracking-widest shadow-card hover:opacity-90 disabled:opacity-50 transition-all"
                    >
                      Ingest vault
                    </button>
                  </div>
                ) : null
              )
            ) : (
              <button
                onClick={handleSubmit}
                disabled={loading || (activeTab === "youtube" && !ytUrl.trim() && !ytManualText)}
                className="btn-primary px-7 py-2.5 rounded-lg text-white text-[13px] font-semibold uppercase tracking-widest shadow-card hover:opacity-90 disabled:opacity-50 active:scale-95 transition-all"
              >
                {loading
                  ? activeTab === "url"
                    ? (() => { try { return `Scraping ${new URL(urlInput).hostname}…`; } catch { return "Scraping…"; } })()
                    : activeTab === "file" && uploadedFile
                    ? `Processing ${uploadedFile.name}…`
                    : activeTab === "youtube" && ytFetching
                    ? "Fetching transcript…"
                    : "Processing…"
                  : "Feed into Memory"}
              </button>
            )}
          </div>
        </div>

        {/* Tab description */}
        <p className="text-xs text-outline -mt-3 px-1">{currentTab.description}</p>

        {/* ── Success / duplicate result card ── */}
        {result && (
          result.duplicate ? (
            <div className="rounded-2xl bg-surface-container px-6 py-5 flex items-start gap-4">
              <div className="w-9 h-9 rounded-full bg-surface-container-high flex items-center justify-center shrink-0 mt-0.5">
                <svg width="15" height="15" viewBox="0 0 16 16" fill="none">
                  <path d="M8 2a6 6 0 1 0 0 12A6 6 0 0 0 8 2zm0 4v4m0-4h.01" stroke="#777c7b" strokeWidth="1.5" strokeLinecap="round"/>
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[15px] font-medium text-on-surface">Already in your knowledge base</p>
                <p className="text-sm text-secondary mt-0.5">{result.chunks_stored} chunk{result.chunks_stored !== 1 ? "s" : ""} already stored</p>
                {result.tags.length > 0 && (
                  <div className="mt-3 flex flex-wrap gap-1.5">
                    {result.tags.map((tag) => (
                      <span key={tag} className="text-[11px] px-2.5 py-1 rounded-full bg-surface-container-high text-on-surface-variant font-medium">#{tag}</span>
                    ))}
                  </div>
                )}
              </div>
            </div>
          ) : (
            <div className="rounded-2xl bg-surface-container-lowest shadow-card px-6 py-5 flex items-start gap-4">
              <div className="w-10 h-10 rounded-full bg-primary flex items-center justify-center shrink-0 mt-0.5">
                <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                  <path d="M3 8.5l3.5 3.5 6.5-7" stroke="white" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"/>
                </svg>
              </div>
              <div className="flex-1 min-w-0">
                <p className="text-[15px] font-semibold text-on-surface">Knowledge Ingested</p>
                {result.title ? (
                  <p className="text-sm text-secondary mt-0.5">"{result.title}" has been successfully distilled and added to your Library.</p>
                ) : (
                  <p className="text-sm text-secondary mt-0.5">Your content has been successfully distilled and added to your Library.</p>
                )}
                <div className="mt-4 flex items-start gap-8">
                  <div>
                    <p className="label-caps text-outline mb-1">Extracted Concepts</p>
                    {result.tags.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {result.tags.map((tag) => (
                          <span key={tag} className="text-[11px] px-2.5 py-1 rounded-full bg-primary-container text-on-primary-container font-medium">#{tag}</span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-outline">No tags extracted</p>
                    )}
                  </div>
                  <div className="shrink-0 text-center">
                    <p className="label-caps text-outline mb-1">Stored Chunks</p>
                    <p className="text-3xl font-headline text-on-surface">{result.chunks_stored}</p>
                  </div>
                  {result.word_count != null && (
                    <div className="shrink-0 text-center">
                      <p className="label-caps text-outline mb-1">Words</p>
                      <p className="text-3xl font-headline text-on-surface">{result.word_count.toLocaleString()}</p>
                    </div>
                  )}
                </div>
              </div>
            </div>
          )
        )}
      </div>

      {/* ── Right: info panel ─────────────────────────────────── */}
      <div className="w-full md:w-72 shrink-0 space-y-4 pt-0 md:pt-[88px]">

        {/* Recent Memory stats card */}
        <div className="bg-surface-container-lowest rounded-2xl shadow-card p-6">
          <h3 className="font-headline text-xl text-on-surface mb-4">Recent Memory</h3>
          {stats ? (
            <div className="space-y-3">
              {stats.tags.slice(0, 3).map((tag, i) => (
                <div key={tag} className="flex items-center gap-3 py-2.5 border-b border-surface-container last:border-0">
                  <div className={`w-8 h-8 rounded-lg flex items-center justify-center shrink-0 ${
                    i === 0 ? "bg-primary-container" : i === 1 ? "bg-tertiary-fixed/40" : "bg-secondary-container"
                  }`}>
                    <svg width="13" height="13" viewBox="0 0 16 16" fill="none">
                      <rect x="2" y="2" width="12" height="12" rx="1.5" stroke={i === 0 ? "#58614f" : i === 1 ? "#81543c" : "#645e57"} strokeWidth="1.5"/>
                      <path d="M5 6h6M5 9h4" stroke={i === 0 ? "#58614f" : i === 1 ? "#81543c" : "#645e57"} strokeWidth="1.5" strokeLinecap="round"/>
                    </svg>
                  </div>
                  <div className="min-w-0">
                    <p className="text-[13px] font-medium text-on-surface capitalize truncate">{tag}</p>
                    <p className="text-[11px] text-outline">In your library</p>
                  </div>
                </div>
              ))}
              {stats.tags.length === 0 && (
                <p className="text-sm text-outline text-center py-4">No memory yet — add your first source above.</p>
              )}
              <div className="pt-2 flex items-center justify-between">
                <span className="text-[12px] text-outline">{stats.total_chunks} total chunks</span>
                <a href="/library" className="text-[12px] text-primary font-medium hover:underline uppercase tracking-wide">
                  View Full Library
                </a>
              </div>
            </div>
          ) : (
            <div className="space-y-3">
              {[...Array(3)].map((_, i) => (
                <div key={i} className="flex items-center gap-3 py-2.5">
                  <div className="w-8 h-8 rounded-lg bg-surface-container animate-pulse" />
                  <div className="flex-1 space-y-1.5">
                    <div className="h-3 bg-surface-container rounded animate-pulse w-3/4" />
                    <div className="h-2.5 bg-surface-container rounded animate-pulse w-1/2" />
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>

        {/* Writer's Block CTA */}
        <div className="bg-tertiary rounded-2xl p-6 text-on-tertiary relative overflow-hidden">
          <div className="relative z-10 space-y-3">
            <p className="font-headline text-xl text-white">Writer&apos;s Block?</p>
            <p className="text-sm text-white/80 leading-relaxed">
              Use your stored memories to generate a unique editorial angle for your next project.
            </p>
            <a
              href="/ideas"
              className="inline-block mt-1 px-4 py-2 rounded-lg border border-white/30 text-white text-[12px] font-semibold uppercase tracking-widest hover:bg-white/10 transition-colors"
            >
              Generate Idea
            </a>
          </div>
          <div className="absolute -right-6 -bottom-6 opacity-10">
            <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
              <path d="M40 10l7.5 17.5L65 30l-12.5 12 3 17.5L40 52 24.5 59.5l3-17.5L15 30l17.5-2.5z" fill="white"/>
            </svg>
          </div>
        </div>

        {/* Decorative pen card */}
        <div className="rounded-2xl overflow-hidden bg-surface-container h-40 flex items-center justify-center">
          <svg width="48" height="48" viewBox="0 0 48 48" fill="none" opacity="0.3">
            <path d="M8 40L14 26 36 4 44 12 22 34z" stroke="#58614f" strokeWidth="2.5" strokeLinejoin="round"/>
            <path d="M8 40l6-4 4 6-10-2z" fill="#58614f"/>
            <path d="M36 4l4 4-6 6-4-4 6-6z" fill="#81543c"/>
          </svg>
        </div>
      </div>

      {/* ── Tooltip tour ─────────────────────────────────────────────────── */}
      {tourActive && tourStep >= 0 && tooltipPos && (
        <div
          style={{
            position: "fixed",
            top: tooltipPos.top,
            left: tooltipPos.left,
            transform: "translateX(-50%)",
            zIndex: 9999,
          }}
        >
          {/* Upward caret */}
          <div
            style={{
              position: "absolute",
              top: -8,
              left: "50%",
              transform: "translateX(-50%)",
              width: 0,
              height: 0,
              borderLeft: "8px solid transparent",
              borderRight: "8px solid transparent",
              borderBottom: "8px solid #3a4a35",
            }}
          />
          {/* Dark sage card */}
          <div
            style={{
              background: "#3a4a35",
              borderRadius: 12,
              padding: "16px 20px",
              width: 280,
              boxShadow: "0px 8px 24px rgba(0,0,0,0.28)",
              color: "#ffffff",
            }}
          >
            {/* Top row: tab name + step indicator */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <p style={{ fontSize: 14, fontWeight: 600, color: "#ffffff" }}>
                {TOUR_STEPS[tourStep].label}
              </p>
              <p style={{ fontSize: 11, color: "rgba(255,255,255,0.55)" }}>
                {tourStep + 1} of {TOUR_STEPS.length}
              </p>
            </div>
            {/* Divider */}
            <div style={{ height: 1, background: "rgba(255,255,255,0.15)", margin: "12px 0" }} />
            {/* Description */}
            <p style={{ fontSize: 13, color: "rgba(255,255,255,0.85)", lineHeight: 1.6, marginTop: 10 }}>
              {TOUR_STEPS[tourStep].description}
            </p>
            {/* Bottom row: Skip + Next/Done */}
            <div style={{ display: "flex", justifyContent: "flex-end", gap: 16, marginTop: 16 }}>
              <button
                onClick={dismissTour}
                style={{ fontSize: 12, color: "rgba(255,255,255,0.5)", background: "none", border: "none", cursor: "pointer", padding: 0 }}
              >
                Skip tour
              </button>
              <button
                onClick={advanceTour}
                style={{ fontSize: 12, color: "#3a4a35", background: "#ffffff", padding: "6px 16px", borderRadius: 99, border: "none", cursor: "pointer", fontWeight: 500 }}
              >
                {tourStep < TOUR_STEPS.length - 1 ? "Next →" : "Done"}
              </button>
            </div>
          </div>
        </div>
      )}

      <ExtensionInstallModal
        isOpen={isExtensionModalOpen}
        onClose={() => setIsExtensionModalOpen(false)}
      />
    </div>
  );
}
