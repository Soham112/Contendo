"use client";

import { useState, useEffect, useCallback } from "react";
import { useApi } from "@/lib/api";
import { useToast } from "@/components/ui/ToastProvider";
import TagInput from "@/components/ui/TagInput";

// ── Shared input class ────────────────────────────────────────────────────────
const inputCls =
  "w-full bg-[#f3f4f3] border-0 border-b border-b-[#aeb3b2] focus:border-b-2 focus:border-b-[#58614f] outline-none px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2] transition-all resize-none";

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

// ── Section wrapper ───────────────────────────────────────────────────────────
function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-5">
      <p className="label-caps text-[#645e57]">{title}</p>
      {children}
    </div>
  );
}

// ── Field wrapper ─────────────────────────────────────────────────────────────
function Field({ label, optional, children }: { label: string; optional?: boolean; children: React.ReactNode }) {
  return (
    <div className="flex flex-col gap-1.5">
      <label className="label-caps text-[#645e57]">
        {label}
        {optional && (
          <span className="normal-case tracking-normal font-normal text-[#aeb3b2] ml-1">(optional)</span>
        )}
      </label>
      {children}
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
  renderItem: (value: string, index: number, onItemChange: (v: string) => void) => React.ReactNode;
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
          className="text-[13px] text-[#58614f] hover:underline text-left w-fit"
        >
          {addLabel}
        </button>
      )}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────
