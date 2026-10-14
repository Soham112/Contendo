"use client";

import React, { useState, useEffect, useCallback, useId } from "react";
import Link from "next/link";
import { useApi } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import TagInput from "@/components/ui/TagInput";
import { Button } from "@/components/ui/button";
import { ErrorState } from "@/components/ui/states";

// ── Shared input class ────────────────────────────────────────────────────────
const inputCls =
  "w-full min-h-11 bg-surface-container-lowest border-0 border-b-[1.5px] border-b-outline rounded-t-md focus:border-b-2 focus:border-b-primary focus-visible:ring-2 focus-visible:ring-primary/30 outline-none px-3 py-2.5 text-[0.9375rem] text-on-surface placeholder:text-placeholder transition-colors resize-none";

// ── Form state ────────────────────────────────────────────────────────────────
interface SettingsForm {
  name: string;
  role: string;
  bio: string;
  location: string;
  target_audience: string;
  topics_of_expertise: string[];
  voice_descriptors: string[];
  words_to_avoid: string[];
  writing_rules: string[];
  opinions: string[];
  writing_samples: string[];
  technical_voice_notes: string; // textarea — joined with \n; split on save
  linkedin_style_notes: string;
  medium_style_notes: string;
  thread_style_notes: string;
  // eslint-disable-next-line @typescript-eslint/no-explicit-any
  projects: any; // preserved, not shown in UI
}

function emptyForm(): SettingsForm {
  return {
    name: "",
    role: "",
    bio: "",
    location: "",
    target_audience: "",
    topics_of_expertise: [],
    voice_descriptors: [],
    words_to_avoid: [],
    writing_rules: [""],
    opinions: [""],
    writing_samples: [""],
    technical_voice_notes: "",
    linkedin_style_notes: "",
    medium_style_notes: "",
    thread_style_notes: "",
    projects: [],
  };
}

// ── Field wrapper ─────────────────────────────────────────────────────────────
function Field({
  label,
  optional,
  children,
}: {
  label: string;
  optional?: boolean;
  children: React.ReactNode;
}) {
  // The label names the field's first control: it gets this id unless it has one.
  const id = useId();
  const items = React.Children.toArray(children);
  const [first, ...rest] = items;
  const control = React.isValidElement<{ id?: string }>(first) ? React.cloneElement(first, { id: first.props.id ?? id }) : first;
  const controlId = React.isValidElement<{ id?: string }>(first) ? (first.props.id ?? id) : undefined;
  return (
    <div className="flex flex-col gap-1.5">
      <label htmlFor={controlId} className="label-caps text-secondary">
        {label}
        {optional && (
          <span className="normal-case tracking-normal font-normal text-on-surface-variant ml-1">
            (optional)
          </span>
        )}
      </label>
      {control}
      {rest}
    </div>
  );
}

// ── Loading skeleton ──────────────────────────────────────────────────────────
function LoadingSkeleton() {
  return (
    <div className="flex flex-col gap-6 mt-8">
      <div className="bg-surface-container animate-pulse rounded h-4 w-1/3" />
      <div className="bg-surface-container animate-pulse rounded h-4 w-2/3" />
      <div className="bg-surface-container animate-pulse rounded h-4 w-1/2" />
    </div>
  );
}

// ── Dynamic list (rules / opinions / samples) ─────────────────────────────────
function DynamicList({
  items,
  onChange,
  max,
  addLabel,
  renderItem,
}: {
  items: string[];
  onChange: (items: string[]) => void;
  max: number;
  addLabel: string;
  renderItem: (
    value: string,
    index: number,
    onItemChange: (v: string) => void
  ) => React.ReactNode;
}) {
  function updateItem(i: number, v: string) {
    const next = [...items];
    next[i] = v;
    onChange(next);
  }
  return (
    <div className="flex flex-col gap-3">
      {items.map((item, i) => renderItem(item, i, (v) => updateItem(i, v)))}
      {items.length < max && (
        <button
          type="button"
          onClick={() => onChange([...items, ""])}
          className="inline-flex min-h-11 items-center text-[0.875rem] text-primary underline-offset-4 hover:underline text-left w-fit"
        >
          {addLabel}
        </button>
      )}
    </div>
  );
}

