// Types and pure helpers for the segment question and the business profile.
// The niche, pillar and tone lists are never written here: they come from the
// backend (GET /niches, backend/config/niches.py).

export type Segment = "business" | "individual";

export interface PillarOption {
  key: string;
  label: string;
  about: string;
}

export interface NicheOption {
  key: string;
  label: string;
  pillars: PillarOption[];
}

export interface ToneOption {
  key: string;
  label: string;
}

export interface NicheOptions {
  segments: Segment[];
  other_niche: string;
  niches: NicheOption[];
  tones: ToneOption[];
}

export interface BusinessProfile {
  business_name: string;
  service_area: string;
  website: string;
  services: string;
  differentiators: string;
  typical_customer: string;
  current_offers: string;
  tone: string;
  tone_notes: string;
}

export interface Account {
  segment: Segment | null;
  business_niche: string | null;
  business_niche_other: string | null;
  business_profile: BusinessProfile | null;
  /** Whether to show the segment question now. Decided by the backend. */
  ask_segment: boolean;
  /** Set only by a business save: whether the profile reached the user's memory. */
  memory_saved?: boolean | null;
}

export interface SegmentAnswer {
  segment: Segment;
  business_niche?: string | null;
  business_niche_other?: string | null;
  business_profile?: BusinessProfile | null;
}

export const EMPTY_BUSINESS_PROFILE: BusinessProfile = {
  business_name: "",
  service_area: "",
  website: "",
  services: "",
  differentiators: "",
  typical_customer: "",
  current_offers: "",
  tone: "",
  tone_notes: "",
};

/** The niche key a URL asked for, or null unless it is one the backend lists. */
export function resolveNicheParam(
  param: string | null | undefined,
  options: Pick<NicheOptions, "niches">
): string | null {
  if (!param) return null;
  return options.niches.some((niche) => niche.key === param) ? param : null;
}

/** A website as the backend accepts it: "" stays "", a bare domain gets https://. */
export function normaliseWebsite(input: string): string {
  const value = input.trim();
  if (!value) return "";
  return /^https?:\/\//i.test(value) ? value : `https://${value}`;
}

export type BusinessProfileErrors = Partial<Record<keyof BusinessProfile | "niche", string>>;

/**
 * What stops the business form being sent. This only saves a round trip: the
 * backend validates every field again and is what decides.
 */
export function businessFormErrors(
  niche: string | null,
  nicheOther: string,
  profile: BusinessProfile,
  options: Pick<NicheOptions, "other_niche">
): BusinessProfileErrors {
  const errors: BusinessProfileErrors = {};
  if (!niche) errors.niche = "Choose the kind of business you run.";
  else if (niche === options.other_niche && !nicheOther.trim())
    errors.niche = "Tell us what kind of business you run.";
  if (!profile.business_name.trim()) errors.business_name = "Add your business name.";
  if (!profile.service_area.trim()) errors.service_area = "Add the city or area you serve.";
  if (!profile.services.trim()) errors.services = "Describe what you do in a sentence or two.";
  if (!profile.tone) errors.tone = "Choose a tone.";
  const website = normaliseWebsite(profile.website);
  if (website) {
    try {
      if (!new URL(website).hostname.includes(".")) errors.website = "That doesn't look like a web address.";
    } catch {
      errors.website = "That doesn't look like a web address.";
    }
  }
  return errors;
}
