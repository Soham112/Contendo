"use client";

import supabase from "@/lib/supabase";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

// ── Request / Response Types ─────────────────────────────────────────────────

export interface IngestRequest {
  content?: string;
  source_type: string;
  raw_image?: string;
}

export interface IngestResponse {
  chunks_stored: number;
  tags: string[];
  duplicate?: boolean;
  message?: string;
}

export interface ScrapeAndIngestResponse {
  chunks_stored: number;
  tags: string[];
  title: string;
  word_count: number;
  duplicate?: boolean;
  message?: string;
}

export interface GenerateRequest {
  topic: string;
  format: string;
  tone: string;
  length?: "concise" | "standard" | "long-form";
  context?: string;
  quality?: string;
}

export interface GenerateResponse {
  post: string;
  score: number;
  score_feedback: string[];
  iterations: number;
  archetype?: string;
  scored?: boolean;
}

export interface RefineRequest {
  current_draft: string;
  refinement_instruction: string;
}

export interface RefineResponse {
  refined_draft: string;
  score: number;
  score_feedback: string[];
}

export interface ScoreResponse {
  score: number;
  score_feedback: string[];
}

export interface LogPostRequest {
  topic: string;
  format: string;
  tone: string;
  content: string;
  authenticity_score: number;
  svg_diagrams?: string | null;
  archetype?: string;
}

export interface PatchPostRequest {
  content?: string;
  authenticity_score?: number;
  svg_diagrams?: object[] | string | null;
}

export interface LibrarySource {
  source_title: string;
  source_type: string;
  ingested_at: string;
  chunk_count: number;
  tags: string[];
  retrieval_count: number;
}

export interface ClusterSourceItem {
  source_title: string;
  source_type: string;
  ingested_at: string;
}

export interface ClusterItem {
  tag: string;
  source_count: number;
  total_chunks: number;
  sources: ClusterSourceItem[];
}

export interface LibraryClustersResponse {
  clusters: ClusterItem[];
  unclustered_sources: ClusterSourceItem[];
  total_sources: number;
  total_tags: number;
}

export interface ProfileData {
  name?: string;
  role?: string;
  bio?: string;
  location?: string;
  topics_of_expertise?: string[];
  target_audience?: string;
  voice_descriptors?: string[];
  words_to_avoid?: string[];
  writing_rules?: string[];
  opinions?: string[];
  writing_samples?: string[];
  [key: string]: unknown;
}

// ── Core Hook ────────────────────────────────────────────────────────────────

/**
 * Returns typed API functions with the Supabase Bearer token pre-attached.
 * Falls back gracefully when no session is present (backend allows this in
 * non-production via the dev fallback to user_id="default").
 */
