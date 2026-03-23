"use client";

import { useEffect, useRef, useState } from "react";

const SS_POST = "contentOS_last_post";
const SS_SCORE = "contentOS_last_score";
const SS_FEEDBACK = "contentOS_last_feedback";
const SS_ITERATIONS = "contentOS_last_iterations";
const SS_VISUALS = "contentOS_last_visuals";
const SS_IDEAS = "contentOS_last_ideas";
const SS_SHOW_ANALYSIS = "contentOS_show_analysis";
const SS_CURRENT_POST_ID = "contentOS_current_post_id";

const API = process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

type Format = "linkedin post" | "medium article" | "thread";
type Tone = "casual" | "technical" | "storytelling";

const FORMATS: { id: Format; label: string }[] = [
  { id: "linkedin post", label: "LinkedIn Post" },
  { id: "medium article", label: "Medium Article" },
  { id: "thread", label: "Thread" },
];

const TONES: { id: Tone; label: string; description: string }[] = [
  { id: "casual", label: "Casual", description: "Like texting a smart friend" },
  { id: "technical", label: "Technical", description: "Precise, assumes expertise" },
  { id: "storytelling", label: "Storytelling", description: "Scene-driven, lesson earned" },
];

interface GenerateResult {
  post: string;
  score: number;
  score_feedback: string[];
  iterations: number;
}

interface Suggestion {
  title: string;
  angle: string;
  format: string;
  reasoning: string;
}

interface Visual {
  type: "diagram" | "image_reminder";
  placeholder: string;
  description: string;
  position: number;
  svg_code: string | null;
  reminder_text: string | null;
}

const FORMAT_BADGE: Record<string, string> = {
  "linkedin post": "LinkedIn",
  "medium article": "Medium",
  "thread": "Thread",
};

type ScreenState = "configure" | "generating" | "review" | "analyse" | "visuals";

function getScreenState(
  loading: boolean,
  result: GenerateResult | null,
  showAnalysis: boolean,
  visualsVisible: boolean
): ScreenState {
  if (loading) return "generating";
  if (!result) return "configure";
  if (showAnalysis) return "analyse";
  if (visualsVisible) return "visuals";
  return "review";
}

function getStep(state: ScreenState): number {
  switch (state) {
    case "configure": return 1;
    case "generating": return 2;
    case "review":
    case "visuals": return 3;
    case "analyse": return 4;
  }
}

// ─── Step Indicator ──────────────────────────────────────────────────────────

const STEP_LABELS = ["Configure", "Generate", "Review post", "Analyse"];

function StepIndicator({ currentStep }: { currentStep: number }) {
  return (
    <div
      style={{ borderBottom: "0.5px solid #e8e3da", height: "40px" }}
      className="flex items-center px-8 bg-page shrink-0"
    >
      <div className="flex items-center">
        {STEP_LABELS.map((label, i) => {
          const step = i + 1;
          const isDone = step < currentStep;
          const isActive = step === currentStep;
          return (
            <div key={i} className="flex items-center">
              <div className={`flex items-center gap-1.5 transition-opacity ${
                isActive ? "opacity-100" : isDone ? "opacity-70" : "opacity-30"
              }`}>
                <div className={`w-4 h-4 rounded-full flex items-center justify-center text-[10px] font-medium leading-none flex-shrink-0 ${
                  isDone || isActive
                    ? "bg-text-primary text-card"
                    : "bg-stat border border-border text-text-muted"
                }`}>
                  {isDone ? (
                    <svg width="8" height="8" viewBox="0 0 8 8" fill="none">
                      <path d="M1.5 4L3.5 6L6.5 2" stroke="currentColor" strokeWidth="1.4" strokeLinecap="round" strokeLinejoin="round" />
                    </svg>
                  ) : step}
                </div>
                <span className={`text-xs ${isActive ? "text-text-primary font-medium" : "text-text-muted"}`}>
                  {label}
                </span>
              </div>
              {i < STEP_LABELS.length - 1 && (
                <div className="w-8 h-px bg-border mx-2" />
              )}
            </div>
          );
        })}
      </div>
    </div>
  );
}

// ─── Score Bar ───────────────────────────────────────────────────────────────

function ScoreBar({ score }: { score: number }) {
  const barColor = score >= 75 ? "bg-score-green" : score >= 55 ? "bg-score-amber" : "bg-score-red";
  const textColor = score >= 75 ? "text-score-green" : "text-text-secondary";
  return (
    <div>
      <div className="flex items-baseline justify-between mb-2">
        <span className="text-xs font-medium text-text-secondary uppercase tracking-widest">
          Authenticity score
        </span>
        <span className={`text-2xl font-semibold tabular-nums ${textColor}`}>
          {score}
          <span className="text-sm font-normal text-text-muted">/100</span>
        </span>
      </div>
      <div className="h-1.5 rounded-full bg-stat">
        <div
          className={`h-full rounded-full ${barColor} transition-all duration-700`}
          style={{ width: `${score}%` }}
        />
      </div>
    </div>
  );
}

