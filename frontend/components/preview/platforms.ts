// Everything the post preview knows about a platform. PostPreview and
// PostMockup render any entry here, so adding a platform is one more entry,
// not a new component. LinkedIn only for now: the platform writes LinkedIn posts.
//
// Icons are neutral lucide icons and colours are plain greys and text colours:
// no platform logos or marks.

import type { LucideIcon } from "lucide-react";
import { MessageSquare, Repeat2, Send, ThumbsUp } from "lucide-react";
import type { CountingRule } from "@/lib/post-length";

export type Device = "desktop" | "mobile";
export type Theme = "light" | "dark";

export interface PlatformColors {
  /** Around the post (the feed). */
  page: string;
  card: string;
  text: string;
  muted: string;
  /** Background of characters past the limit. */
  overflow: string;
}

export interface PlatformConfig {
  id: string;
  label: string;
  /** The platform's own limit for one post, counted by `counting`. */
  maxCharacters: number;
  counting: CountingRule;
  /** Rendered width of the post card in CSS pixels, per device. */
  cardWidth: Record<Device, number>;
  /** Space around the card, showing the feed behind it. */
  feedPadding: Record<Device, number>;
  font: { size: number; lineHeight: number };
  /**
   * How the feed cuts a long post. The platform cuts by rendered lines, not by
   * characters, so the preview clamps lines at the card's real width and font.
   * Omit when the feed shows the whole post.
   */
  seeMore?: { label: string; lines: Record<Device, number> };
  /** What sits under the name: the author's headline, or their @handle beside it. */
  byline: "headline" | "handle";
  timestamp: string;
  actions: { label: string; icon: LucideIcon }[];
  /** Whether each action shows its word next to its icon. */
  actionLabels: boolean;
  colors: Record<Theme, PlatformColors>;
}

export const PLATFORMS: PlatformConfig[] = [
  {
    id: "linkedin",
    label: "LinkedIn",
    maxCharacters: 3000,
    counting: "codepoints",
    cardWidth: { desktop: 555, mobile: 375 },
    feedPadding: { desktop: 24, mobile: 0 },
    font: { size: 14, lineHeight: 20 },
    // About 3 lines before the cut on both devices, which matches the usual
    // "about 210 characters on desktop, 140 on mobile" at each card's width.
    // LinkedIn doesn't publish these numbers and changes them: check them
    // against a real post now and then, and adjust them here.
    seeMore: { label: "…see more", lines: { desktop: 3, mobile: 3 } },
    byline: "headline",
    timestamp: "Now",
    actions: [
      { label: "Like", icon: ThumbsUp },
      { label: "Comment", icon: MessageSquare },
      { label: "Repost", icon: Repeat2 },
      { label: "Send", icon: Send },
    ],
    actionLabels: true,
    colors: {
      light: { page: "#f4f2ee", card: "#ffffff", text: "rgba(0,0,0,0.9)", muted: "rgba(0,0,0,0.6)", overflow: "rgba(204,16,22,0.18)" },
      dark: { page: "#000000", card: "#1b1f23", text: "rgba(255,255,255,0.9)", muted: "rgba(255,255,255,0.6)", overflow: "rgba(242,92,84,0.3)" },
    },
  },
];

export function platformById(id: string): PlatformConfig {
  return PLATFORMS.find((platform) => platform.id === id) ?? PLATFORMS[0];
}

/** What the preview shows about the author. Missing parts show neutral placeholders. */
export interface PreviewAuthor {
  name: string;
  headline?: string;
  handle?: string;
  avatarUrl?: string | null;
}

/** Placeholders for a viewer with no profile, e.g. on the public tool page. */
export const PLACEHOLDER_AUTHOR: PreviewAuthor = { name: "Your Name", headline: "Your headline", handle: "yourhandle" };
