"use client";

import { useState, useEffect, useRef } from "react";
import { Puzzle } from "lucide-react";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi, type MemoryContext } from "@/lib/api";
import { ingestOutcome, keepsInput, type IngestResult } from "@/lib/ingest-result";
import { useTracking } from "@/lib/useTracking";
import ExtensionInstallModal from "@/components/ExtensionInstallModal";
import Link from "next/link";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";
import { chipClass } from "@/components/ui/chip";

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
    description: "Upload a PDF, DOCX, TXT, or MD file. Its text is added to your library.",
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
    description: "Upload a screenshot, diagram, or whiteboard photo. Contendo reads the text and ideas in it.",
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
      "Connect your Obsidian vault. All your notes are added to your library.",
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
  const { logEvent } = useTracking();
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
  const [result, setResult] = useState<IngestResult | null>(null);
  const [error, setError] = useState("");
  // YouTube two-path state
  const [ytUrl, setYtUrl] = useState("");
  const [ytTranscript, setYtTranscript] = useState("");
  const [ytVideoId, setYtVideoId] = useState("");
  const [ytFetching, setYtFetching] = useState(false);
  const [ytFetchError, setYtFetchError] = useState("");
  const [ytManualText, setYtManualText] = useState("");
  const [stats, setStats] = useState<Stats | null>(null);
  const [memoryContext, setMemoryContext] = useState<MemoryContext | null>(null);
  const [contextSuggesting, setContextSuggesting] = useState(false);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const docFileInputRef = useRef<HTMLInputElement>(null);
  const { showToast } = useToast();

  // ── Tooltip tour ─────────────────────────────────────────────────────────────
  const [tourStep, setTourStep] = useState(-1);
  const [tourActive, setTourActive] = useState(false);
  const [tooltipPos, setTooltipPos] = useState<{ top: number; left: number } | null>(null);
  const tabBarRef = useRef<HTMLDivElement>(null);
  const tabButtonRefs = useRef<(HTMLButtonElement | null)[]>([]);
  const mobileTabBarRef = useRef<HTMLDivElement>(null);
  const mobileTabButtonRefs = useRef<(HTMLButtonElement | null)[]>([]);

  // Start tour 800ms after mount — only when localStorage key is absent
  useEffect(() => {
    if (typeof window !== "undefined" && localStorage.getItem("contendo_feed_tour_done")) return;
    const timer = setTimeout(() => {
      setTourActive(true);
      setTourStep(0);
      logEvent({ event_type: "feature_start", page_url: "/feed-memory", button_name: "feed_memory_tour", metadata: { status: "shown" } });
    }, 800);
    return () => clearTimeout(timer);
  // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // When tour step changes: switch active tab and measure fixed position for the tooltip
  useEffect(() => {
    if (!tourActive || tourStep < 0) return;
    setActiveTab(TOUR_STEPS[tourStep].id);
    requestAnimationFrame(() => {
      const tabIdx = TABS.findIndex((t) => t.id === TOUR_STEPS[tourStep].id);
      const desktopBtn = tabButtonRefs.current[tabIdx];
      const mobileBtn = mobileTabButtonRefs.current[tabIdx];
      // Pick the visible button — offsetParent is null for display:none elements
      const useDesktop = !!(desktopBtn && desktopBtn.offsetParent !== null);
      const btn = useDesktop ? desktopBtn : mobileBtn;
      const bar = useDesktop ? tabBarRef.current : mobileTabBarRef.current;
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

  const _endTour = () => {
    setTourActive(false);
    setTourStep(-1);
    if (typeof window !== "undefined") localStorage.setItem("contendo_feed_tour_done", "1");
  };

  const dismissTour = () => {
    logEvent({ event_type: "feature_abandon", page_url: "/feed-memory", button_name: "feed_memory_tour", metadata: { status: "skipped" } });
    _endTour();
  };

  const advanceTour = () => {
    if (tourStep < TOUR_STEPS.length - 1) {
      setTourStep(tourStep + 1);
    } else {
      logEvent({ event_type: "feature_complete", page_url: "/feed-memory", button_name: "feed_memory_tour", metadata: { status: "completed" } });
      _endTour();
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

  const handleContextBlur = async (text: string) => {
    if (!text || text.trim().length < 30 || memoryContext !== null) return;
    setContextSuggesting(true);
    try {
      const res = await api.suggestMemoryContext(text);
      if (res.ok) {
        const data = await res.json();
        if (data.suggested_context && memoryContext === null) {
          setMemoryContext(data.suggested_context as MemoryContext);
        }
      }
    } catch {}
    finally { setContextSuggesting(false); }
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
    logEvent({ event_type: "button_click", page_url: "/feed-memory", button_name: "source_tab", metadata: { source_type: tab } });
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
    setMemoryContext(null);
    setContextSuggesting(false);
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
      "text/markdown",
    ];
    const extAllowed = file.name.match(/\.(pdf|docx|txt|md)$/i);
    if (!allowed.includes(file.type) && !extAllowed) {
      setError("Unsupported file type. Please upload a PDF, DOCX, TXT, or MD file.");
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

  /** replaceSourceId: resend the same input to replace that duplicate (lib/ingest-result.ts). */
  const handleSubmit = async (replaceSourceId?: string) => {
    setError("");
    setResult(null);

    if (activeTab === "image") {
      if (!imageFile) { setError("Please select an image file."); return; }
    } else if (activeTab === "file") {
      if (!uploadedFile) { setError("Please upload a file."); return; }
    } else if (activeTab === "url") {
      if (!urlInput.trim()) { setError("Please enter a URL."); return; }
      if (!urlInput.trim().startsWith("http://") && !urlInput.trim().startsWith("https://")) {
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
        if (replaceSourceId) formData.append("replace_source_id", replaceSourceId);
        res = await api.ingestFile(formData);
      } else if (activeTab === "url") {
        res = await api.scrapeAndIngest(urlInput.trim(), replaceSourceId);
      } else {
        const body: { source_type: string; raw_image?: string; content?: string; source_title?: string; memory_context?: MemoryContext | null; video_url?: string; replace_source_id?: string } = {
          source_type: activeTab,
          memory_context: memoryContext,
        };
        if (replaceSourceId) body.replace_source_id = replaceSourceId;
        if (activeTab === "image") { body.raw_image = imagePreview; body.content = ""; }
        else if (activeTab === "youtube") {
          // A link is saved from the transcript the server fetched for the
          // preview (or fetches again); a pasted transcript is saved as typed.
          if (ytUrl.trim()) body.video_url = ytUrl.trim();
          else body.content = ytManualText || ytTranscript;
        }
        else { body.content = content; }
        res = await api.ingestContent(body);
      }

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Ingest failed");
      }

      const data: IngestResult = await res.json();
      const outcome = ingestOutcome(data);
      if (outcome.kind === "empty") {
        throw new Error("No chunks were stored. Check that the source contains readable text and try again.");
      }
      setResult(data);
      logEvent({
        event_type: data.duplicate ? "feature_abandon" : "feature_complete",
        page_url: "/feed-memory",
        button_name: "ingest_submit",
        metadata: { source_type: activeTab, chunks_stored: data.chunks_stored ?? 0, duplicate: !!data.duplicate },
      });
      if (keepsInput(outcome)) return;   // the card offers Replace with the same input
      showToast(
        data.duplicate
          ? "This source is already in your library."
          : replaceSourceId
          ? `Replaced. ${data.chunks_stored} passages stored.`
          : `Ingested successfully! Added ${data.chunks_stored} chunks.`,
        "success",
      );
      setContent("");
      setUrlInput("");
      setImageFile(null);
      setImagePreview("");
      setUploadedFile(null);
      setMemoryContext(null);
      if (fileInputRef.current) fileInputRef.current.value = "";
      if (docFileInputRef.current) docFileInputRef.current.value = "";
      setYtUrl("");
      setYtTranscript("");
      setYtVideoId("");
      setYtFetchError("");
      setYtManualText("");
      await fetchStats();
    } catch (e: unknown) {
      const msg = e instanceof Error ? e.message : "Something went wrong.";
      setError(msg);
      logEvent({ event_type: "feature_abandon", page_url: "/feed-memory", button_name: "ingest_submit", metadata: { source_type: activeTab, error: msg } });
    } finally {
      setLoading(false);
    }
  };

    const currentTab = TABS.find((t) => t.id === activeTab)!;

  // What the active tab still needs before it can be added, said on the button.
  const missingInput =
    (activeTab === "article" || activeTab === "note") && !content.trim() ? "Paste some text to continue" :
    activeTab === "url" && !urlInput.trim() ? "Add a link to continue" :
    activeTab === "file" && !uploadedFile ? "Choose a file to continue" :
    activeTab === "image" && !imageFile ? "Choose an image to continue" :
    activeTab === "youtube" && !ytUrl.trim() && !ytManualText ? "Add a YouTube link or transcript" :
    undefined;
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
          <h1 className="font-headline text-4xl text-on-surface leading-tight">Feed memory</h1>
          <p className="mt-2 text-secondary text-[15px] leading-relaxed">
            Add something for Contendo to write from: an article, a link, a file, a video, an image or a note.
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
          className="hidden md:flex w-full min-h-11 rounded-xl bg-surface-container-low px-4 items-center gap-2 cursor-pointer hover:bg-surface-container transition-colors text-secondary focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary"
        >
          <Puzzle size={16} className="shrink-0" />
          <span className="text-[0.875rem] font-normal truncate">Install the Chrome extension</span>
        </div>

        {/* Tab selector */}
        <div className="hidden md:flex flex-wrap gap-2" ref={tabBarRef}>
          {TABS.map((tab, idx) => (
            <button
              key={tab.id}
              ref={(el) => { tabButtonRefs.current[idx] = el; }}
              onClick={() => handleTabChange(tab.id)}
              aria-pressed={activeTab === tab.id}
              className={chipClass(activeTab === tab.id)}
            >
              <span className={activeTab === tab.id ? "text-white/80" : "text-on-surface-variant"}>
                {SOURCE_ICONS[tab.id]}
              </span>
              {tab.label}
            </button>
          ))}
        </div>

        <div className="md:hidden flex gap-2 overflow-x-auto no-scrollbar pb-1" ref={mobileTabBarRef}>
          {TABS.map((tab, idx) => (
            <button
              key={tab.id}
              ref={(el) => { mobileTabButtonRefs.current[idx] = el; }}
              onClick={() => handleTabChange(tab.id)}
              aria-pressed={activeTab === tab.id}
              className={chipClass(activeTab === tab.id)}
            >
              <span className={activeTab === tab.id ? "text-white/80" : "text-on-surface-variant"}>
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
                      type="button"
                      aria-pressed={obsidianMode === "local"}
                      onClick={() => setObsidianMode("local")}
                      className={chipClass(obsidianMode === "local")}
                    >
                      Local path
                    </button>
                    <button
                      type="button"
                      aria-pressed={obsidianMode === "zip"}
                      onClick={() => setObsidianMode("zip")}
                      className={chipClass(obsidianMode === "zip")}
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
                              <span className="text-xs text-on-surface-variant self-center">+{obsidianResult.all_tags.length - 10} more</span>
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
                          <label htmlFor="feed-field-0" className="label-caps text-secondary">Vault folder path</label>
                          <input id="feed-field-0"
                            type="text"
                            value={vaultPath}
                            onChange={(e) => { setVaultPath(e.target.value); setVaultPreview(null); setObsidianPhase("input"); }}
                            onKeyDown={(e) => { if (e.key === "Enter" && obsidianPhase === "input") handleVaultPreview(); }}
                            placeholder="/Users/yourname/Documents/ObsidianVault"
                            className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-placeholder rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary transition-colors"
                          />
                          <p className="text-xs text-on-surface-variant">
                            Open Obsidian → Settings → About to find your vault path.
                          </p>
                        </div>
                        {vaultPreview && obsidianPhase === "preview" && (
                          <div className="rounded-xl bg-surface-container-low px-5 py-4 space-y-1">
                            <p className="text-[15px] font-medium text-on-surface">{vaultPreview.vault_name}</p>
                            <p className="text-sm text-secondary">
                              {vaultPreview.total_files} notes · {vaultPreview.total_words.toLocaleString()} words
                            </p>
                            <p className="text-xs text-on-surface-variant">
                              ~{vaultPreview.estimated_chunks} chunks to store
                            </p>
                            {vaultPreview.skipped_files > 0 && (
                              <p className="text-xs text-on-surface-variant">{vaultPreview.skipped_files} short notes will be skipped</p>
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
                              <span className="text-xs text-on-surface-variant self-center">+{obsidianResult.all_tags.length - 10} more</span>
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
                          <p className="text-xs text-on-surface-variant">
                            ~{zipPreview.estimated_chunks} chunks to store
                          </p>
                          {zipPreview.skipped_files > 0 && (
                            <p className="text-xs text-on-surface-variant">{zipPreview.skipped_files} short notes will be skipped</p>
                          )}
                        </div>
                      </div>
                    ) : (
                      <div className="space-y-2">
                        <label htmlFor="feed-field-1" className="label-caps text-secondary">Vault zip file</label>
                        <button
                  type="button"
                          onDragOver={handleZipDragOver}
                          onDragLeave={handleZipDragLeave}
                          onDrop={handleZipDrop}
                          onClick={() => docFileInputRef.current?.click()}
                          className={`block w-full rounded-lg border-2 border-dashed p-10 text-center cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                            zipIsDragging
                              ? "border-primary bg-surface-container"
                              : "border-ghost-border bg-surface-container-low hover:border-primary/30"
                          }`}
                        >
                          <span className="block text-[15px] text-secondary">
                            Drop your vault.zip here or click to browse
                          </span>
                          <span className="block text-xs text-on-surface-variant mt-1">Max 50 MB</span>
                        </button>
                        <input id="feed-field-1"
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
                <label htmlFor="feed-field-2" className="label-caps text-secondary">{inputLabel}</label>
                <input id="feed-field-2"
                  type="url"
                  value={urlInput}
                  onChange={(e) => setUrlInput(e.target.value)}
                  onKeyDown={(e) => { if (e.key === "Enter") handleSubmit(); }}
                  placeholder="https://example.com/article"
                  className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-placeholder rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary transition-colors"
                />
              </div>

            ) : activeTab === "image" ? (
              /* ── Image ── */
              <div className="space-y-4">
                <label htmlFor="feed-field-3" className="label-caps text-secondary">{inputLabel}</label>
                <button
                  type="button"
                  onClick={() => fileInputRef.current?.click()}
                  className={`block w-full rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
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
                    <span className="block space-y-1">
                      <span className="block text-[15px] text-secondary">Click to upload</span>
                      <span className="block text-xs text-on-surface-variant">PNG, JPG, or WEBP</span>
                    </span>
                  )}
                </button>
                <input id="feed-field-3" ref={fileInputRef} type="file" accept="image/png,image/jpeg,image/webp" onChange={handleImageChange} className="hidden" />
                {imageFile && <p className="text-xs text-on-surface-variant">{imageFile.name}</p>}
              </div>

            ) : activeTab === "file" ? (
              /* ── File ── */
              <div className="space-y-4">
                <label className="label-caps text-secondary">{inputLabel}</label>
                {!uploadedFile ? (
                  <button
                  type="button"
                    onDragOver={handleDragOver}
                    onDragLeave={handleDragLeave}
                    onDrop={handleDrop}
                    onClick={() => docFileInputRef.current?.click()}
                    className={`block w-full rounded-xl border-2 border-dashed p-10 text-center cursor-pointer transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary ${
                      isDragging
                        ? "border-primary bg-primary-container/20"
                        : "border-outline-variant hover:border-primary"
                    }`}
                  >
                    <span className="block space-y-1">
                      <span className="block text-[15px] text-secondary">
                        {isDragging ? "Drop file here" : "Click or drag a file here"}
                      </span>
                      <span className="block text-xs text-on-surface-variant">PDF, DOCX, TXT, or MD · max 10 MB</span>
                    </span>
                  </button>
                ) : (
                  <div className="rounded-xl bg-surface-container-low px-5 py-4 flex items-center justify-between gap-4">
                    <div className="flex items-center gap-3 min-w-0">
                      <span className="label-caps px-2.5 py-1 rounded-full bg-surface-container text-on-surface-variant shrink-0 text-[10px]">
                        {FILE_TYPE_LABELS[uploadedFile.type] ?? uploadedFile.name.split(".").pop()?.toUpperCase() ?? "FILE"}
                      </span>
                      <span className="text-sm text-on-surface truncate">{uploadedFile.name}</span>
                      <span className="text-xs text-on-surface-variant shrink-0">{formatBytes(uploadedFile.size)}</span>
                    </div>
                    <Button
                      variant="tertiary"
                      size="sm"
                      className="shrink-0"
                      onClick={() => { setUploadedFile(null); if (docFileInputRef.current) docFileInputRef.current.value = ""; }}
                    >
                      Remove
                    </Button>
                  </div>
                )}
                <input ref={docFileInputRef} type="file" accept=".pdf,.docx,.txt,.md" onChange={handleDocFileChange} className="hidden" />
              </div>

            ) : activeTab === "youtube" ? (
              /* ── YouTube — two-path layout ── */
              <div className="space-y-5">

                {/* PATH A — URL, fetched on submit */}
                <div className="space-y-2">
                  <label htmlFor="feed-field-4" className="label-caps text-secondary">YOUTUBE URL</label>
                  <input id="feed-field-4"
                    type="url"
                    value={ytUrl}
                    onChange={(e) => {
                      setYtUrl(e.target.value);
                      setYtFetchError("");
                    }}
                    placeholder="Paste a YouTube URL..."
                    className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-placeholder rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary transition-colors"
                  />
                  {ytFetchError && (
                    <p className="text-sm text-error">{ytFetchError}</p>
                  )}
                </div>

                {/* OR separator — text only, no line (No-Line Rule) */}
                <div className="text-center">
                  <span className="label-caps text-on-surface-variant">or</span>
                </div>

                {/* PATH B — Manual paste */}
                <div className="space-y-2">
                  <label htmlFor="feed-field-5" className="label-caps text-secondary">PASTE TRANSCRIPT</label>
                  <textarea id="feed-field-5"
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
                    className="w-full bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-placeholder rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary resize-none transition-colors leading-relaxed"
                  />
                </div>

              </div>

            ) : (
              /* ── Article / Note ── */
              <div className="space-y-2 w-full max-md:!w-full max-md:!max-w-none max-md:mx-0">
                <label htmlFor="feed-field-6" className="label-caps text-secondary">{inputLabel}</label>
                <textarea id="feed-field-6"
                  value={content}
                  onChange={(e) => setContent(e.target.value)}
                  onBlur={(e) => handleContextBlur(e.target.value)}
                  placeholder={
                    activeTab === "note"
                      ? "Write your thoughts, ideas, or observations..."
                      : "Paste an article, a post or your own notes here..."
                  }
                  rows={10}
                  className="w-full max-md:w-full max-md:!w-full box-border bg-surface-container-low px-4 py-3 text-[15px] text-on-surface placeholder:text-placeholder rounded-lg border-0 border-b-2 border-outline-variant focus:outline-none focus:border-primary resize-none transition-colors leading-relaxed"
                />
              </div>
            )}

            {/* Context selector — article, note, youtube only */}
            {(activeTab === "article" || activeTab === "note" || activeTab === "youtube") && (
              <div className="space-y-2">
                <div className="flex items-center gap-2">
                  <p id="feed-context-label" className="label-caps text-secondary">Where this comes from</p>
                  {contextSuggesting && (
                    <span className="text-[10px] text-on-surface-variant animate-pulse">suggesting…</span>
                  )}
                </div>
                <div role="group" aria-labelledby="feed-context-label" className="flex flex-wrap gap-2">
                  {(
                    [
                      { value: "work" as MemoryContext, label: "Work" },
                      { value: "personal_project" as MemoryContext, label: "Personal project" },
                      { value: "learning" as MemoryContext, label: "Learning" },
                      { value: "observation" as MemoryContext, label: "Observation" },
                    ] as { value: MemoryContext; label: string }[]
                  ).map(({ value, label }) => (
                    <button
                      key={value}
                      type="button"
                      aria-pressed={memoryContext === value}
                      onClick={() => setMemoryContext(memoryContext === value ? null : value)}
                      className={chipClass(memoryContext === value)}
                    >
                      {label}
                    </button>
                  ))}
                </div>
                <p className="text-[11px] text-on-surface-variant">
                  Tag the origin so your posts know what you lived vs what you learned.
                </p>
              </div>
            )}

            {/* Error */}
            {error && (
              <ErrorState message={activeTab === "url" ? `${error} You can paste the text in the Article tab instead.` : error} />
            )}
          </div>

          {/* Card footer / action bar */}
          <div className="px-8 py-5 bg-surface-container-low flex items-center justify-between gap-4">
            <span />

            {activeTab === "obsidian" ? (
              effectiveObsidianMode === "local" ? (
                // Local path flow buttons
                obsidianPhase === "done" ? (
                  <Button
                    variant="secondary"
                    onClick={() => { setObsidianPhase("input"); setVaultPreview(null); setObsidianResult(null); setVaultPath(""); setError(""); }}
                  >
                    Add another vault
                  </Button>
                ) : obsidianPhase === "ingesting" ? null : obsidianPhase === "preview" ? (
                  <div className="flex gap-3">
                    <Button
                      variant="secondary"
                      onClick={() => { setObsidianPhase("input"); setVaultPreview(null); setError(""); }}
                      disabled={loading}
                    >
                      Cancel
                    </Button>
                    <Button
                      onClick={handleVaultIngest}
                      loading={loading}
                    >
                      Ingest all notes
                    </Button>
                  </div>
                ) : (
                  <Button
                    onClick={handleVaultPreview}
                    loading={loading}
                  >
                    {loading ? "Scanning vault…" : "Preview vault"}
                  </Button>
                )
              ) : (
                // Zip upload flow buttons
                obsidianPhase === "done" ? (
                  <Button
                    variant="secondary"
                    onClick={() => resetObsidianZip()}
                  >
                    Upload another vault
                  </Button>
                ) : obsidianPhase === "ingesting" ? null : zipPreview && obsidianPhase === "preview" ? (
                  <div className="flex gap-3">
                    <Button
                      variant="secondary"
                      onClick={() => resetObsidianZip()}
                      disabled={loading}
                    >
                      Choose different file
                    </Button>
                    <Button
                      onClick={handleZipIngest}
                      loading={loading}
                    >
                      Ingest vault
                    </Button>
                  </div>
                ) : null
              )
            ) : (
              <Button
                onClick={() => handleSubmit()}
                loading={loading}
                disabled={!!missingInput}
                disabledReason={missingInput}
              >
                {loading
                  ? activeTab === "url"
                    ? (() => { try { return `Reading ${new URL(urlInput).hostname}…`; } catch { return "Reading the page…"; } })()
                    : activeTab === "file" && uploadedFile
                    ? `Processing ${uploadedFile.name}…`
                    : activeTab === "youtube" && ytFetching
                    ? "Fetching transcript…"
                    : "Adding…"
                  : "Add to library"}
              </Button>
            )}
          </div>
        </div>

        {/* Tab description */}
        <p className="text-xs text-on-surface-variant -mt-3 px-1">{currentTab.description}</p>

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
                <p className="text-[15px] font-medium text-on-surface">Already in your library</p>
                {result.replaceable && result.existing_source_id ? (
                  <>
                    <p className="text-sm text-secondary mt-0.5">
                      You added this {activeTab === "url" || activeTab === "youtube" ? "link" : activeTab === "image" ? "image" : "file"} before
                      {result.existing_title ? <> as &ldquo;{result.existing_title}&rdquo;</> : null}. Replace it to read it again with the latest extraction.
                    </p>
                    <div className="mt-3">
                      <Button variant="secondary" size="sm" loading={loading} onClick={() => handleSubmit(result.existing_source_id ?? undefined)}>
                        Replace
                      </Button>
                    </div>
                  </>
                ) : (
                  <p className="text-sm text-secondary mt-0.5">You added this before, so there was nothing new to save.</p>
                )}
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
                <p className="text-[15px] font-semibold text-on-surface">Added to your library</p>
                {result.title ? (
                  <p className="text-sm text-secondary mt-0.5">&ldquo;{result.title}&rdquo; is in your library. Contendo can now write from it.</p>
                ) : (
                  <p className="text-sm text-secondary mt-0.5">It&apos;s in your library. Contendo can now write from it.</p>
                )}
                <div className="mt-4 flex items-start gap-8">
                  <div>
                    <p className="label-caps text-on-surface-variant mb-1">Topics</p>
                    {result.tags.length > 0 ? (
                      <div className="flex flex-wrap gap-1.5 mt-2">
                        {result.tags.map((tag) => (
                          <span key={tag} className="text-[11px] px-2.5 py-1 rounded-full bg-primary-container text-on-primary-container font-medium">#{tag}</span>
                        ))}
                      </div>
                    ) : (
                      <p className="text-sm text-on-surface-variant">No topics found</p>
                    )}
                  </div>
                  <div className="shrink-0 text-center">
                    <p className="label-caps text-on-surface-variant mb-1">Passages</p>
                    <p className="text-3xl font-headline text-on-surface">{result.chunks_stored}</p>
                  </div>
                  {result.word_count != null && (
                    <div className="shrink-0 text-center">
                      <p className="label-caps text-on-surface-variant mb-1">Words</p>
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
          <h2 className="font-headline text-xl text-on-surface mb-4">Your library</h2>
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
                    <p className="text-[11px] text-on-surface-variant">In your library</p>
                  </div>
                </div>
              ))}
              {stats.tags.length === 0 && (
                <p className="text-sm text-on-surface-variant text-center py-4">Nothing here yet. Add your first source.</p>
              )}
              <div className="pt-2 flex items-center justify-between">
                <span className="text-[0.8125rem] text-on-surface-variant">{stats.total_chunks} passages</span>
                <Link href="/library" className="inline-flex min-h-11 items-center text-[0.8125rem] text-primary font-medium underline-offset-4 hover:underline">
                  Open library
                </Link>
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
            <p className="font-headline text-xl text-white">Not sure what to write?</p>
            <p className="text-sm text-white/90 leading-relaxed">
              Get post ideas drawn from what you&apos;ve added.
            </p>
            <Link
              href="/ideas"
              className="inline-flex min-h-11 items-center mt-1 px-4 rounded-md border border-white/60 text-white text-[0.875rem] font-medium hover:bg-white/10 transition-colors focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white"
            >
              Get ideas
            </Link>
          </div>
          <div className="absolute -right-6 -bottom-6 opacity-10">
            <svg width="80" height="80" viewBox="0 0 80 80" fill="none">
              <path d="M40 10l7.5 17.5L65 30l-12.5 12 3 17.5L40 52 24.5 59.5l3-17.5L15 30l17.5-2.5z" fill="white"/>
            </svg>
          </div>
        </div>

        
      </div>

      {/* ── Tooltip tour ─────────────────────────────────────────────────── */}
      {tourActive && tourStep >= 0 && tooltipPos && (
        <div
          style={{
            position: "fixed",
            top: tooltipPos.top,
            // Centred under its tab, but kept 16px inside the screen edges.
            left: `clamp(156px, ${tooltipPos.left}px, calc(100vw - 156px))`,
            transform: "translateX(-50%)",
            zIndex: 9999,
          }}
          role="dialog"
          aria-label={`Tour: ${TOUR_STEPS[tourStep].label}`}
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
              width: "min(280px, calc(100vw - 32px))",
              boxShadow: "0px 8px 24px rgba(0,0,0,0.28)",
              color: "#ffffff",
            }}
          >
            {/* Top row: tab name + step indicator */}
            <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center" }}>
              <p style={{ fontSize: 14, fontWeight: 600, color: "#ffffff" }}>
                {TOUR_STEPS[tourStep].label}
              </p>
              <p style={{ fontSize: 12, color: "rgba(255,255,255,0.8)" }}>
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
            <div style={{ display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 8, marginTop: 12 }}>
              <button type="button" onClick={dismissTour} className="min-h-11 px-2 text-[0.8125rem] text-white/85 underline-offset-4 hover:underline focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white rounded-md">
                Skip tour
              </button>
              <button type="button" onClick={advanceTour} className="min-h-11 rounded-full bg-white px-4 text-[0.8125rem] font-medium text-[#3a4a35] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-white focus-visible:ring-offset-2 focus-visible:ring-offset-[#3a4a35]">
                {tourStep < TOUR_STEPS.length - 1 ? "Next" : "Done"}
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
