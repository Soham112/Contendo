"use client";

import React, { useState } from "react";
import { motion } from "motion/react";
import {
  EMPTY_BUSINESS_PROFILE,
  businessFormErrors,
  normaliseWebsite,
  type BusinessProfile,
  type BusinessProfileErrors,
  type NicheOptions,
  type SegmentAnswer,
} from "@/lib/account";
import { Button } from "@/components/ui/button";
import { riseIn, transition } from "@/components/ui/motion";
import { ErrorState } from "@/components/ui/states";
import { chipClass } from "@/components/ui/chip";

const FIELD = "w-full min-h-11 rounded-t-md bg-surface-container-low px-3 py-2.5 text-[1rem] text-on-surface placeholder:text-placeholder border-0 border-b-[1.5px] border-outline focus:outline-none focus:border-b-2 focus:border-primary focus-visible:ring-2 focus-visible:ring-primary/30 aria-[invalid=true]:border-error";

function Field({
  id,
  label,
  hint,
  error,
  children,
}: {
  id: string;
  label: string;
  hint?: string;
  error?: string;
  children: React.ReactNode;
}) {
    // The control gets the hint and error as its description, and is marked invalid with an error.
  const described = [hint && `${id}-hint`, error && `${id}-error`].filter(Boolean).join(" ") || undefined;
  const control = React.isValidElement(children)
    ? React.cloneElement(children as React.ReactElement<Record<string, unknown>>, { "aria-describedby": described, "aria-invalid": error ? true : undefined })
    : children;
  return (
    <div>
      <label htmlFor={id} className="label-caps text-secondary">
        {label}
      </label>
      {hint && <p id={`${id}-hint`} className="mt-1 text-[0.8125rem] text-secondary">{hint}</p>}
      <div className="mt-2">{control}</div>
      {error && (
        <p id={`${id}-error`} role="alert" className="mt-1.5 text-[0.8125rem] text-error">
          {error}
        </p>
      )}
    </div>
  );
}

/**
 * Niche, then the business profile. Everything here is saved to the user's
 * memory as a source, so their first post has real material to draw on.
 *
 * Other ways to fill the profile (import from a website, voice input) belong
 * in `prefill`: they produce the same BusinessProfile fields this form edits,
 * so nothing after this component changes when they are added.
 */
