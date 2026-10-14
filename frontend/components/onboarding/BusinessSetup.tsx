"use client";

import { useState } from "react";
import {
  EMPTY_BUSINESS_PROFILE,
  businessFormErrors,
  normaliseWebsite,
  type BusinessProfile,
  type BusinessProfileErrors,
  type NicheOptions,
  type SegmentAnswer,
} from "@/lib/account";

const FIELD = "input-editorial w-full px-3 py-2.5 text-[1rem] text-on-surface placeholder:text-outline";

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
  return (
    <div>
      <label htmlFor={id} className="label-caps text-secondary">
        {label}
      </label>
      {hint && <p className="mt-1 text-[0.8125rem] text-secondary">{hint}</p>}
      <div className="mt-2">{children}</div>
      {error && (
        <p role="alert" className="mt-1.5 text-[0.8125rem] text-error">
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
}: {
  options: NicheOptions;
  initialNiche: string | null;
  prefill?: Partial<BusinessProfile>;
  busy: boolean;
  error: string;
  onBack: () => void;
  onSubmit: (answer: SegmentAnswer) => void;
}) {
  const [niche, setNiche] = useState<string | null>(initialNiche);
  const [nicheOther, setNicheOther] = useState("");
  const [profile, setProfile] = useState<BusinessProfile>({ ...EMPTY_BUSINESS_PROFILE, ...prefill });
  const [errors, setErrors] = useState<BusinessProfileErrors>({});

  function set<K extends keyof BusinessProfile>(key: K, value: BusinessProfile[K]) {
    setProfile((prev) => ({ ...prev, [key]: value }));
  }

  function submit(e: React.FormEvent) {
    e.preventDefault();
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

      <fieldset>
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
                className={`rounded-full px-4 py-2.5 text-[0.9375rem] transition-colors ${
                  selected
                    ? "bg-primary-container text-on-primary-fixed outline outline-1 outline-primary"
                    : "bg-surface-container-low text-on-surface hover:bg-surface-container-highest"
                }`}
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
      </fieldset>

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

      <Field id="website" label="Website (optional)" error={errors.website}>
        <input
          id="website"
          className={FIELD}
          value={profile.website}
          inputMode="url"
          autoComplete="url"
          placeholder="yourbusiness.com"
          onChange={(e) => set("website", e.target.value)}
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

      <Field id="typical_customer" label="Your typical customer (optional)">
        <textarea
          id="typical_customer"
          className={`${FIELD} min-h-[4.5rem] leading-relaxed`}
          value={profile.typical_customer}
          maxLength={400}
          onChange={(e) => set("typical_customer", e.target.value)}
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
              className={`flex items-center gap-3 rounded-lg px-4 py-3 text-[0.9375rem] cursor-pointer transition-colors ${
                profile.tone === tone.key
                  ? "bg-primary-container text-on-primary-fixed"
                  : "bg-surface-container-low text-on-surface hover:bg-surface-container-highest"
              }`}
            >
              <input
                type="radio"
                name="tone"
                value={tone.key}
                checked={profile.tone === tone.key}
                onChange={() => set("tone", tone.key)}
                className="accent-primary"
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

      {error && (
        <p role="alert" className="text-[0.875rem] text-error">
          {error}
        </p>
      )}

      <div className="flex flex-col-reverse sm:flex-row sm:items-center sm:justify-between gap-3">
        <button
          type="button"
          onClick={onBack}
          disabled={busy}
          className="text-[0.875rem] text-secondary hover:text-on-surface py-2 disabled:opacity-50"
        >
          Back
        </button>
        <button
          type="submit"
          disabled={busy}
          className="btn-primary text-white px-6 py-3 rounded-md text-[0.9375rem] font-medium disabled:opacity-50 disabled:cursor-not-allowed"
        >
          {busy ? "Saving…" : "Save and continue"}
        </button>
      </div>
    </form>
  );
}