// ── Initials helper ───────────────────────────────────────────────────────────
function getInitials(name: string): string {
  const parts = name.trim().split(/\s+/);
  if (parts.length === 0 || !parts[0]) return "?";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function ProfileSettingsPage() {
  const api = useApi();
  const { showToast } = useToast();

  const [form, setForm] = useState<SettingsForm | null>(null);
  const [loaded, setLoaded] = useState<SettingsForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);
  const [loadFailed, setLoadFailed] = useState(false);
  // Bumped by "Try again" to load the profile again.
  const [reloadKey, setReloadKey] = useState(0);

  // ── Dirty tracking ────────────────────────────────────────────────────────
  const isDirty =
    form !== null &&
    loaded !== null &&
    JSON.stringify(form) !== JSON.stringify(loaded);

  // ── beforeunload guard ────────────────────────────────────────────────────
  useEffect(() => {
    const handler = (e: BeforeUnloadEvent) => {
      if (isDirty) e.preventDefault();
    };
    window.addEventListener("beforeunload", handler);
    return () => window.removeEventListener("beforeunload", handler);
  }, [isDirty]);

  // ── Load profile on mount ─────────────────────────────────────────────────
  useEffect(() => {
    async function load() {
      setLoadFailed(false);
      try {
        const res = await api.getProfile();
        if (!res.ok) throw new Error("Failed");
        const data = await res.json();
        const p = data.profile ?? {};

        const initial: SettingsForm = {
          name: p.name ?? "",
          role: p.role ?? "",
          bio: p.bio ?? "",
          location: p.location ?? "",
          target_audience: p.target_audience ?? "",
          topics_of_expertise: p.topics_of_expertise ?? [],
          voice_descriptors: p.voice_descriptors ?? [],
          words_to_avoid: p.words_to_avoid ?? [],
          writing_rules:
            (p.writing_rules ?? []).length > 0 ? p.writing_rules : [""],
          opinions: (p.opinions ?? []).length > 0 ? p.opinions : [""],
          writing_samples:
            (p.writing_samples ?? []).length > 0 ? p.writing_samples : [""],
          technical_voice_notes: Array.isArray(p.technical_voice_notes)
            ? p.technical_voice_notes.join("\n")
            : p.technical_voice_notes ?? "",
          linkedin_style_notes: p.linkedin_style_notes ?? "",
          medium_style_notes: p.medium_style_notes ?? "",
          thread_style_notes: p.thread_style_notes ?? "",
          projects: p.projects ?? [],
        };

        setForm(initial);
        setLoaded(structuredClone(initial));
      } catch {
        setLoadFailed(true);
      }
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [reloadKey]);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const set = useCallback(
    <K extends keyof SettingsForm>(key: K, value: SettingsForm[K]) => {
      setForm((prev) => (prev ? { ...prev, [key]: value } : prev));
    },
    []
  );

  // ── Save ──────────────────────────────────────────────────────────────────
  async function handleSave() {
    if (!form) return;
    setSaving(true);
    try {
      const payload = {
        ...form,
        technical_voice_notes: form.technical_voice_notes
          .split("\n")
          .map((s) => s.trim())
          .filter(Boolean),
        writing_rules: form.writing_rules.filter(Boolean),
        opinions: form.opinions.filter(Boolean),
        writing_samples: form.writing_samples.filter(Boolean),
        projects: loaded?.projects ?? [],
      };
      const res = await api.saveProfile(payload);
      if (res.ok) {
        setLoaded(structuredClone(form));
        showToast("Profile updated", "success");
      } else {
        showToast("We couldn't save your profile. Please try again.", "error");
      }
    } catch {
      showToast("We couldn't save your profile. Please try again.", "error");
    }
    setSaving(false);
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto pb-32">

      {/* Back link */}
      <div className="mb-6">
        <Link
          href="/settings"
          className="inline-flex min-h-11 items-center gap-1.5 text-[0.875rem] text-secondary hover:text-on-surface transition-colors"
        >
          <svg width="14" height="14" viewBox="0 0 14 14" fill="none" aria-hidden="true">
            <path
              d="M9 11L5 7l4-4"
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </svg>
          Settings
        </Link>
      </div>

      {/* Page header */}
      <p className="label-caps text-secondary mb-2">PROFILE</p>
      <h1 className="font-headline text-[32px] text-on-surface mb-2">Edit profile</h1>
      <p className="text-[14px] text-secondary mb-8">
        Your voice profile. Everything here shapes how Contendo writes for you.
      </p>

      {/* Profile summary header card */}
      {form ? (
        <div className="bg-surface-container-low rounded-2xl p-6 mb-8 flex items-start gap-4">
          <div className="w-16 h-16 rounded-full bg-primary/10 flex items-center justify-center shrink-0">
            <span className="text-primary font-medium text-[18px]">
              {form.name ? getInitials(form.name) : "..."}
            </span>
          </div>
          <div className="flex flex-col gap-1 min-w-0">
            <span className="font-medium text-on-surface text-[18px] leading-snug truncate">
              {form.name || "Your name"}
            </span>
            <span className="text-secondary text-[13px]">
              {form.role || "Your role"}
            </span>
            {form.location && (
              <span className="text-on-surface-variant text-[12px]">{form.location}</span>
            )}
            <p className="text-[12px] text-secondary mt-1 leading-relaxed">
              Your voice profile shapes every post Contendo writes for you.
            </p>
          </div>
        </div>
      ) : (
        <div className="bg-surface-container-low rounded-2xl p-6 mb-8 flex items-center gap-4">
          <div className="w-16 h-16 rounded-full bg-surface-container animate-pulse shrink-0" />
          <div className="flex flex-col gap-2 flex-1">
            <div className="bg-surface-container animate-pulse rounded h-4 w-1/2" />
            <div className="bg-surface-container animate-pulse rounded h-3 w-1/3" />
          </div>
        </div>
      )}

      {/* Sticky section nav */}
      <div className="sticky top-0 z-10 bg-background/90 backdrop-blur-sm py-3 mb-8 border-b border-outline-variant/20 -mx-6 px-6">
        <div className="flex items-center gap-1 overflow-x-auto no-scrollbar">
          {[
            { id: "identity", label: "Identity" },
            { id: "audience", label: "Audience" },
            { id: "voice", label: "Voice" },
            { id: "opinions", label: "Opinions" },
            { id: "samples", label: "Samples" },
            { id: "advanced", label: "Advanced" },
          ].map(({ id, label }) => (
            <a
              key={id}
              href={`#${id}`}
              className="inline-flex min-h-11 items-center px-3 rounded-lg text-[0.75rem] uppercase tracking-wide whitespace-nowrap text-secondary hover:text-on-surface hover:bg-surface-container transition-colors shrink-0"
            >
              {label}
            </a>
          ))}
        </div>
      </div>

      {!form && loadFailed && (
        <ErrorState message="We couldn't load your profile. Check your connection and try again." onRetry={() => setReloadKey((k) => k + 1)} />
      )}
      {!form && !loadFailed && <LoadingSkeleton />}

      {/* Form sections */}
      {form && (
        <div className="flex flex-col gap-8">

          {/* ── Section 1: Identity ───────────────────────────────────────── */}
          <div
            id="identity"
            style={{ scrollMarginTop: "72px" }}
            className="bg-surface-container-low rounded-2xl p-6 flex flex-col gap-5"
          >
            <p className="label-caps text-secondary">About you</p>
            <Field label="Full name">
              <input
                className={inputCls}
                placeholder="Alex Chen"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
              />
            </Field>
            <Field label="Role / title">
              <input
                className={inputCls}
                placeholder="e.g. ML Engineer, Founder, Product Manager"
                value={form.role}
                onChange={(e) => set("role", e.target.value)}
              />
            </Field>
            <Field label="Bio">
              <textarea
                className={inputCls}
                rows={4}
                placeholder="2–3 sentences. What do you do, and what do you stand for?"
                value={form.bio}
                onChange={(e) => set("bio", e.target.value)}
              />
            </Field>
            <Field label="Location" optional>
              <input
                className={inputCls}
                placeholder="e.g. Mumbai, India"
                value={form.location}
                onChange={(e) => set("location", e.target.value)}
              />
            </Field>
          </div>

          {/* ── Section 2: Audience ───────────────────────────────────────── */}
          <div
            id="audience"
            style={{ scrollMarginTop: "72px" }}
            className="bg-surface-container-low rounded-2xl p-6 flex flex-col gap-5"
          >
            <p className="label-caps text-secondary">Expertise</p>
            <Field label="Topics of expertise">
              <TagInput
                value={form.topics_of_expertise}
                onChange={(v) => set("topics_of_expertise", v)}
                placeholder="e.g. machine learning, product strategy"
                hint="Add 3–8 topics. These become the lens for your content."
              />
            </Field>
            <Field label="Target audience">
              <input
                className={inputCls}
                placeholder="Who reads your content? e.g. early-stage founders, ML engineers"
                value={form.target_audience}
                onChange={(e) => set("target_audience", e.target.value)}
              />
            </Field>
          </div>

          {/* ── Section 3: Voice ─────────────────────────────────────────── */}
          <div
            id="voice"
            style={{ scrollMarginTop: "72px" }}
            className="bg-surface-container-low rounded-2xl p-6 flex flex-col gap-5"
          >
            <p className="label-caps text-secondary">How you write</p>
            <Field label="Phrases you use">
              <TagInput
                value={form.voice_descriptors}
                onChange={(v) => set("voice_descriptors", v)}
                placeholder="e.g. to be honest, let me be direct, here's the thing"
                hint="Phrases that sound like you. Add 3–6."
              />
            </Field>
            <Field label="Words to avoid">
              <TagInput
                value={form.words_to_avoid}
                onChange={(v) => set("words_to_avoid", v)}
                placeholder="e.g. leverage, synergy, game-changing, transformative"
                hint="Words that make you cringe. These get actively avoided."
              />
            </Field>
            <Field label="Writing rules">
              <DynamicList
                items={form.writing_rules}
                onChange={(v) => set("writing_rules", v)}
                max={5}
                addLabel="+ Add rule"
                renderItem={(value, i, onItemChange) => (
                  <div key={i} className="flex flex-col gap-1">
                    <label htmlFor={`rule-${i}`} className="text-[0.75rem] text-on-surface-variant uppercase tracking-wide">Rule {i + 1}</label>
                    <input
                      id={`rule-${i}`}
                      className={inputCls}
                      placeholder={
                        i === 0
                          ? "e.g. Never use passive voice"
                          : i === 1
                          ? "e.g. Always open with a specific story"
                          : "e.g. No bullet points in LinkedIn posts"
                      }
                      value={value}
                      onChange={(e) => onItemChange(e.target.value)}
                    />
                  </div>
                )}
              />
            </Field>
          </div>

          {/* ── Section 4: Opinions ───────────────────────────────────────── */}
          <div
            id="opinions"
            style={{ scrollMarginTop: "72px" }}
            className="bg-surface-container-low rounded-2xl p-6 flex flex-col gap-5"
          >
            <p className="label-caps text-secondary">Your opinions</p>
            <DynamicList
              items={form.opinions}
              onChange={(v) => set("opinions", v)}
              max={5}
              addLabel="+ Add opinion"
              renderItem={(value, i, onItemChange) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <label htmlFor={`opinion-${i}`} className="text-[0.75rem] text-on-surface-variant uppercase tracking-wide">Opinion {i + 1}</label>
                  <textarea
                    id={`opinion-${i}`}
                    className={inputCls}
                    rows={2}
                    placeholder="A take you'd defend publicly. Be specific: not 'marketing matters' but 'most open houses fail because they're scheduled for the agent, not the buyer'"
                    value={value}
                    onChange={(e) => onItemChange(e.target.value)}
                  />
                </div>
              )}
            />
            <p className="text-[11px] text-on-surface-variant">
              The more specific, the better. Vague opinions produce generic posts.
            </p>
          </div>

          {/* ── Section 5: Samples ────────────────────────────────────────── */}
          <div
            id="samples"
            style={{ scrollMarginTop: "72px" }}
            className="bg-surface-container-low rounded-2xl p-6 flex flex-col gap-5"
          >
            <p className="label-caps text-secondary">Writing samples</p>
            <DynamicList
              items={form.writing_samples}
              onChange={(v) => set("writing_samples", v)}
              max={5}
              addLabel="+ Add sample"
              renderItem={(value, i, onItemChange) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <label htmlFor={`sample-${i}`} className="label-caps text-secondary">Sample {i + 1}</label>
                  <textarea
                    id={`sample-${i}`}
                    className={inputCls}
                    rows={i === 0 ? 8 : 6}
                    placeholder={
                      i === 0
                        ? "Paste a real LinkedIn post, article paragraph, or anything you've actually published"
                        : "Another writing sample (optional)…"
                    }
                    value={value}
                    onChange={(e) => onItemChange(e.target.value)}
                  />
                </div>
              )}
            />
            <p className="text-[11px] text-on-surface-variant">
              These are never shared. They teach Contendo your exact rhythm and word choices.
            </p>
          </div>

          {/* ── Section 6: Advanced (collapsed) ─────────────────────────── */}
          <div
            id="advanced"
            style={{ scrollMarginTop: "72px" }}
            className="bg-surface-container-low rounded-2xl p-6 flex flex-col gap-5"
          >
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              aria-expanded={advancedOpen}
              className="flex min-h-11 items-center gap-2 label-caps text-secondary hover:text-on-surface transition-colors w-fit"
            >
              Advanced
              <svg
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                style={{
                  transform: advancedOpen ? "rotate(180deg)" : "rotate(0deg)",
                  transition: "transform 0.2s",
                }}
              >
                <path
                  d="M2 4l4 4 4-4"
                  stroke="currentColor"
                  strokeWidth="1.5"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
            </button>

            {advancedOpen && (
              <div className="flex flex-col gap-5">
                <Field label="How you explain technical concepts">
                  <textarea
                    className={inputCls}
                    rows={4}
                    placeholder="e.g. I use analogies before definitions. I always give a real example before the abstraction."
                    value={form.technical_voice_notes}
                    onChange={(e) => set("technical_voice_notes", e.target.value)}
                  />
                  <p className="text-[11px] text-on-surface-variant">Each line becomes a separate note.</p>
                </Field>
                <Field label="LinkedIn style notes">
                  <textarea
                    className={inputCls}
                    rows={3}
                    placeholder="e.g. Hook in the first line. End with a takeaway, not a CTA."
                    value={form.linkedin_style_notes}
                    onChange={(e) => set("linkedin_style_notes", e.target.value)}
                  />
                </Field>
                <Field label="Medium style notes">
                  <textarea
                    className={inputCls}
                    rows={3}
                    placeholder="e.g. Start in the middle of the story. Technical depth is welcome."
                    value={form.medium_style_notes}
                    onChange={(e) => set("medium_style_notes", e.target.value)}
                  />
                </Field>
                <Field label="Thread style notes">
                  <textarea
                    className={inputCls}
                    rows={3}
                    placeholder="e.g. Each tweet stands alone. Number tweets. Last tweet is the payoff."
                    value={form.thread_style_notes}
                    onChange={(e) => set("thread_style_notes", e.target.value)}
                  />
                </Field>
              </div>
            )}
          </div>

        </div>
      )}

      {/* ── Sticky save button ──────────────────────────────────────────────── */}
      {form && (
        <div className="fixed bottom-0 right-0 p-4 sm:p-6 z-40">
          <Button size="lg" className="shadow-float" onClick={handleSave} loading={saving} disabled={!isDirty} disabledReason="No changes to save">
            Save changes
          </Button>
        </div>
      )}
    </div>
  );
}