// ─── SVG / Visual helpers ─────────────────────────────────────────────────────

function svgToDataURL(svgCode: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const parser = new DOMParser();
    const doc = parser.parseFromString(svgCode, "image/svg+xml");
    const svgEl = doc.querySelector("svg");
    const viewBox = svgEl?.getAttribute("viewBox") ?? "0 0 680 400";
    const parts = viewBox.split(/[\s,]+/);
    const vbW = parseFloat(parts[2]) || 680;
    const vbH = parseFloat(parts[3]) || 400;

    const canvas = document.createElement("canvas");
    canvas.width = vbW * 2;
    canvas.height = vbH * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) { reject(new Error("No canvas context")); return; }

    const img = new Image();
    const blob = new Blob([svgCode], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);

    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => { URL.revokeObjectURL(url); reject(new Error("Image load failed")); };
    img.src = url;
  });
}

function DiagramCard({ visual }: { visual: Visual }) {
  const [pngState, setPngState] = useState<"idle" | "opened" | "blocked">("idle");
  const [fallbackDataURL, setFallbackDataURL] = useState<string | null>(null);

  if (!visual.svg_code) {
    return (
      <div className="rounded-lg border border-score-red bg-score-red-bg px-5 py-4">
        <p className="text-sm font-medium text-score-red">
          Diagram generation failed — try regenerating the post
        </p>
        <p className="text-xs text-score-red opacity-70 mt-1">{visual.description}</p>
      </div>
    );
  }

  const handleOpen = async () => {
    try {
      const dataURL = await svgToDataURL(visual.svg_code!);
      const win = window.open();
      if (win) {
        win.document.write(
          `<html><body style="margin:0;background:#fdfcfb;display:flex;justify-content:center;padding:24px">` +
          `<img src="${dataURL}" style="max-width:100%;border-radius:8px" />` +
          `</body></html>`
        );
        win.document.close();
        setPngState("opened");
        setTimeout(() => setPngState("idle"), 5000);
      } else {
        setFallbackDataURL(dataURL);
        setPngState("blocked");
      }
    } catch {
      // conversion failed — do nothing
    }
  };

  return (
    <div className="rounded-lg border border-border bg-card overflow-hidden">
      <div className="px-5 py-3 border-b border-border-subtle">
        <p className="text-sm font-medium text-text-secondary">
          Diagram —{" "}
          <span className="font-normal text-text-muted">
            {visual.description.length > 60
              ? visual.description.slice(0, 60) + "…"
              : visual.description}
          </span>
        </p>
      </div>
      <div className="p-4 overflow-x-auto" dangerouslySetInnerHTML={{ __html: visual.svg_code }} />
      <div className="px-5 py-3 border-t border-border-subtle space-y-2">
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpen}
            className="text-xs border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:border-text-primary hover:text-text-primary transition-colors"
          >
            Open as PNG
          </button>
          {pngState === "opened" && (
            <span className="text-xs text-text-muted">
              PNG opened in new tab — right-click and <strong>Save Image</strong>
            </span>
          )}
          {pngState === "blocked" && (
            <span className="text-xs text-text-muted">
              Popup blocked — right-click the image below and <strong>Save Image</strong>
            </span>
          )}
        </div>
        {pngState === "blocked" && fallbackDataURL && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={fallbackDataURL} alt="diagram PNG" className="max-w-full rounded-lg border border-border" />
        )}
      </div>
    </div>
  );
}

function ImageReminderCard({ visual }: { visual: Visual }) {
  return (
    <div className="rounded-lg border-2 border-dashed border-border bg-surface px-5 py-4 space-y-1">
      <p className="text-xs font-semibold uppercase tracking-widest text-text-hint">
        Add your own visual
      </p>
      <p className="text-sm text-text-muted leading-relaxed">{visual.reminder_text}</p>
    </div>
  );
}

// ─── Settings Drawer ──────────────────────────────────────────────────────────

interface DrawerProps {
  initialTopic: string;
  initialFormat: Format;
  initialTone: Tone;
  initialContext: string;
  onCancel: () => void;
  onRegenerate: (overrides: { topic: string; format: Format; tone: Tone; context: string }) => void;
}