export default function SettingsPage() {
  const api = useApi();
  const { showToast } = useToast();

  const [form, setForm] = useState<SettingsForm | null>(null);
  const [loaded, setLoaded] = useState<SettingsForm | null>(null);
  const [saving, setSaving] = useState(false);
  const [advancedOpen, setAdvancedOpen] = useState(false);

  // ── Dirty tracking ────────────────────────────────────────────────────────
  const isDirty =
    form !== null && loaded !== null && JSON.stringify(form) !== JSON.stringify(loaded);

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
      try {
        const res = await api.getProfile();
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
          writing_rules: (p.writing_rules ?? []).length > 0 ? p.writing_rules : [""],
          opinions: (p.opinions ?? []).length > 0 ? p.opinions : [""],
          writing_samples: (p.writing_samples ?? []).length > 0 ? p.writing_samples : [""],
          technical_voice_notes: Array.isArray(p.technical_voice_notes)
            ? p.technical_voice_notes.join("\n")
            : (p.technical_voice_notes ?? ""),
          linkedin_style_notes: p.linkedin_style_notes ?? "",
          medium_style_notes: p.medium_style_notes ?? "",
          thread_style_notes: p.thread_style_notes ?? "",
          projects: p.projects ?? [],
        };

        setForm(initial);
        setLoaded(structuredClone(initial));
      } catch {
        showToast("Failed to load profile", "error");
        const fallback = emptyForm();
        setForm(fallback);
        setLoaded(structuredClone(fallback));
      }
    }
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // ── Helpers ───────────────────────────────────────────────────────────────
  const set = useCallback(<K extends keyof SettingsForm>(key: K, value: SettingsForm[K]) => {
    setForm((prev) => prev ? { ...prev, [key]: value } : prev);
  }, []);

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
        showToast("Failed to save profile", "error");
      }
    } catch {
      showToast("Failed to save profile", "error");
    }
    setSaving(false);
  }

  // ── Render ────────────────────────────────────────────────────────────────
  return (
    <div className="max-w-2xl mx-auto px-6 py-10 pb-32">
      {/* Page header */}
      <p className="label-caps text-[#645e57] mb-2">YOUR WORKSPACE</p>
      <h1 className="font-headline text-[32px] text-[#2f3333] mb-2">Profile Settings</h1>
      <p className="text-[14px] text-[#645e57] mb-10">
        Your voice profile. Everything here shapes how Contendo writes for you.
      </p>

      {/* Loading skeleton */}
      {!form && <LoadingSkeleton />}

      {/* Form sections */}
      {form && (
        <div className="flex flex-col gap-12">

          {/* ── Section 1: About you ──────────────────────────────────────── */}
          <Section title="About you">
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
          </Section>

          {/* ── Section 2: Expertise ─────────────────────────────────────── */}
          <Section title="Expertise">
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
          </Section>

          {/* ── Section 3: Writing fingerprint ───────────────────────────── */}
          <Section title="Writing fingerprint">
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
                    <span className="text-[11px] text-[#aeb3b2] uppercase tracking-wide">Rule {i + 1}</span>
                    <input
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
          </Section>

          {/* ── Section 4: Your opinions ─────────────────────────────────── */}
          <Section title="Your opinions">
            <DynamicList
              items={form.opinions}
              onChange={(v) => set("opinions", v)}
              max={5}
              addLabel="+ Add opinion"
              renderItem={(value, i, onItemChange) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <span className="text-[11px] text-[#aeb3b2] uppercase tracking-wide">Opinion {i + 1}</span>
                  <textarea
                    className={inputCls}
                    rows={2}
                    placeholder="A take you'd defend publicly. Be specific — not 'AI is important' but 'most AI demos fail because founders optimize for wow moments, not retention'"
                    value={value}
                    onChange={(e) => onItemChange(e.target.value)}
                  />
                </div>
              )}
            />
            <p className="text-[11px] text-[#aeb3b2]">
              The more specific, the better. Vague opinions produce generic posts.
            </p>
          </Section>

          {/* ── Section 5: Writing samples ───────────────────────────────── */}
          <Section title="Writing samples">
            <DynamicList
              items={form.writing_samples}
              onChange={(v) => set("writing_samples", v)}
              max={5}
              addLabel="+ Add sample"
              renderItem={(value, i, onItemChange) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <label className="label-caps text-[#645e57]">Sample {i + 1}</label>
                  <textarea
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
            <p className="text-[11px] text-[#aeb3b2]">
              These are never shared. They teach Contendo your exact rhythm and word choices.
            </p>
          </Section>

          {/* ── Section 6: Advanced (collapsed) ─────────────────────────── */}
          <div>
            <button
              type="button"
              onClick={() => setAdvancedOpen((v) => !v)}
              className="flex items-center gap-2 label-caps text-[#645e57] hover:text-[#2f3333] transition-colors"
            >
              Advanced
              <svg
                width="12"
                height="12"
                viewBox="0 0 12 12"
                fill="none"
                style={{ transform: advancedOpen ? "rotate(180deg)" : "rotate(0deg)", transition: "transform 0.2s" }}
              >
                <path d="M2 4l4 4 4-4" stroke="currentColor" strokeWidth="1.5" strokeLinecap="round" strokeLinejoin="round"/>
              </svg>
            </button>

            {advancedOpen && (
              <div className="flex flex-col gap-5 mt-6">
                <Field label="How you explain technical concepts">
                  <textarea
                    className={inputCls}
                    rows={4}
                    placeholder="e.g. I use analogies before definitions. I always give a real example before the abstraction."
                    value={form.technical_voice_notes}
                    onChange={(e) => set("technical_voice_notes", e.target.value)}
                  />
                  <p className="text-[11px] text-[#aeb3b2]">Each line becomes a separate note.</p>
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
        <div className="fixed bottom-0 right-0 p-6 z-40">
          <button
            type="button"
            onClick={handleSave}
            disabled={saving || !isDirty}
            className="btn-primary flex items-center gap-2 px-5 py-2.5 rounded-xl text-[14px] font-medium text-white disabled:opacity-40 disabled:cursor-not-allowed shadow-float transition-opacity"
          >
            {isDirty && <span className="w-2 h-2 rounded-full bg-amber-400 shrink-0" />}
            {saving ? (
              <>
                <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                Saving…
              </>
            ) : (
              "Save changes"
            )}
          </button>
        </div>
      )}
    </div>
  );
}