export default function BusinessSetup({
  options,
  initialNiche,
  prefill,
  busy,
  error,
  onBack,
  onSubmit,
  onStep,
}: {
  options: NicheOptions;
  initialNiche: string | null;
  prefill?: Partial<BusinessProfile>;
  busy: boolean;
  error: string;
  onBack: () => void;
  onSubmit: (answer: SegmentAnswer) => void;
  onStep: (step: "niche" | "business_profile", outcome: "started" | "completed") => void;
}) {
  const [stage, setStage] = useState<"niche" | "profile">("niche");
  const [niche, setNiche] = useState<string | null>(initialNiche);
  const [nicheOther, setNicheOther] = useState("");
  const [profile, setProfile] = useState<BusinessProfile>({ ...EMPTY_BUSINESS_PROFILE, ...prefill });
  const [errors, setErrors] = useState<BusinessProfileErrors>({});

  function set<K extends keyof BusinessProfile>(key: K, value: BusinessProfile[K]) {
    setProfile((prev) => ({ ...prev, [key]: value }));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
    if (stage === "niche") {
      if (!niche || (niche === options.other_niche && !nicheOther.trim())) { setErrors({ niche: "Choose your kind of business." }); return; }
      onStep("niche", "completed");
      onStep("business_profile", "started");
      setErrors({}); setStage("profile"); return;
    }
    const found = businessFormErrors(niche, nicheOther, profile, options);
    setErrors(found);
    if (Object.keys(found).length > 0) return;
    onSubmit({
      segment: "business",
      business_niche: niche,
      business_niche_other: niche === options.other_niche ? nicheOther.trim() : null,
      business_profile: { ...profile, website: normaliseWebsite(profile.website) },
    });
  }

  return (
    <form onSubmit={submit} noValidate className="w-full flex flex-col gap-7">
      <div>
        <h1 className="font-headline text-[1.5rem] sm:text-[1.75rem] leading-snug text-on-surface">
          Tell us about your business
        </h1>
        <p className="mt-3 text-[0.9375rem] leading-relaxed text-secondary">
          Your posts are written only from what you tell us. Nothing is made up, so the more you add here, the more
          we have to work with.
        </p>
      </div>

      {/* Each stage fades and rises in. */}
      <motion.div key={stage} initial={riseIn.initial} animate={riseIn.animate} transition={transition.base} className="flex flex-col gap-7">
      {stage === "niche" && <fieldset>
        <legend className="label-caps text-secondary">What kind of business?</legend>
        <div className="mt-3 flex flex-wrap gap-2">
          {options.niches.map((option) => {
            const selected = niche === option.key;
            return (
              <button
                key={option.key}
                type="button"
                aria-pressed={selected}
                onClick={() => setNiche(option.key)}
                className={chipClass(selected)}
              >
                {option.label}
              </button>
            );
          })}
        </div>
        {niche === options.other_niche && (
          <input
            aria-label="Your kind of business"
            className={`${FIELD} mt-3`}
            value={nicheOther}
            maxLength={80}
            placeholder="e.g. Dog groomer"
            onChange={(e) => setNicheOther(e.target.value)}
          />
        )}
        {errors.niche && (
          <p role="alert" className="mt-1.5 text-[0.8125rem] text-error">
            {errors.niche}
          </p>
        )}
      </fieldset>}

      {stage === "profile" && <>
      <Field id="business_name" label="Business name" error={errors.business_name}>
        <input
          id="business_name"
          className={FIELD}
          value={profile.business_name}
          maxLength={120}
          autoComplete="organization"
          onChange={(e) => set("business_name", e.target.value)}
        />
      </Field>

      <Field id="service_area" label="City or area you serve" error={errors.service_area}>
        <input
          id="service_area"
          className={FIELD}
          value={profile.service_area}
          maxLength={120}
          onChange={(e) => set("service_area", e.target.value)}
        />
      </Field>



      <Field
        id="services"
        label="What you do"
        hint="The services you offer, in a sentence or two."
        error={errors.services}
      >
        <textarea
          id="services"
          className={`${FIELD} min-h-[5.5rem] leading-relaxed`}
          value={profile.services}
          maxLength={600}
          onChange={(e) => set("services", e.target.value)}
        />
      </Field>

      <Field id="differentiators" label="What makes you different (optional)">
        <textarea
          id="differentiators"
          className={`${FIELD} min-h-[4.5rem] leading-relaxed`}
          value={profile.differentiators}
          maxLength={400}
          onChange={(e) => set("differentiators", e.target.value)}
        />
      </Field>



      <Field
        id="current_offers"
        label="Current offers (optional)"
        hint="Anything you're promoting right now. You can change this later."
      >
        <textarea
          id="current_offers"
          className={`${FIELD} min-h-[4.5rem] leading-relaxed`}
          value={profile.current_offers}
          maxLength={400}
          onChange={(e) => set("current_offers", e.target.value)}
        />
      </Field>

      <fieldset>
        <legend className="label-caps text-secondary">How should your posts sound?</legend>
        <div className="mt-3 flex flex-col gap-2">
          {options.tones.map((tone) => (
            <label
              key={tone.key}
              className={`flex min-h-11 items-center gap-3 rounded-xl border px-4 py-3 text-[0.9375rem] cursor-pointer transition-colors duration-150 ease-out has-[:focus-visible]:ring-2 has-[:focus-visible]:ring-primary ${
                profile.tone === tone.key
                  ? "border-primary bg-primary-container text-on-primary-fixed"
                  : "border-outline bg-surface-container-lowest text-on-surface hover:bg-surface-container-low"
              }`}
            >
              <input
                type="radio"
                name="tone"
                value={tone.key}
                checked={profile.tone === tone.key}
                onChange={() => set("tone", tone.key)}
                className="h-5 w-5 accent-primary"
              />
              {tone.label}
            </label>
          ))}
        </div>
        {errors.tone && (
          <p role="alert" className="mt-1.5 text-[0.8125rem] text-error">
            {errors.tone}
          </p>
        )}
        <input
          aria-label="Anything else about your tone (optional)"
          className={`${FIELD} mt-3`}
          value={profile.tone_notes}
          maxLength={300}
          placeholder="Anything else? e.g. never pushy, no jargon"
          onChange={(e) => set("tone_notes", e.target.value)}
        />
      </fieldset>
      </>}
      </motion.div>

      {error && <ErrorState message={error} />}

      <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
        <Button
          variant="secondary"
          onClick={() => { if (stage === "profile") { setStage("niche"); onStep("niche", "started"); } else onBack(); }}
          disabled={busy}
        >
          Back
        </Button>
        <Button type="submit" size="lg" loading={busy}>
          {stage === "niche" ? "Continue" : "Create my first post"}
        </Button>
      </div>
    </form>
  );
}