function SettingsDrawer({ initialTopic, initialFormat, initialTone, initialContext, onCancel, onRegenerate }: DrawerProps) {
  const [dTopic, setDTopic] = useState(initialTopic);
  const [dFormat, setDFormat] = useState<Format>(initialFormat);
  const [dTone, setDTone] = useState<Tone>(initialTone);
  const [dContext, setDContext] = useState(initialContext);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/10 z-40"
        onClick={onCancel}
      />
      {/* Drawer panel */}
      <div className="fixed top-0 right-0 h-full w-80 bg-page border-l border-border z-50 flex flex-col shadow-lg">
        {/* Header */}
        <div
          style={{ borderBottom: "0.5px solid #e8e3da", height: "52px" }}
          className="flex items-center justify-between px-5 shrink-0"
        >
          <p className="text-sm font-medium text-text-primary">Regenerate settings</p>
          <button
            onClick={onCancel}
            className="text-text-muted hover:text-text-primary transition-colors text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-6 space-y-5">
          {/* Topic */}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Topic</label>
            <input
              type="text"
              value={dTopic}
              onChange={(e) => setDTopic(e.target.value)}
              placeholder="What do you want to write about?"
              className="w-full rounded-lg border border-border-input bg-card px-3 py-2.5 text-sm text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary transition-colors"
            />
          </div>

          {/* Format */}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Format</label>
            <div className="space-y-1.5">
              {FORMATS.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setDFormat(f.id)}
                  className={`w-full px-3 py-2 rounded-lg text-sm text-left border transition-colors ${
                    dFormat === f.id
                      ? "border-text-primary bg-hover text-text-primary font-medium"
                      : "border-border text-text-secondary hover:bg-hover bg-card"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tone */}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">Tone</label>
            <div className="space-y-1.5">
              {TONES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setDTone(t.id)}
                  className={`w-full px-3 py-2.5 rounded-lg text-sm text-left border transition-colors ${
                    dTone === t.id
                      ? "border-text-primary bg-hover text-text-primary"
                      : "border-border text-text-secondary hover:bg-hover bg-card"
                  }`}
                >
                  <div className={`font-medium ${dTone === t.id ? "" : ""}`}>{t.label}</div>
                  <div className={`text-xs mt-0.5 ${dTone === t.id ? "text-text-muted" : "text-text-hint"}`}>
                    {t.description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Context */}
          <div>
            <label className="block text-xs font-medium text-text-secondary mb-1.5">
              Additional context{" "}
              <span className="font-normal text-text-hint">(optional)</span>
            </label>
            <textarea
              value={dContext}
              onChange={(e) => setDContext(e.target.value)}
              placeholder="Specific angle, story, or data point..."
              rows={3}
              className="w-full rounded-lg border border-border-input bg-card px-3 py-2.5 text-sm text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary resize-none transition-colors"
            />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{ borderTop: "0.5px solid #e8e3da" }}
          className="px-5 py-4 flex gap-2 shrink-0"
        >
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg border border-border text-text-secondary text-sm py-2 hover:border-text-primary hover:text-text-primary transition-colors bg-card"
          >
            Cancel
          </button>
          <button
            onClick={() => onRegenerate({ topic: dTopic, format: dFormat, tone: dTone, context: dContext })}
            className="flex-1 rounded-lg bg-text-primary text-card text-sm font-medium py-2 hover:opacity-90 transition-opacity"
          >
            Regenerate
          </button>
        </div>
      </div>
    </>
  );
}

// ─── Main Component ───────────────────────────────────────────────────────────

export default function CreatePost() {
  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState<Format>("linkedin post");
  const [tone, setTone] = useState<Tone>("casual");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [editedPost, setEditedPost] = useState("");
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsVisible, setSuggestionsVisible] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);
  const [selectedIdeaIndex, setSelectedIdeaIndex] = useState<number | null>(null);
  const [ideaCount, setIdeaCount] = useState(8);
  const [ideaTopic, setIdeaTopic] = useState("");

  const [visuals, setVisuals] = useState<Visual[]>([]);
  const [visualsLoading, setVisualsLoading] = useState(false);
  const [visualsVisible, setVisualsVisible] = useState(false);

  const [refineInstruction, setRefineInstruction] = useState("");
  const [refineLoading, setRefineLoading] = useState(false);
  const [refineError, setRefineError] = useState("");

  const [showAnalysis, setShowAnalysis] = useState(false);
  const [currentPostId, setCurrentPostId] = useState<number | null>(null);
  const [restored, setRestored] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const topicRef = useRef<HTMLInputElement>(null);

  const screenState = getScreenState(loading, result, showAnalysis, visualsVisible);
  const currentStep = getStep(screenState);

  // Restore session on mount
  useEffect(() => {
    try {
      const savedPost = sessionStorage.getItem(SS_POST);
      const savedScore = sessionStorage.getItem(SS_SCORE);
      const savedFeedback = sessionStorage.getItem(SS_FEEDBACK);
      const savedIterations = sessionStorage.getItem(SS_ITERATIONS);
      const savedVisuals = sessionStorage.getItem(SS_VISUALS);
      const savedIdeas = sessionStorage.getItem(SS_IDEAS);
      const savedShowAnalysis = sessionStorage.getItem(SS_SHOW_ANALYSIS);
      const savedPostId = sessionStorage.getItem(SS_CURRENT_POST_ID);

      if (savedPost && savedScore && savedFeedback && savedIterations) {
        const restoredResult: GenerateResult = {
          post: savedPost,
          score: Number(savedScore),
          score_feedback: JSON.parse(savedFeedback),
          iterations: Number(savedIterations),
        };
        setResult(restoredResult);
        setEditedPost(savedPost);
        if (savedVisuals) {
          const parsedVisuals: Visual[] = JSON.parse(savedVisuals);
          setVisuals(parsedVisuals);
          setVisualsVisible(parsedVisuals.length > 0);
        }
        setRestored(true);
      }

      if (savedIdeas) {
        const parsedIdeas: Suggestion[] = JSON.parse(savedIdeas);
        if (parsedIdeas.length > 0) {
          setSuggestions(parsedIdeas);
          setSuggestionsVisible(true);
        }
      }

      if (savedShowAnalysis !== null) {
        setShowAnalysis(savedShowAnalysis === "true");
      }

      if (savedPostId) {
        setCurrentPostId(Number(savedPostId));
      }

      // Check for prefill from Ideas screen
      const prefillTopic = sessionStorage.getItem("contentOS_last_topic");
      const prefillFormat = sessionStorage.getItem("contentOS_prefill_format");
      if (prefillTopic) setTopic(prefillTopic);
      if (prefillFormat) setFormat(prefillFormat as Format);
      sessionStorage.removeItem("contentOS_prefill_format");
    } catch {
      // corrupt sessionStorage — ignore
    }
  }, []);

  // Persist session whenever result or visuals change
  useEffect(() => {
    if (!result) return;
    try {
      sessionStorage.setItem(SS_POST, editedPost);
      sessionStorage.setItem(SS_SCORE, String(result.score));
      sessionStorage.setItem(SS_FEEDBACK, JSON.stringify(result.score_feedback));
      sessionStorage.setItem(SS_ITERATIONS, String(result.iterations));
      sessionStorage.setItem(SS_VISUALS, JSON.stringify(visuals));
    } catch {
      // ignore
    }
  }, [result, editedPost, visuals]);

  // Persist showAnalysis preference
  useEffect(() => {
    try {
      sessionStorage.setItem(SS_SHOW_ANALYSIS, String(showAnalysis));
    } catch {
      // ignore
    }
  }, [showAnalysis]);

  // Pre-fill refinement instruction from latest feedback
  useEffect(() => {
    if (!result || result.score_feedback.length === 0) return;
    const items = result.score_feedback.slice(0, 3);
    setRefineInstruction(
      "Fix the following issues: " +
      items.map((f) => f.trim().replace(/\.+$/, "")).join(". ") +
      "."
    );
  }, [result]);

  const clearSession = () => {
    [SS_POST, SS_SCORE, SS_FEEDBACK, SS_ITERATIONS, SS_VISUALS, SS_IDEAS, SS_CURRENT_POST_ID].forEach((k) =>
      sessionStorage.removeItem(k)
    );
    setRestored(false);
    setCurrentPostId(null);
    setSuggestions([]);
    setSuggestionsVisible(false);
    setSelectedIdeaIndex(null);
  };

  const autoSavePost = async (data: GenerateResult, postContent: string) => {
    try {
      const res = await fetch(`${API}/log-post`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          format,
          tone,
          content: postContent,
          authenticity_score: data.score,
          svg_diagrams: null,
        }),
      });
      if (!res.ok) return;
      const saved = await res.json();
      const postId: number = saved.post_id;
      setCurrentPostId(postId);
      try {
        sessionStorage.setItem(SS_CURRENT_POST_ID, String(postId));
      } catch {
        // ignore
      }
    } catch {
      // auto-save failure is non-critical
    }
  };

  const patchHistory = async (fields: {
    content?: string;
    authenticity_score?: number;
    svg_diagrams?: object[] | null;
  }) => {
    const postId = currentPostId ?? (() => {
      try { return Number(sessionStorage.getItem(SS_CURRENT_POST_ID)) || null; } catch { return null; }
    })();
    if (!postId) return;
    try {
      await fetch(`${API}/history/${postId}`, {
        method: "PATCH",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(fields),
      });
    } catch {
      // patch failure is non-critical
    }
  };

  const generate = async (overrides?: {
    topic?: string;
    format?: Format;
    tone?: Tone;
    context?: string;
  }) => {
    const t = overrides?.topic ?? topic;
    const f = overrides?.format ?? format;
    const tn = overrides?.tone ?? tone;
    const ctx = overrides?.context ?? context;

    if (!t.trim()) {
      setError("Topic is required.");
      return;
    }
    setError("");
    setLoading(true);
    setResult(null);
    setVisuals([]);
    setVisualsVisible(false);
    setShowAnalysis(false);
    clearSession();

    // Apply overrides to main state
    if (overrides?.topic !== undefined) setTopic(overrides.topic);
    if (overrides?.format !== undefined) setFormat(overrides.format);
    if (overrides?.tone !== undefined) setTone(overrides.tone);
    if (overrides?.context !== undefined) setContext(overrides.context);

    try {
      const res = await fetch(`${API}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic: t, format: f, tone: tn, context: ctx }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Generation failed");
      }

      const data: GenerateResult = await res.json();
      setResult(data);
      setEditedPost(data.post);
      await autoSavePost(data, data.post);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
    }
  };

  const handleRefine = async () => {
    if (!refineInstruction.trim()) {
      setRefineError("Refinement instruction is required.");
      return;
    }
    setRefineError("");
    setRefineLoading(true);
    try {
      const res = await fetch(`${API}/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_draft: editedPost,
          refinement_instruction: refineInstruction,
        }),
      });
      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Refinement failed");
      }
      const data: { refined_draft: string; score: number; score_feedback: string[] } = await res.json();

      setEditedPost(data.refined_draft);
      setResult((prev) =>
        prev ? { ...prev, score: data.score, score_feedback: data.score_feedback } : prev
      );

      try {
        sessionStorage.setItem(SS_POST, data.refined_draft);
        sessionStorage.setItem(SS_SCORE, String(data.score));
        sessionStorage.setItem(SS_FEEDBACK, JSON.stringify(data.score_feedback));
      } catch {
        // ignore
      }

      await patchHistory({ content: data.refined_draft, authenticity_score: data.score });
    } catch (e: unknown) {
      setRefineError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setRefineLoading(false);
    }
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(editedPost);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const handleGenerateVisuals = async () => {
    setVisualsLoading(true);
    setVisualsVisible(true);
    setVisuals([]);
    setShowAnalysis(false);
    try {
      const res = await fetch(`${API}/generate-visuals`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ post_content: editedPost }),
      });
      if (!res.ok) throw new Error("Visuals generation failed");
      const data = await res.json();
      const newVisuals: Visual[] = data.visuals ?? [];
      setVisuals(newVisuals);

      const diagrams = newVisuals
        .filter((v) => v.type === "diagram" && v.svg_code)
        .map((v) => ({ position: v.position, description: v.description, svg_code: v.svg_code }));
      if (diagrams.length > 0) {
        await patchHistory({ svg_diagrams: diagrams });
      }
    } catch {
      setVisuals([]);
    } finally {
      setVisualsLoading(false);
    }
  };

  const handleGetIdeas = async () => {
    setSuggestionsLoading(true);
    setSuggestionsVisible(true);
    setSuggestions([]);
    setSelectedIdeaIndex(null);
    try {
      const params = new URLSearchParams({ count: String(ideaCount) });
      if (ideaTopic.trim()) params.set("topic", ideaTopic.trim());
      const res = await fetch(`${API}/suggestions?${params}`);
      if (!res.ok) throw new Error("Failed to fetch suggestions");
      const data = await res.json();
      const fetched: Suggestion[] = data.suggestions ?? [];
      setSuggestions(fetched);
      try {
        sessionStorage.setItem(SS_IDEAS, JSON.stringify(fetched));
      } catch {
        // ignore
      }
    } catch {
      setSuggestions([]);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const handleUseSuggestion = (s: Suggestion, index: number) => {
    setTopic(s.title);
    const fmt = s.format as Format;
    if (FORMATS.find((f) => f.id === fmt)) setFormat(fmt);
    setSelectedIdeaIndex(index);
    topicRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    topicRef.current?.focus();
  };

  const handleDismissIdeas = () => {
    setSuggestionsVisible(false);
    setSuggestions([]);
    setSelectedIdeaIndex(null);
    try { sessionStorage.removeItem(SS_IDEAS); } catch { /* ignore */ }
  };

  const handleDrawerRegenerate = (overrides: { topic: string; format: Format; tone: Tone; context: string }) => {
    setDrawerOpen(false);
    generate(overrides);
  };

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div className="-mx-8 -mt-10 -mb-10 relative min-h-screen bg-page flex flex-col">

      {/* Top bar */}
      <div
        style={{ borderBottom: "0.5px solid #e8e3da", height: "52px" }}
        className="flex items-center justify-between px-8 bg-page shrink-0"
      >
        <div className="flex items-baseline gap-3">
          <span className="text-sm font-medium text-text-primary">Create Post</span>
          <span className="text-xs text-text-muted">
            {screenState === "configure" && "Set up your post"}
            {screenState === "generating" && "Generating your draft…"}
            {screenState === "review" && "Review and refine"}
            {screenState === "analyse" && "Authenticity analysis"}
            {screenState === "visuals" && "Visual assets"}
          </span>
        </div>
      </div>

      {/* Step indicator */}
      <StepIndicator currentStep={currentStep} />

      {/* Page content */}
      <div className="flex-1 px-8 py-8">
        <div className="max-w-[660px] mx-auto space-y-6">

          {/* Restored session banner */}
          {restored && screenState !== "generating" && (
            <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-2.5">
              <p className="text-xs text-text-secondary">Restored your last session</p>
              <button
                onClick={() => {
                  clearSession();
                  setResult(null);
                  setEditedPost("");
                  setVisuals([]);
                  setVisualsVisible(false);
                  setShowAnalysis(false);
                }}
                className="text-text-muted hover:text-text-secondary text-xl leading-none ml-4"
                aria-label="Dismiss"
              >
                ×
              </button>
            </div>
          )}

          {/* Ideas panel */}
          {suggestionsVisible && (
            <div className="rounded-lg border border-border bg-card overflow-hidden">
              <div className="flex items-center justify-between px-5 py-3 border-b border-border-subtle">
                <div>
                  <p className="text-sm font-medium text-text-primary">
                    {suggestionsLoading
                      ? "Finding ideas…"
                      : `${suggestions.length} idea${suggestions.length !== 1 ? "s" : ""} from your memory`}
                  </p>
                  {!suggestionsLoading && (
                    <p className="text-xs text-text-muted mt-0.5">
                      {ideaTopic.trim()
                        ? `Focused on: ${ideaTopic.trim()}`
                        : "Ideas drawn from your full knowledge base"}
                    </p>
                  )}
                </div>
                <div className="flex items-center gap-3">
                  {!suggestionsLoading && (
                    <button
                      onClick={handleGetIdeas}
                      className="text-xs text-text-secondary hover:text-text-primary border border-border rounded-lg px-2.5 py-1 transition-colors"
                    >
                      Refresh
                    </button>
                  )}
                  <button
                    onClick={handleDismissIdeas}
                    className="text-text-muted hover:text-text-primary transition-colors text-xl leading-none"
                  >
                    ×
                  </button>
                </div>
              </div>

              {suggestionsLoading && (
                <div className="px-5 py-6 text-sm text-text-muted">Thinking…</div>
              )}

              {!suggestionsLoading && suggestions.length === 0 && (
                <div className="px-5 py-6 text-sm text-text-muted">
                  No suggestions returned. Try adding more content to your memory first.
                </div>
              )}

              {!suggestionsLoading && suggestions.length > 0 && (
                <div className="divide-y divide-border-subtle">
                  {suggestions.map((s, i) => (
                    <div
                      key={i}
                      className={`px-5 py-4 flex items-start justify-between gap-4 transition-colors ${
                        selectedIdeaIndex === i ? "bg-stat" : ""
                      }`}
                    >
                      <div className="flex-1 min-w-0">
                        <div className="flex items-center gap-2">
                          {selectedIdeaIndex === i && (
                            <span className="text-score-green text-xs font-medium">✓</span>
                          )}
                          <p className="text-sm font-medium text-text-primary leading-snug">{s.title}</p>
                        </div>
                        <div className="mt-1 flex items-center gap-2">
                          <span className="text-xs px-2 py-0.5 rounded-full bg-stat border border-border text-text-muted">
                            {FORMAT_BADGE[s.format] ?? s.format}
                          </span>
                        </div>
                        <p className="mt-1 text-xs text-text-muted leading-relaxed">{s.angle}</p>
                      </div>
                      <button
                        onClick={() => handleUseSuggestion(s, i)}
                        className={`text-xs whitespace-nowrap rounded-lg px-3 py-1.5 transition-colors border flex-shrink-0 ${
                          selectedIdeaIndex === i
                            ? "border-border bg-card text-text-muted"
                            : "border-border bg-card text-text-secondary hover:bg-hover"
                        }`}
                      >
                        {selectedIdeaIndex === i ? "Selected" : "Use this"}
                      </button>
                    </div>
                  ))}
                </div>
              )}
            </div>
          )}

          {/* ── State 1: Configure ─────────────────────────────────────────── */}
          {screenState === "configure" && (
            <div className="space-y-5">
              {/* Topic */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">Topic</label>
                <input
                  ref={topicRef}
                  type="text"
                  value={topic}
                  onChange={(e) => setTopic(e.target.value)}
                  onKeyDown={(e) => e.key === "Enter" && generate()}
                  placeholder="What do you want to write about?"
                  className="w-full rounded-lg border border-border-input bg-card px-4 py-2.5 text-sm text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary transition-colors"
                />
              </div>

              {/* Format */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">Format</label>
                <div className="flex gap-2">
                  {FORMATS.map((f) => (
                    <button
                      key={f.id}
                      onClick={() => setFormat(f.id)}
                      className={`flex-1 px-4 py-2 rounded-lg text-sm font-medium border transition-colors ${
                        format === f.id
                          ? "border-text-primary bg-hover text-text-primary"
                          : "border-border text-text-secondary hover:text-text-primary hover:bg-hover bg-card"
                      }`}
                    >
                      {f.label}
                    </button>
                  ))}
                </div>
              </div>

              {/* Tone */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">Tone</label>
                <div className="flex gap-2">
                  {TONES.map((t) => (
                    <button
                      key={t.id}
                      onClick={() => setTone(t.id)}
                      className={`flex-1 px-4 py-2.5 rounded-lg text-sm border transition-colors text-left ${
                        tone === t.id
                          ? "border-text-primary bg-hover text-text-primary"
                          : "border-border text-text-secondary hover:text-text-primary hover:bg-hover bg-card"
                      }`}
                    >
                      <div className="font-medium">{t.label}</div>
                      <div className={`text-xs mt-0.5 ${tone === t.id ? "text-text-muted" : "text-text-hint"}`}>
                        {t.description}
                      </div>
                    </button>
                  ))}
                </div>
              </div>

              {/* Context */}
              <div>
                <label className="block text-xs font-medium text-text-secondary mb-1.5">
                  Additional context{" "}
                  <span className="font-normal text-text-hint">(optional)</span>
                </label>
                <textarea
                  value={context}
                  onChange={(e) => setContext(e.target.value)}
                  placeholder="Specific angle, story, or data point you want included…"
                  rows={3}
                  className="w-full rounded-lg border border-border-input bg-card px-4 py-3 text-sm text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary resize-none transition-colors"
                />
              </div>

              {error && <p className="text-sm text-score-red">{error}</p>}

              <button
                onClick={() => generate()}
                disabled={loading}
                className="w-full rounded-lg bg-text-primary text-card font-medium py-2.5 text-sm hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed transition-opacity"
              >
                Generate
              </button>
            </div>
          )}

          {/* ── State 2: Generating ────────────────────────────────────────── */}
          {screenState === "generating" && (
            <div className="flex flex-col items-center justify-center py-20 gap-5 text-center">
              <div className="w-10 h-10 rounded-full border-2 border-border border-t-text-primary animate-spin" />
              <div>
                <p className="text-sm font-medium text-text-primary">Generating your draft</p>
                <p className="text-xs text-text-muted mt-1">
                  Retrieving from memory, composing in your voice, running humanizer pass…
                </p>
              </div>
            </div>
          )}

          {/* ── State 3: Review post ───────────────────────────────────────── */}
          {screenState === "review" && result && (
            <div className="space-y-4">
              {/* Post meta */}
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <span className="text-xs px-2 py-0.5 rounded-full bg-stat border border-border text-text-muted">
                    {FORMAT_BADGE[format] ?? format}
                  </span>
                  <span className="text-xs text-text-muted capitalize">{tone}</span>
                </div>
                <button
                  onClick={() => { setResult(null); setEditedPost(""); setShowAnalysis(false); }}
                  className="text-xs text-text-muted hover:text-text-secondary transition-colors"
                >
                  ← Start over
                </button>
              </div>

              {/* Editable textarea */}
              <textarea
                value={editedPost}
                onChange={(e) => setEditedPost(e.target.value)}
                rows={18}
                className="w-full rounded-lg border border-border-input bg-card px-4 py-4 text-sm text-text-primary focus:outline-none focus:border-text-primary resize-none leading-relaxed transition-colors"
              />

              {/* Action buttons */}
              <div className="flex gap-2">
                <button
                  onClick={handleCopy}
                  className="flex-1 rounded-lg border border-border text-text-secondary font-medium py-2 text-sm hover:border-text-primary hover:text-text-primary transition-colors bg-card"
                >
                  {copied ? "Copied!" : "Copy"}
                </button>
                <button
                  onClick={handleGenerateVisuals}
                  disabled={visualsLoading}
                  className="flex-1 rounded-lg border border-border text-text-secondary font-medium py-2 text-sm hover:border-text-primary hover:text-text-primary transition-colors bg-card disabled:opacity-50"
                >
                  Visuals
                </button>
                <button
                  onClick={() => setDrawerOpen(true)}
                  className="flex-1 rounded-lg border border-border text-text-secondary font-medium py-2 text-sm hover:border-text-primary hover:text-text-primary transition-colors bg-card"
                >
                  Settings
                </button>
                <button
                  onClick={() => generate()}
                  disabled={loading}
                  className="flex-1 rounded-lg bg-text-primary text-card font-medium py-2 text-sm hover:opacity-90 disabled:opacity-50 transition-opacity"
                >
                  Regenerate
                </button>
              </div>

              <div className="flex items-center justify-between">
                <p className="text-xs text-text-hint">Auto-saved to history</p>
                <button
                  onClick={() => setShowAnalysis(true)}
                  className="text-xs text-text-muted hover:text-text-secondary transition-colors underline underline-offset-2"
                >
                  View authenticity analysis →
                </button>
              </div>
            </div>
          )}

          {/* ── State 4: Analyse ──────────────────────────────────────────── */}
          {screenState === "analyse" && result && (
            <div className="space-y-6">
              {/* Back link */}
              <button
                onClick={() => setShowAnalysis(false)}
                className="text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                ← Back to post
              </button>

              {/* Score bar */}
              <div className="rounded-lg border border-border bg-card px-5 py-5">
                <ScoreBar score={result.score} />
                <p className="text-xs text-text-muted mt-3">
                  {result.iterations} humanizer iteration{result.iterations !== 1 ? "s" : ""}
                </p>
              </div>

              {/* Feedback */}
              {result.score_feedback.length > 0 && (
                <div className="rounded-lg border border-border bg-card px-5 py-5 space-y-3">
                  <p className="text-xs font-medium uppercase tracking-widest text-text-hint">Feedback</p>
                  <div className="space-y-2">
                    {result.score_feedback.map((f, i) => (
                      <div key={i} className="flex items-start gap-2.5">
                        <span className="text-text-hint text-xs mt-0.5 flex-shrink-0">—</span>
                        <p className="text-sm text-text-secondary leading-relaxed">{f}</p>
                      </div>
                    ))}
                  </div>
                </div>
              )}

              {/* Refine */}
              <div className="rounded-lg border border-border bg-stat px-5 py-5 space-y-3">
                <p className="text-xs font-medium uppercase tracking-widest text-text-hint">Refine draft</p>
                <textarea
                  value={refineInstruction}
                  onChange={(e) => setRefineInstruction(e.target.value)}
                  rows={3}
                  placeholder="Describe what to fix — e.g. make the hook more specific, add a concrete data point in paragraph 2."
                  className="w-full rounded-lg border border-border-input bg-card px-4 py-3 text-sm text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary resize-none transition-colors"
                />
                {refineError && <p className="text-xs text-score-red">{refineError}</p>}
                <button
                  onClick={handleRefine}
                  disabled={refineLoading}
                  className="rounded-lg border border-border text-text-secondary font-medium px-4 py-2 text-sm hover:border-text-primary hover:text-text-primary transition-colors bg-card disabled:opacity-50"
                >
                  {refineLoading ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                      Refining…
                    </span>
                  ) : (
                    "Refine draft"
                  )}
                </button>
              </div>
            </div>
          )}

          {/* ── State 5: Visuals ──────────────────────────────────────────── */}
          {screenState === "visuals" && (
            <div className="space-y-5">
              {/* Back link */}
              <div className="flex items-center justify-between">
                <button
                  onClick={() => setVisualsVisible(false)}
                  className="text-xs text-text-muted hover:text-text-secondary transition-colors"
                >
                  ← Back to post
                </button>
                <button
                  onClick={handleGenerateVisuals}
                  disabled={visualsLoading}
                  className="text-xs border border-border rounded-lg px-3 py-1.5 text-text-secondary hover:border-text-primary hover:text-text-primary transition-colors bg-card disabled:opacity-50"
                >
                  {visualsLoading ? "Scanning…" : "Regenerate visuals"}
                </button>
              </div>

              {visualsLoading && (
                <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
                  <div className="w-8 h-8 rounded-full border-2 border-border border-t-text-primary animate-spin" />
                  <p className="text-sm text-text-muted">Scanning post for visual opportunities…</p>
                </div>
              )}

              {!visualsLoading && visuals.length === 0 && (
                <div className="rounded-lg border border-border bg-card px-5 py-5">
                  <p className="text-sm text-text-muted leading-relaxed">
                    No visual placeholders found. Add{" "}
                    <code className="text-xs bg-stat px-1 py-0.5 rounded">[DIAGRAM: description]</code>
                    {" "}or{" "}
                    <code className="text-xs bg-stat px-1 py-0.5 rounded">[IMAGE: description]</code>
                    {" "}to your post and try again.
                  </p>
                </div>
              )}

              {!visualsLoading &&
                visuals.map((v, i) =>
                  v.type === "diagram" ? (
                    <DiagramCard key={i} visual={v} />
                  ) : (
                    <ImageReminderCard key={i} visual={v} />
                  )
                )}
            </div>
          )}

        </div>
      </div>

      {/* Settings drawer */}
      {drawerOpen && (
        <SettingsDrawer
          initialTopic={topic}
          initialFormat={format}
          initialTone={tone}
          initialContext={context}
          onCancel={() => setDrawerOpen(false)}
          onRegenerate={handleDrawerRegenerate}
        />
      )}
    </div>
  );
}
