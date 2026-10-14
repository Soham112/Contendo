"use client";

import { useEffect, useState } from "react";
import { useApi } from "@/lib/api";
import { Textarea } from "@/components/ui/field";
import type { PillarOption } from "@/lib/account";
import { chipClass } from "@/components/ui/chip";

export interface BusinessPost {
  /** The user's niche pillars; empty for individuals and niches without any. */
  pillars: PillarOption[];
  pillar: string | null;
  setPillar: (key: string | null) => void;
  details: string;
  setDetails: (value: string) => void;
  /** The fields to add to a /generate request. */
  requestFields: () => { pillar?: string; pillar_details?: string };
  /** Call after a post is generated: the details are in memory now. */
  clearDetails: () => void;
}

/** What a business user is posting about. Loads nothing useful for individuals. */
export function useBusinessPost(): BusinessPost {
  const api = useApi();
  const [pillars, setPillars] = useState<PillarOption[]>([]);
  const [pillar, setPillar] = useState<string | null>(null);
  const [details, setDetails] = useState("");

  useEffect(() => {
    let cancelled = false;
    Promise.all([api.getAccount(), api.getNicheOptions()])
      .then(([account, options]) => {
        if (cancelled || account.segment !== "business") return;
        setPillars(options.niches.find((niche) => niche.key === account.business_niche)?.pillars ?? []);
      })
      // The create screen works without pillars.
      .catch(() => {});
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return {
    pillars,
    pillar,
    setPillar,
    details,
    setDetails,
    requestFields: () => (pillar ? { pillar, pillar_details: details.trim() } : {}),
    clearDetails: () => setDetails(""),
  };
}

/** Kind of post, and its details. Renders nothing unless the user's niche has pillars. */
export default function BusinessPostFields({ business }: { business: BusinessPost }) {
  if (business.pillars.length === 0) return null;
  const chosen = business.pillars.find((pillar) => pillar.key === business.pillar);

  return (
    <div>
      <p id="kind-of-post" className="label-caps mb-2.5 text-on-surface-variant">Kind of post</p>
      <div role="group" aria-labelledby="kind-of-post" className="flex flex-wrap gap-2">
        {business.pillars.map((pillar) => {
          const selected = pillar.key === business.pillar;
          return (
            <button
              key={pillar.key}
              type="button"
              aria-pressed={selected}
              onClick={() => business.setPillar(selected ? null : pillar.key)}
              className={chipClass(selected)}
            >
              {pillar.label}
            </button>
          );
        })}
      </div>

      {chosen && (
        <div className="mt-4">
          <label htmlFor="pillar-details" className="block text-[0.875rem] text-on-surface-variant leading-relaxed">
            {chosen.about} Give us the details: we only write what you tell us, and we save it to your memory for
            later posts.
          </label>
          <Textarea
            id="pillar-details"
            rows={4}
            maxLength={4000}
            value={business.details}
            onChange={(e) => business.setDetails(e.target.value)}
            className="mt-2"
          />
        </div>
      )}
    </div>
  );
}
