"use client";

import { useAuth } from "@clerk/nextjs";

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
 * Returns typed API functions with the Clerk Bearer token pre-attached.
 * Falls back gracefully when no token is present (backend allows this in
 * non-production via the dev fallback to user_id="default").
 */
export function useApi() {
  const { getToken } = useAuth();

  async function apiFetch(
    path: string,
    options: RequestInit = {}
  ): Promise<Response> {
    const token = await getToken();
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

    // ── Library ───────────────────────────────────────────────────────────
    getLibrary: () => apiFetch("/library"),

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

    // ── Ideas ─────────────────────────────────────────────────────────────
    getSuggestions: (count: number, topic?: string) =>
      apiFetch(
        `/suggestions?count=${count}${topic ? `&topic=${encodeURIComponent(topic)}` : ""}`
      ),

    // ── Stats ─────────────────────────────────────────────────────────────
    getStats: () => apiFetch("/stats"),

    // ── Profile ───────────────────────────────────────────────────────────
    getProfile: () => apiFetch("/profile"),

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
