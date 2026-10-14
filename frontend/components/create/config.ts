// Constants, option lists and shapes shared by the create screen's parts.

import type { Grounding } from "@/components/GroundingNotice";
import type { ClosestSource } from "@/lib/api";

export const SS_POST = "contentOS_last_post";
export const SS_SCORE = "contentOS_last_score";
export const SS_FEEDBACK = "contentOS_last_feedback";
export const SS_ITERATIONS = "contentOS_last_iterations";
export const SS_VISUALS = "contentOS_last_visuals";
export const SS_IDEAS = "contentOS_last_ideas";
export const SS_SHOW_ANALYSIS = "contentOS_show_analysis";
export const SS_CURRENT_POST_ID = "contentOS_current_post_id";
export const SS_TOPIC = "contentOS_last_topic_meta";
export const SS_FORMAT = "contentOS_last_format_meta";
export const SS_TONE = "contentOS_last_tone_meta";
export const SS_LENGTH = "contentOS_last_length";
export const SS_SCORED = "contentOS_last_scored";
export const SS_RAW_POST = "contentOS_raw_post";


export type Format = "linkedin post" | "medium article" | "thread";
export type Tone = "casual" | "technical" | "storytelling";
export type Length = "concise" | "standard" | "long-form";

export const FORMATS: { id: Format; label: string }[] = [
  { id: "linkedin post", label: "LinkedIn Post" },
  { id: "medium article", label: "Medium Article" },
  { id: "thread", label: "Thread" },
];

export const TONES: { id: Tone; label: string; description: string }[] = [
  { id: "casual", label: "Casual", description: "Like texting a smart friend" },
  { id: "technical", label: "Technical", description: "Precise, assumes expertise" },
  { id: "storytelling", label: "Storytelling", description: "Scene-driven, lesson earned" },
];

export const TONE_DISPLAY_LABELS: Record<Tone, string> = {
  casual: "Casual",
  technical: "Technical",
  storytelling: "Storytelling",
};

export const TONE_DESCRIPTIONS: Record<Tone, string> = {
  casual: "Conversational and direct. First-person, short sentences. Focus on clarity and utility.",
  technical: "Precise and substantive. Uses domain language without over-explaining. Respects expertise.",
  storytelling: "Narrative-first. Opens with a moment, builds tension, lands on a lesson.",
};

export const LENGTHS: { id: Length; label: string }[] = [
  { id: "concise", label: "Concise" },
  { id: "standard", label: "Standard" },
  { id: "long-form", label: "Long-form" },
];

export const LENGTH_META: Record<Format, Record<Length, string>> = {
  "linkedin post": {
    concise: "~100-150 words",
    standard: "~200-300 words",
    "long-form": "~400-600 words",
  },
  "medium article": {
    concise: "~350-500 words",
    standard: "~700-900 words",
    "long-form": "~1200-1600 words",
  },
  thread: {
    concise: "4-5 tweets",
    standard: "7-9 tweets",
    "long-form": "11-14 tweets",
  },
};

export interface GenerateResult {
  grounding?: Grounding | null;
  status?: "ok" | "low_coverage" | "draft_truncated" | "draft_refused" | "needs_review";
  message?: string;
  post: string;
  score: number;
  score_feedback: string[];
  iterations: number;
  scored: boolean;
  trace_id?: string | null;
  closest_sources?: ClosestSource[];
  no_specifics_enabled?: boolean;
}

export interface Suggestion {
  title: string;
  angle: string;
  format: string;
  reasoning: string;
}

export interface Visual {
  type: "diagram" | "image_reminder";
  placeholder: string;
  description: string;
  position: number;
  svg_code: string | null;
  reminder_text: string | null;
}

export const FORMAT_BADGE: Record<string, string> = {
  "linkedin post": "LinkedIn",
  "medium article": "Medium",
  "thread": "Thread",
};
