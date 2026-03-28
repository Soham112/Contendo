"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { useApi } from "@/lib/api";
import TagInput from "@/components/ui/TagInput";

// ── Shared label component ───────────────────────────────────────────────────
function FieldLabel({ children }: { children: React.ReactNode }) {
  return (
    <label className="label-caps text-[#645e57]">{children}</label>
  );
}

// ── Step indicator ───────────────────────────────────────────────────────────
function StepDots({ total, current }: { total: number; current: number }) {
  return (
    <div className="flex items-center gap-2 justify-center mb-8">
      {Array.from({ length: total }).map((_, i) => (
        <div
          key={i}
          className={`w-2 h-2 rounded-full transition-all duration-200 ${
            i <= current
              ? "bg-[#58614f]"
              : "border border-[#58614f] opacity-30"
          }`}
        />
      ))}
    </div>
  );
}

// ── Shared input class (matches .input-editorial but works with Tailwind) ────
const inputCls =
  "w-full bg-[#f3f4f3] border-0 border-b border-b-[#aeb3b2] focus:border-b-2 focus:border-b-[#58614f] outline-none px-3 py-2.5 text-[14px] text-[#2f3333] placeholder-[#aeb3b2] transition-all resize-none";

// ── Optional step hint ───────────────────────────────────────────────────────
function OptionalHint() {
  return (
    <p className="text-[11px] text-[#aeb3b2] text-center mt-1">
      You can always update this later.
    </p>
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
  phrases_i_use: string[];
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
  phrases_i_use: [],
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
    if (step === 0) return !!form.name.trim() && !!form.role.trim();
    return true; // steps 1–4 are always optional
  }

  async function handleFinish() {
    setSaving(true);
    setError("");
    try {
      const payload = {
        name: form.name,
        role: form.role,
        bio: form.bio,
        location: form.location,
        target_audience: form.target_audience,
        topics_of_expertise: form.topics_of_expertise,
        voice_descriptors: form.phrases_i_use, // mapped to backend field name
        words_to_avoid: form.words_to_avoid,
        writing_rules: form.writing_rules.filter(Boolean),
        opinions: form.opinions.filter(Boolean),
        writing_samples: form.writing_samples.filter(Boolean),
        // backend defaults — sent as empty so auto-merge doesn't overwrite
        projects: [],
        technical_voice_notes: [],
        linkedin_style_notes: "",
        medium_style_notes: "",
        thread_style_notes: "",
      };
      console.log("[onboarding] sending profile payload:", payload);
      // saveProfile now throws on non-2xx, so no need to check res.ok separately
      const res = await api.saveProfile(payload);
      const data = await res.json();
      console.log("[onboarding] save response:", data);
      if (!data.saved) {
        throw new Error("Backend reported saved: false");
      }
      router.push("/");
    } catch (err) {
      console.error("[onboarding] handleFinish error:", err);
      setError("Something went wrong saving your profile. Please try again.");
      setSaving(false);
    }
  }

  return (
    <div className="min-h-screen bg-[#faf9f8] flex flex-col items-center justify-center px-4 py-12">
      {/* Wordmark */}
      <div className="flex flex-col items-center gap-1 mb-10">
        <span className="text-[28px] font-headline italic text-[#2f3333]">Contendo</span>
        <span className="text-[10px] uppercase tracking-[0.14em] text-[#645e57]">Editorial Atelier</span>
      </div>

      {/* Card */}
      <div className="w-full max-w-[600px] bg-white rounded-2xl shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] px-8 py-10">
        <StepDots total={TOTAL_STEPS} current={step} />

        {/* ── Animated step content ────────────────────────────────────────── */}
        <div key={step} className="step-animate flex flex-col gap-6">

          {/* ── Step 0 ──────────────────────────────────────────────────────── */}
          {step === 0 && (
            <>
              <div>
                <h2 className="font-headline text-[24px] text-[#2f3333] mb-2">
                  Let's build your voice.
                </h2>
                <p className="text-[13px] text-[#645e57] leading-relaxed">
                  Contendo writes in your voice. The more specific you are, the better it sounds like you.
                </p>
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Full name</FieldLabel>
                <input
                  className={inputCls}
                  placeholder="Alex Chen"
                  value={form.name}
                  onChange={(e) => set("name", e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Current role or title</FieldLabel>
                <input
                  className={inputCls}
                  placeholder="e.g. ML Engineer, Founder, Product Manager"
                  value={form.role}
                  onChange={(e) => set("role", e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Who you are and what you believe</FieldLabel>
                <textarea
                  className={inputCls}
                  rows={3}
                  placeholder="2–3 sentences. What do you do, and what do you stand for?"
                  value={form.bio}
                  onChange={(e) => set("bio", e.target.value)}
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>
                  Location{" "}
                  <span className="normal-case tracking-normal font-normal text-[#aeb3b2]">
                    (optional)
                  </span>
                </FieldLabel>
                <input
                  className={inputCls}
                  placeholder="e.g. Mumbai, India"
                  value={form.location}
                  onChange={(e) => set("location", e.target.value)}
                />
              </div>
            </>
          )}

          {/* ── Step 1 ──────────────────────────────────────────────────────── */}
          {step === 1 && (
            <>
              <div>
                <h2 className="font-headline text-[24px] text-[#2f3333] mb-2">
                  Your expertise.
                </h2>
                <p className="text-[13px] text-[#645e57] leading-relaxed">
                  These shape which ideas get surfaced and how posts are framed.
                </p>
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Topics of expertise</FieldLabel>
                <TagInput
                  value={form.topics_of_expertise}
                  onChange={(v) => set("topics_of_expertise", v)}
                  placeholder="e.g. machine learning, product strategy"
                  hint="Add 3–8 topics. These become the lens for your content."
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Target audience</FieldLabel>
                <input
                  className={inputCls}
                  placeholder="Who reads your content? e.g. early-stage founders, ML engineers"
                  value={form.target_audience}
                  onChange={(e) => set("target_audience", e.target.value)}
                />
              </div>

              <OptionalHint />
            </>
          )}

          {/* ── Step 2 ──────────────────────────────────────────────────────── */}
          {step === 2 && (
            <>
              <div>
                <h2 className="font-headline text-[24px] text-[#2f3333] mb-2">
                  Your writing fingerprint.
                </h2>
                <p className="text-[13px] text-[#645e57] leading-relaxed">
                  These are injected directly into every post generation prompt.
                </p>
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Phrases you naturally use</FieldLabel>
                <TagInput
                  value={form.phrases_i_use}
                  onChange={(v) => set("phrases_i_use", v)}
                  placeholder="e.g. to be honest, let me be direct, here's the thing"
                  hint="Phrases that sound like you. Add 3–6."
                />
              </div>

              <div className="flex flex-col gap-1.5">
                <FieldLabel>Words you never use</FieldLabel>
                <TagInput
                  value={form.words_to_avoid}
                  onChange={(v) => set("words_to_avoid", v)}
                  placeholder="e.g. leverage, synergy, game-changing, transformative"
                  hint="Words that make you cringe. These get actively avoided."
                />
              </div>

              <div className="flex flex-col gap-3">
                <FieldLabel>Your writing rules</FieldLabel>
                {([0, 1, 2] as const).map((i) => (
                  <div key={i} className="flex flex-col gap-1">
                    <span className="text-[11px] text-[#aeb3b2] uppercase tracking-wide">
                      Rule {i + 1}
                    </span>
                    <input
                      className={inputCls}
                      placeholder={
                        i === 0
                          ? "e.g. Never use passive voice"
                          : i === 1
                          ? "e.g. Always open with a specific story"
                          : "e.g. No bullet points in LinkedIn posts"
                      }
                      value={form.writing_rules[i]}
                      onChange={(e) => setTriple("writing_rules", i, e.target.value)}
                    />
                  </div>
                ))}
              </div>

              <OptionalHint />
            </>
          )}

          {/* ── Step 3 ──────────────────────────────────────────────────────── */}
          {step === 3 && (
            <>
              <div>
                <h2 className="font-headline text-[24px] text-[#2f3333] mb-2">
                  Your opinions.
                </h2>
                <p className="text-[13px] text-[#645e57] leading-relaxed">
                  Contendo writes with conviction. These are the takes that make your content different from everyone else's.
                </p>
              </div>

              {([0, 1, 2] as const).map((i) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <span className="text-[11px] text-[#aeb3b2] uppercase tracking-wide">
                    Opinion {i + 1}
                  </span>
                  <textarea
                    className={inputCls}
                    rows={2}
                    placeholder="A take you'd defend publicly. Be specific — not 'AI is important' but 'most AI demos fail because founders optimize for wow moments, not retention'"
                    value={form.opinions[i]}
                    onChange={(e) => setTriple("opinions", i, e.target.value)}
                  />
                </div>
              ))}

              <p className="text-[11px] text-[#aeb3b2]">
                The more specific, the better. Vague opinions produce generic posts.
              </p>

              <OptionalHint />
            </>
          )}

          {/* ── Step 4 ──────────────────────────────────────────────────────── */}
          {step === 4 && (
            <>
              <div>
                <h2 className="font-headline text-[24px] text-[#2f3333] mb-2">
                  Your writing samples.
                </h2>
                <p className="text-[13px] text-[#645e57] leading-relaxed">
                  This is the single most powerful signal. Paste real posts or pieces you've written — Contendo learns your rhythm from these directly.
                </p>
              </div>

              {([0, 1, 2] as const).map((i) => (
                <div key={i} className="flex flex-col gap-1.5">
                  <FieldLabel>
                    Sample {i + 1}{" "}
                    {i > 0 && (
                      <span className="normal-case tracking-normal font-normal text-[#aeb3b2]">
                        (optional)
                      </span>
                    )}
                  </FieldLabel>
                  <textarea
                    className={inputCls}
                    rows={i === 0 ? 8 : 6}
                    placeholder={
                      i === 0
                        ? "Paste a real LinkedIn post, article paragraph, or anything you've actually published"
                        : "Another writing sample (optional)…"
                    }
                    value={form.writing_samples[i]}
                    onChange={(e) => setTriple("writing_samples", i, e.target.value)}
                  />
                </div>
              ))}

              <p className="label-caps text-[#aeb3b2] text-center">
                These are stored privately and never shared. They're only used to match your writing style in generated posts.
              </p>

              {error && (
                <p className="text-[13px] text-red-500 text-center">{error}</p>
              )}
            </>
          )}
        </div>

        {/* ── Navigation ──────────────────────────────────────────────────────── */}
        <div className={`flex gap-3 mt-8 ${step === 0 ? "justify-end" : "justify-between"}`}>
          {step > 0 && (
            <button
              onClick={() => { setError(""); setStep((s) => s - 1); }}
              className="flex-1 py-2.5 rounded-xl text-[14px] text-[#645e57] hover:bg-[#f3f4f3] transition-colors"
            >
              Back
            </button>
          )}
          {step < TOTAL_STEPS - 1 ? (
            <button
              onClick={() => setStep((s) => s + 1)}
              disabled={!canAdvance()}
              className="flex-1 btn-primary text-white py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-40 disabled:cursor-not-allowed transition-opacity"
            >
              Next
            </button>
          ) : (
            <button
              onClick={handleFinish}
              disabled={saving}
              className="flex-1 btn-primary text-white py-2.5 rounded-xl text-[14px] font-medium disabled:opacity-60 disabled:cursor-not-allowed transition-opacity flex items-center justify-center gap-2"
            >
              {saving ? (
                <>
                  <div className="w-4 h-4 border-2 border-white/40 border-t-white rounded-full animate-spin" />
                  Building…
                </>
              ) : (
                "Build my profile →"
              )}
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
