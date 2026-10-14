// How long a post is by a platform's own counting rule, and where it first
// goes over the limit, so the preview can count and mark the overflow the way
// the platform will.

export type CountingRule = "codepoints" | "x-weighted";

export interface LengthResult {
  /** The length as the platform counts it. */
  count: number;
  /** UTF-16 index in the text where the limit is first exceeded; null when it fits. */
  overflowAt: number | null;
}

// X's published counting rules (twitter-text v3 configuration): code points in
// these ranges weigh 1, every other code point 2 (CJK, Unicode bold and italic
// letters...), an emoji sequence 2, and a link always 23.
const X_LIGHT_RANGES: [number, number][] = [[0, 4351], [8192, 8205], [8208, 8223], [8242, 8247]];
const X_LINK_LENGTH = 23;
const X_HEAVY = 2;

// A link X shortens: one starting with a scheme or "www.". Bare domains
// ("example.com") are counted as typed here; X shortens those too, so a post
// with one can count a little longer here than on X, never shorter.
const LINK = /\b(?:https?:\/\/|www\.)[^\s]+/gi;
const TRAILING_PUNCTUATION = /[.,!?;:)\]'"]+$/;
// A multi-code-point emoji sequence (ZWJ families, flags, keycaps, "©️").
const EMOJI = /\p{Extended_Pictographic}|\p{Regional_Indicator}|⃣/u;

interface Unit {
  start: number;
  weight: number;
}

function graphemes(text: string): { segment: string; index: number }[] {
  if (typeof Intl !== "undefined" && "Segmenter" in Intl) {
    return Array.from(new Intl.Segmenter(undefined, { granularity: "grapheme" }).segment(text));
  }
  // Without Intl.Segmenter, fall back to code points.
  const out: { segment: string; index: number }[] = [];
  let index = 0;
  for (const segment of text) {
    out.push({ segment, index });
    index += segment.length;
  }
  return out;
}

function linkSpans(text: string): [number, number][] {
  return Array.from(text.matchAll(LINK), (match) => {
    const url = match[0].replace(TRAILING_PUNCTUATION, "");
    return [match.index ?? 0, (match.index ?? 0) + url.length] as [number, number];
  });
}

function xWeight(grapheme: string): number {
  const normal = grapheme.normalize("NFC");
  // A lone code point is weighed by its range (a bare "©" is 1, "😀" is 2);
  // a sequence that forms an emoji is 2 however many code points it has.
  if (Array.from(normal).length > 1 && EMOJI.test(normal)) return X_HEAVY;
  let weight = 0;
  for (const char of normal) {
    const code = char.codePointAt(0) ?? 0;
    weight += X_LIGHT_RANGES.some(([low, high]) => code >= low && code <= high) ? 1 : X_HEAVY;
  }
  return weight;
}

function xUnits(text: string): Unit[] {
  const links = linkSpans(text);
  const units: Unit[] = [];
  for (const { segment, index } of graphemes(text)) {
    const link = links.find(([start, end]) => index >= start && index < end);
    if (link) {
      if (index === link[0]) units.push({ start: index, weight: X_LINK_LENGTH });
      continue;
    }
    units.push({ start: index, weight: xWeight(segment) });
  }
  return units;
}

function codepointUnits(text: string): Unit[] {
  const units: Unit[] = [];
  let index = 0;
  for (const char of text) {
    units.push({ start: index, weight: 1 });
    index += char.length;
  }
  return units;
}

/** The text's length under `rule`, and where it first exceeds `limit`. */
export function measure(text: string, rule: CountingRule, limit: number): LengthResult {
  const units = rule === "x-weighted" ? xUnits(text) : codepointUnits(text);
  let count = 0;
  let overflowAt: number | null = null;
  for (const unit of units) {
    count += unit.weight;
    if (overflowAt === null && count > limit) overflowAt = unit.start;
  }
  return { count, overflowAt };
}
