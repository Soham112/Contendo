// A post's text as it leaves Contendo: what the copy button puts on the
// clipboard and what the platform preview shows are the same string.

/** Markdown the editor may hold, reduced to plain text (social platforms show it literally). */
export function stripMarkdown(text: string): string {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/\*([^*\n]+)\*/g, "$1")
    .replace(/_([^_\n]+)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "");
}

/** Strip [DIAGRAM:...] and [IMAGE:...] placeholders from text for clipboard. */
export function stripPlaceholders(text: string): string {
  return text.replace(/\[(DIAGRAM|IMAGE):[^\]]+\]/gi, "").replace(/\n{3,}/g, "\n\n").trim();
}

/** The text a user gets when they copy a post for a social platform. */
export function pastedText(text: string): string {
  return stripMarkdown(stripPlaceholders(text));
}

/** Up to two initials from a name, for an avatar without a photo. "?" when there is no name. */
export function initials(name: string): string {
  const letters = name
    .trim()
    .split(/\s+/)
    .filter(Boolean)
    .slice(0, 2)
    .map((word) => Array.from(word)[0]?.toLocaleUpperCase() ?? "");
  return letters.join("") || "?";
}

export interface PostStats {
  wordCount: number;
  charCount: number;
  /** Minutes at 200 words a minute, to the nearest half minute. */
  readingTime: number;
  /** How many 280-character tweets the text would fill. */
  tweetCount: number;
}

export function getPostStats(text: string): PostStats {
  const wordCount = text.trim().split(/\s+/).filter(Boolean).length;
  const charCount = text.length;
  const readingTime = Math.round((wordCount / 200) * 2) / 2;
  const tweetCount = Math.ceil(charCount / 280);
  return { wordCount, charCount, readingTime, tweetCount };
}
