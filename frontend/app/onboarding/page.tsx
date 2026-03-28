"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";

// ── Tag pill input ──────────────────────────────────────────────────────────
function TagInput({
  value,
  onChange,
  placeholder,
}: {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
}) {
  const [input, setInput] = useState("");

  function addTag(raw: string) {
    const tag = raw.trim();
    if (tag && !value.includes(tag)) onChange([...value, tag]);
    setInput("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Backspace" && input === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="flex flex-wrap gap-2 bg-[#f3f4f3] rounded-xl px-3 py-2.5 focus-within:ring-2 focus-within:ring-[#58614f]/40">
      {value.map((tag) => (
        <span
          key={tag}
          className="inline-flex items-center gap-1 bg-white text-[#2f3333] text-[13px] px-2.5 py-1 rounded-full shadow-sm"
        >
          {tag}
          <button
            type="button"
            onClick={() => onChange(value.filter((t) => t !== tag))}
            className="text-[#645e57] hover:text-[#2f3333] leading-none"
          >
            ×
          </button>
        </span>
      ))}
      <input
        value={input}
        onChange={(e) => setInput(e.target.value)}
        onKeyDown={onKeyDown}
        onBlur={() => input && addTag(input)}
        placeholder={value.length === 0 ? placeholder : ""}
        className="flex-1 min-w-[120px] bg-transparent outline-none text-[14px] text-[#2f3333] placeholder-[#aeb3b2]"
      />
    </div>
  );
}

// ── Shared input styles ─────────────────────────────────────────────────────
const inputCls =
  "w-full bg-[#f3f4f3] rounded-xl px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2] outline-none focus:ring-2 focus:ring-[#58614f]/40 resize-none";

// ── Step indicator ──────────────────────────────────────────────────────────
function StepDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center gap-2 justify-center mb-8">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`w-2 h-2 rounded-full transition-all ${
            i <= current
              ? "bg-[#58614f]"
              : "border border-[#58614f] opacity-30"
          }`}
        />
      ))}
    </div>
  );
}

// ── Form state ───────────────────────────────────────────────────────────────
interface FormState {
  name: string;
  role: string;
  bio: string;
  location: string;
  topics_of_expertise: string[];
  target_audience: string;
  voice_descriptors: string[];
  words_to_avoid: string[];
  writing_rules: [string, string, string];
  opinions: [string, string, string];
  writing_samples: [string, string, string];
}

const EMPTY: FormState = {
  name: "",
  role: "",
  bio: "",
  location: "",
  topics_of_expertise: [],
  target_audience: "",
  voice_descriptors: [],
  words_to_avoid: [],
  writing_rules: ["", "", ""],
  opinions: ["", "", ""],
  writing_samples: ["", "", ""],
};

const TOTAL_STEPS = 5;

export default function OnboardingPage() {
  const router = useRouter();
  const api = useApi();
  const [step, setStep] = useState(0);
  const [form, setForm] = useState<FormState>(EMPTY);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState("");

  function set<K extends keyof FormState>(key: K, value: FormState[K]) {
    setForm((prev) => ({ ...prev, [key]: value }));
  }

  function setTriple<K extends "writing_rules" | "opinions" | "writing_samples">(
    key: K,
    idx: number,
    value: string
  ) {
    setForm((prev) => {
      const arr = [...prev[key]] as [string, string, string];
      arr[idx] = value;
      return { ...prev, [key]: arr };
    });
  }

  function canAdvance(): boolean {
    if (step === 0) return !!form.name.trim() && !!form.role.trim() && !!form.bio.trim();
    if (step === 1) return form.topics_of_expertise.length > 0;
    return true;
  }

  async function handleFinish() {
    setSaving(true);
    setError("");
    try {
      const payload = {
        ...form,
        writing_rules: form.writing_rules.filter(Boolean),
        opinions: form.opinions.filter(Boolean),
        writing_samples: form.writing_samples.filter(Boolean),
      };
      const res = await api.saveProfile(payload);
      if (!res.ok) throw new Error("Save failed");
      router.push("/");
    } catch {
      setError("Something went wrong. Please try again.");
      setSaving(false);
    }
  }

  // ── Completion screen ────────────────────────────────────────────────────
  if (saving) {
    return (
      <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center gap-4">
        <div className="w-8 h-8 border-2 border-[#58614f]/30 border-t-[#58614f] rounded-full animate-spin" />
        <p className="text-[14px] text-[#645e57]">Building your profile…</p>
      </div>
    );
  }

  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      {/* Wordmark */}
      <div className="flex flex-col items-center gap-1 mb-10">
        <span className="text-[28px] font-headline italic text-[#2f3333]">Contendo</span>
        <span className="text-[10px] uppercase tracking-[0.14em] text-[#645e57]">Editorial Atelier</span>
      </div>

      {/* Card */}
      <div className="w-full max-w-[580px] bg-white rounded-2xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] px-8 py-10">
        <StepDots total={TOTAL_STEPS} current={step} />

        {/* ── Step 0: Who are you? ─────────────────────────────────────── */}
        {step === 0 && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="font-headline text-[22px] text-[#2f3333] mb-1">Who are you?</h2>
              <p className="text-[13px] text-[#645e57]">The basics — this shapes every post we write for you.</p>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Full name</label>
              <input
                className={inputCls}
                placeholder="Alex Chen"
                value={form.name}
                onChange={(e) => set("name", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Current role / title</label>
              <input
                className={inputCls}
                placeholder="Staff Engineer at Stripe"
                value={form.role}
                onChange={(e) => set("role", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Short bio</label>
              <textarea
                className={inputCls}
                rows={3}
                placeholder="2–3 sentences about who you are and what you believe."
                value={form.bio}
                onChange={(e) => set("bio", e.target.value)}
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">
                Location <span className="normal-case tracking-normal text-[#aeb3b2]">(optional)</span>
              </label>
              <input
                className={inputCls}
                placeholder="San Francisco, CA"
                value={form.location}
                onChange={(e) => set("location", e.target.value)}
              />
            </div>
          </div>
        )}

        {/* ── Step 1: What do you know deeply? ────────────────────────── */}
        {step === 1 && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="font-headline text-[22px] text-[#2f3333] mb-1">What do you know deeply?</h2>
              <p className="text-[13px] text-[#645e57]">Your expertise shapes what ideas we surface for you.</p>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Topics of expertise</label>
              <p className="text-[12px] text-[#aeb3b2] mb-1">Type a topic and press Enter to add it.</p>
              <TagInput
                value={form.topics_of_expertise}
                onChange={(v) => set("topics_of_expertise", v)}
                placeholder="e.g. distributed systems, ML infrastructure…"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Target audience</label>
              <input
                className={inputCls}
                placeholder="e.g. Senior engineers considering staff roles"
                value={form.target_audience}
                onChange={(e) => set("target_audience", e.target.value)}
              />
            </div>
          </div>
        )}

        {/* ── Step 2: How do you write? ────────────────────────────────── */}
        {step === 2 && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="font-headline text-[22px] text-[#2f3333] mb-1">How do you write?</h2>
              <p className="text-[13px] text-[#645e57]">Voice, tone, and the rules you never break.</p>
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Phrases you naturally use</label>
              <p className="text-[12px] text-[#aeb3b2] mb-1">Type and press Enter.</p>
              <TagInput
                value={form.voice_descriptors}
                onChange={(v) => set("voice_descriptors", v)}
                placeholder="e.g. in practice, the real question is…"
              />
            </div>
            <div className="flex flex-col gap-1">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Words you never use</label>
              <TagInput
                value={form.words_to_avoid}
                onChange={(v) => set("words_to_avoid", v)}
                placeholder="e.g. leverage, synergy, game-changer…"
              />
            </div>
            <div className="flex flex-col gap-3">
              <label className="text-[12px] uppercase tracking-[0.07em] text-[#645e57]">Your 3 writing rules</label>
              {([0, 1, 2] as const).map((i) => (
                <div key={i} className="flex flex-col gap-1">
                  <span className="text-[12px] text-[#aeb3b2]">Rule {i + 1}</span>
                  <input
                    className={inputCls}
                    placeholder={
                      i === 0
                        ? "e.g. Never bury the lede — say the thing first"
                        : i === 1
                        ? "e.g. One idea per paragraph, always"
                        : "e.g. End with a question, not a conclusion"
                    }
                    value={form.writing_rules[i]}
                    onChange={(e) => setTriple("writing_rules", i, e.target.value)}
                  />
                </div>
              ))}
            </div>
          </div>
        )}

        {/* ── Step 3: What do you actually believe? ───────────────────── */}
        {step === 3 && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="font-headline text-[22px] text-[#2f3333] mb-1">What do you actually believe?</h2>
              <p className="text-[13px] text-[#645e57]">Strong opinions make great posts. Give us three you'd defend.</p>
            </div>
            {([0, 1, 2] as const).map((i) => (
              <div key={i} className="flex flex-col gap-1">
                <label className="text-[12px] text-[#aeb3b2]">Opinion {i + 1}</label>
                <textarea
                  className={inputCls}
                  rows={2}
                  placeholder="A take you'd defend in public"
                  value={form.opinions[i]}
                  onChange={(e) => setTriple("opinions", i, e.target.value)}
                />
              </div>
            ))}
          </div>
        )}

        {/* ── Step 4: Show me how you write ───────────────────────────── */}
        {step === 4 && (
          <div className="flex flex-col gap-5">
            <div>
              <h2 className="font-headline text-[22px] text-[#2f3333] mb-1">Show me how you write</h2>
              <p className="text-[13px] text-[#645e57]">
                Paste real posts or pieces you've written. These are the most powerful signal for voice matching.
              </p>
            </div>
            {([0, 1, 2] as const).map((i) => (
              <div key={i} className="flex flex-col gap-1">
                <label className="text-[12px] text-[#aeb3b2]">
                  Sample {i + 1}{i > 0 && <span className="ml-1 text-[#aeb3b2]/70">(optional)</span>}
                </label>
                <textarea
                  className={inputCls}
                  rows={5}
                  placeholder={i === 0 ? "Paste a real post or piece you've written…" : "Another writing sample (optional)…"}
                  value={form.writing_samples[i]}
                  onChange={(e) => setTriple("writing_samples", i, e.target.value)}
                />
              </div>
            ))}
            <p className="text-[12px] text-[#aeb3b2]">
              The more real samples you add, the better we can match your voice.
            </p>
            {error && <p className="text-[13px] text-red-500">{error}</p>}
          </div>
        )}

        {/* ── Navigation ──────────────────────────────────────────────── */}
        <div className={`flex gap-3 mt-8 ${step === 0 ? "justify-end" : "justify-between"}`}>
          {step > 0 && (
            <button
              onClick={() => setStep((s) => s - 1)}
              className="flex-1 py-2.5 rounded-xl text-[14px] text-[#645e57] hover:bg-[#f3f4f3] transition-colors"
            >
              Back
            </button>
          )}
          {step < TOTAL_STEPS - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={!canAdvance()}
              className="flex-1 btn-primary py-2.5 rounded-xl text-[14px] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={!form.writing_samples[0].trim()}
              className="flex-1 btn-primary py-2.5 rounded-xl text-[14px] disabled:opacity-40 disabled:cursor-not-allowed"
            >
              Finish
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