export function useApi() {
  async function apiFetch(
    path: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const {
      data: { session },
    } = await supabase.auth.getSession();
    const token = session?.access_token ?? null;
    const headers: Record<string, string> = {
      ...(options.headers as Record<string, string> ?? {}),
    };
    if (token) {
      headers["Authorization"] = `Bearer ${token}`;
    }
    return fetch(`${API}${path}`, { ...options, headers });
  }

  return {
    // ── Ingest ────────────────────────────────────────────────────────────
    ingestContent: (body: IngestRequest) =>
      apiFetch("/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),

    ingestFile: (formData: FormData) =>
      apiFetch("/ingest-file", { method: "POST", body: formData }),

    scrapeAndIngest: (url: string) =>
      apiFetch("/scrape-and-ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      }),

    obsidianPreview: (vault_path: string) =>
      apiFetch("/obsidian/preview", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vault_path }),
      }),

    obsidianIngest: (vault_path: string) =>
      apiFetch("/obsidian/ingest", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ vault_path }),
      }),

    obsidianPreviewZip: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch("/obsidian/preview-zip", { method: "POST", body: formData });
    },

    obsidianIngestZip: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch("/obsidian/ingest-zip", { method: "POST", body: formData });
    },

    fetchYoutubeTranscript: (url: string) =>
      apiFetch("/fetch-youtube-transcript", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ url }),
      }),

    // ── Generate ──────────────────────────────────────────────────────────
    generatePost: (body: GenerateRequest) =>
      apiFetch("/generate", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),

    refinePost: (body: RefineRequest) =>
      apiFetch("/refine", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),

    refineSelection: async (
      selectedText: string,
      instruction: string,
      fullPost: string
    ): Promise<{ rewritten_text: string }> => {
      const {
        data: { session },
      } = await supabase.auth.getSession();
      const token = session?.access_token ?? null;
      const res = await fetch(`${API}/refine-selection`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
          ...(token ? { Authorization: `Bearer ${token}` } : {}),
        },
        body: JSON.stringify({
          selected_text: selectedText,
          instruction,
          full_post: fullPost,
        }),
      });
      if (!res.ok) throw new Error("refineSelection failed");
      return res.json();
    },

    scorePost: (post_content: string) =>
      apiFetch("/score", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ post_content }),
      }),

    generateVisuals: (post_content: string) =>
      apiFetch("/generate-visuals", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ post_content }),
      }),

    refineVisual: (
      svgCode: string,
      refinementInstruction: string,
      originalDescription: string,
      styleHint?: string
    ) =>
      apiFetch("/refine-visual", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          svg_code: svgCode,
          refinement_instruction: refinementInstruction,
          original_description: originalDescription,
          style_hint: styleHint ?? null,
        }),
      }),

    // ── Library ───────────────────────────────────────────────────────────
    getLibrary: () => apiFetch("/library"),

    getLibraryClusters: async (): Promise<LibraryClustersResponse> => {
      const res = await apiFetch("/library/clusters");
      if (!res.ok) throw new Error(`GET /library/clusters failed with status ${res.status}`);
      return res.json();
    },

    deleteSource: (source_title: string) =>
      apiFetch("/library/source", {
        method: "DELETE",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ source_title }),
      }),

    // ── History ───────────────────────────────────────────────────────────
    getHistory: () => apiFetch("/history"),

    logPost: (body: LogPostRequest) =>
      apiFetch("/log-post", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),

    patchPost: (post_id: number, body: PatchPostRequest) =>
      apiFetch(`/history/${post_id}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(body),
      }),

    deletePost: (post_id: number) =>
      apiFetch(`/history/${post_id}`, { method: "DELETE" }),

    restoreVersion: (post_id: number, version_id: number) =>
      apiFetch(`/history/${post_id}/restore/${version_id}`, {
        method: "POST",
      }),

    markAsPublished: (post_id: number, platform: string, published_content?: string) =>
      apiFetch(`/history/${post_id}/publish`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ platform, published_content: published_content ?? null }),
      }),

    // ── Ideas ─────────────────────────────────────────────────────────────
    getSuggestions: (count: number, topic?: string) =>
      apiFetch(
        `/suggestions?count=${count}${topic ? `&topic=${encodeURIComponent(topic)}` : ""}`
      ),

    // ── Stats ─────────────────────────────────────────────────────────────
    getStats: () => apiFetch("/stats"),

    // ── Feedback ──────────────────────────────────────────────────────────
    submitFeedback: (message: string, page: string) =>
      apiFetch("/feedback", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message, page }),
      }),

    // ── Analytics ─────────────────────────────────────────────────────────
    logEvent: (payload: {
      event_type: string;
      page_url?: string;
      button_name?: string;
      metadata?: Record<string, unknown>;
    }) =>
      apiFetch("/log-event", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(payload),
      }),

    // ── Profile ───────────────────────────────────────────────────────────
    getProfile: () => apiFetch("/profile"),

    extractResume: (file: File) => {
      const formData = new FormData();
      formData.append("file", file);
      return apiFetch("/extract-resume", { method: "POST", body: formData });
    },

    saveProfile: async (profile: ProfileData) => {
      const res = await apiFetch("/profile", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(profile),
      });
      console.log("[api.saveProfile] status:", res.status, "ok:", res.ok);
      if (!res.ok) {
        const body = await res.text().catch(() => "(unreadable)");
        console.error("[api.saveProfile] error body:", body);
        throw new Error(`POST /profile failed with status ${res.status}: ${body}`);
      }
      return res;
    },
  };
}
