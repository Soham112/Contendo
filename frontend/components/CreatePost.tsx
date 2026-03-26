"use client";

import { useEffect, useRef, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";

const SS_POST = "contentOS_last_post";
const SS_SCORE = "contentOS_last_score";
const SS_FEEDBACK = "contentOS_last_feedback";
const SS_ITERATIONS = "contentOS_last_iterations";
const SS_VISUALS = "contentOS_last_visuals";
const SS_IDEAS = "contentOS_last_ideas";
const SS_SHOW_ANALYSIS = "contentOS_show_analysis";
const SS_CURRENT_POST_ID = "contentOS_current_post_id";
const SS_TOPIC = "contentOS_last_topic_meta";
const SS_FORMAT = "contentOS_last_format_meta";
const SS_TONE = "contentOS_last_tone_meta";
const SS_SCORED = "contentOS_last_scored";

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
  scored: boolean;
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
          `<html><body style="margin:0;background:#faf9f7;display:flex;justify-content:center;padding:24px">` +
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
          style={{ borderBottom: "0.5px solid #e0dcd3", height: "52px" }}
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
              className="w-full rounded-xl border border-border-subtle bg-card px-4 py-3 text-sm font-medium text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary shadow-sm focus-within:shadow-md focus-within:border-border transition-all duration-200"
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
                      ? "border-text-primary bg-surface text-text-primary shadow-sm ring-1 ring-text-primary ring-opacity-10 font-medium"
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
                      ? "border-text-primary bg-surface text-text-primary shadow-sm ring-1 ring-text-primary ring-opacity-10"
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
              className="w-full rounded-xl border border-border-subtle bg-card px-4 py-3 text-sm text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary resize-none shadow-sm focus-within:shadow-md focus-within:border-border transition-all duration-200"
            />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{ borderTop: "0.5px solid #e0dcd3" }}
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

  const { showToast } = useToast();
  const [lastSaved, setLastSaved] = useState<number | null>(null);
  const [saveStatusText, setSaveStatusText] = useState("");

  useEffect(() => {
    if (!lastSaved) {
      setSaveStatusText("");
      return;
    }
    const update = () => {
      const diff = Math.floor((Date.now() - lastSaved) / 1000);
      if (diff < 60) setSaveStatusText("Saved just now");
      else setSaveStatusText(`Saved ${Math.floor(diff / 60)}m ago`);
    };
    update();
    const interval = setInterval(update, 10000);
    return () => clearInterval(interval);
  }, [lastSaved]);

  const [scoreLoading, setScoreLoading] = useState(false);

  const [refineInstruction, setRefineInstruction] = useState("");
  const [refineLoading, setRefineLoading] = useState(false);
  const [refineError, setRefineError] = useState("");

  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [isWide, setIsWide] = useState(true);
  const [currentPostId, setCurrentPostId] = useState<number | null>(null);
  const [restored, setRestored] = useState(false);
  const [drawerOpen, setDrawerOpen] = useState(false);

  const topicRef = useRef<HTMLInputElement>(null);
  const analysisRef = useRef<HTMLDivElement>(null);

  // Responsive width detection
  useEffect(() => {
    const check = () => setIsWide(window.innerWidth >= 900);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

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

      const savedScored = sessionStorage.getItem(SS_SCORED);

      if (savedPost && savedScore && savedFeedback && savedIterations) {
        const restoredResult: GenerateResult = {
          post: savedPost,
          score: Number(savedScore),
          score_feedback: JSON.parse(savedFeedback),
          iterations: Number(savedIterations),
          // null = old session before lazy scoring — treat as scored for back-compat
          scored: savedScored === null ? true : savedScored === "true",
        };
        setResult(restoredResult);
        setEditedPost(savedPost);
        if (savedVisuals) {
          const parsedVisuals: Visual[] = JSON.parse(savedVisuals);
          setVisuals(parsedVisuals);
        }
        // Restore topic/format/tone so history saves correctly after restore
        const savedTopic = sessionStorage.getItem(SS_TOPIC);
        const savedFormat = sessionStorage.getItem(SS_FORMAT);
        const savedTone = sessionStorage.getItem(SS_TONE);
        if (savedTopic) setTopic(savedTopic);
        if (savedFormat) setFormat(savedFormat as Format);
        if (savedTone) setTone(savedTone as Tone);
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
        setAnalysisOpen(savedShowAnalysis === "true");
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
      sessionStorage.setItem(SS_TOPIC, topic);
      sessionStorage.setItem(SS_FORMAT, format);
      sessionStorage.setItem(SS_TONE, tone);
      sessionStorage.setItem(SS_SCORED, String(result.scored));
    } catch {
      // ignore
    }
  }, [result, editedPost, visuals, topic, format, tone]);

  // Persist analysisOpen preference
  useEffect(() => {
    try {
      sessionStorage.setItem(SS_SHOW_ANALYSIS, String(analysisOpen));
    } catch {
      // ignore
    }
  }, [analysisOpen]);

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
    [SS_POST, SS_SCORE, SS_FEEDBACK, SS_ITERATIONS, SS_VISUALS, SS_IDEAS, SS_CURRENT_POST_ID, SS_TOPIC, SS_FORMAT, SS_TONE, SS_SCORED].forEach((k) =>
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
      setLastSaved(Date.now());
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
      setLastSaved(Date.now());
    } catch {
      // patch failure is non-critical
    }
  };

  const handleScore = async () => {
    if (!result || scoreLoading) return;
    setScoreLoading(true);
    try {
      const res = await fetch(`${API}/score`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ post_content: editedPost }),
      });
      if (!res.ok) throw new Error("Scoring failed");
      const data: { score: number; score_feedback: string[] } = await res.json();
      setResult((prev) =>
        prev ? { ...prev, score: data.score, score_feedback: data.score_feedback, scored: true } : prev
      );
      try {
        sessionStorage.setItem(SS_SCORE, String(data.score));
        sessionStorage.setItem(SS_FEEDBACK, JSON.stringify(data.score_feedback));
        sessionStorage.setItem(SS_SCORED, "true");
      } catch {
        // ignore
      }
      await patchHistory({ authenticity_score: data.score });
    } catch {
      // scoring failure is non-critical — user can try again
    } finally {
      setScoreLoading(false);
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
    setAnalysisOpen(false);
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

  const handleRefineWith = async (instruction: string) => {
    setRefineError("");
    setRefineLoading(true);
    try {
      const res = await fetch(`${API}/refine`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_draft: editedPost,
          refinement_instruction: instruction,
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
      setRefineInstruction("");
    } catch (e: unknown) {
      setRefineError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setRefineLoading(false);
    }
  };

  const handleRefine = async () => {
    if (!refineInstruction.trim()) {
      setRefineError("Refinement instruction is required.");
      return;
    }
    await handleRefineWith(refineInstruction);
  };

  const handleApplyFeedback = async () => {
    if (!result || result.score_feedback.length === 0) return;
    const instruction =
      result.score_feedback.map((f) => f.trim().replace(/\.+$/, "")).join(". ") + ".";
    setRefineInstruction(instruction);
    await handleRefineWith(instruction);
  };

  const handleCopy = async () => {
    await navigator.clipboard.writeText(editedPost);
    setCopied(true);
    showToast("Post copied to clipboard", "success");
    setTimeout(() => setCopied(false), 2000);
  };

  const handleGenerateVisuals = async () => {
    setVisualsLoading(true);
    setVisualsVisible(true);
    setVisuals([]);
    setAnalysisOpen(false);

    // Ensure a history entry exists before generating visuals
    const existingPostId = currentPostId ?? (() => {
      try { return Number(sessionStorage.getItem(SS_CURRENT_POST_ID)) || null; } catch { return null; }
    })();
    if (!existingPostId && result) {
      await autoSavePost(result, editedPost);
    }

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

  // ─── Derived state ────────────────────────────────────────────────────────

  const postGenerated = !!result;
  const splitActive = postGenerated && analysisOpen && isWide && !visualsVisible;

  const scoreColor = result
    ? result.score >= 80 ? "#4a7a4a" : result.score >= 60 ? "#1a1918" : "#6b6862"
    : "#6b6862";
  const scoreStatus = result
    ? result.score >= 80
      ? "Good"
      : result.score >= 60
        ? "Needs work"
        : "Needs revision"
    : "";

  // ─── Analysis panel content (reused in split right panel and stacked mobile) ─

  const analysisPanelContent = result ? (
    scoreLoading ? (
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", justifyContent: "center", padding: "64px 0", gap: 12 }}>
        <div style={{ width: 20, height: 20, border: "2px solid #e0dcd3", borderTopColor: "#1a1918", borderRadius: "50%", animation: "spin 0.8s linear infinite" }} />
        <p style={{ fontSize: 13, color: "#969288" }}>Scoring post…</p>
      </div>
    ) : result.scored ? (
    <div ref={analysisRef}>

      {/* Score header row */}
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start", marginBottom: 24 }}>
        <div>
          <span style={{ fontSize: 40, fontWeight: 500, color: scoreColor, lineHeight: 1, display: "block" }}>
            {result.score}
          </span>
          <p style={{ fontSize: 12, color: "#969288", marginTop: 4 }}>out of 100</p>
        </div>
        <div style={{ textAlign: "right" }}>
          <p style={{ fontSize: 13, fontWeight: 500, color: "#1a1918" }}>{scoreStatus}</p>
          <p style={{ fontSize: 11, color: "#969288", marginTop: 3 }}>
            {result.iterations} humanizer pass{result.iterations !== 1 ? "es" : ""}
          </p>
        </div>
      </div>

      {/* Progress bar */}
      <div
        style={{
          width: "100%",
          height: 4,
          borderRadius: 20,
          background: "#e0dcd3",
          marginBottom: 24,
          overflow: "hidden",
        }}
      >
        <div
          style={{
            width: `${result.score}%`,
            height: "100%",
            borderRadius: 20,
            background: scoreColor,
            transition: "width 0.7s",
          }}
        />
      </div>

      {/* Divider before feedback */}
      <div style={{ borderTop: "0.5px solid #e0dcd3", marginBottom: 20 }} />

      {/* What to fix */}
      {result.score_feedback.length > 0 && (
        <>
          <p
            style={{
              fontSize: 10.5,
              fontWeight: 500,
              textTransform: "uppercase",
              letterSpacing: "0.07em",
              color: "#969288",
              marginBottom: 14,
            }}
          >
            WHAT TO FIX
          </p>
          <div>
            {result.score_feedback.map((f, i) => (
              <div
                key={i}
                style={{
                  display: "flex",
                  gap: 10,
                  padding: "10px 0",
                  borderBottom:
                    i < result.score_feedback.length - 1 ? "0.5px solid #ebe7df" : "none",
                }}
              >
                <span style={{ color: "#969288", flexShrink: 0, fontSize: 13, marginTop: 1 }}>—</span>
                <p style={{ fontSize: 13.5, lineHeight: 1.65, color: "#6b6862" }}>{f}</p>
              </div>
            ))}
          </div>
        </>
      )}

      {/* Divider before refine */}
      <div style={{ borderTop: "0.5px solid #e0dcd3", marginTop: 4, marginBottom: 20 }} />

      {/* Refine box */}
      <p
        style={{
          fontSize: 10.5,
          fontWeight: 500,
          textTransform: "uppercase",
          color: "#969288",
          letterSpacing: "0.07em",
          marginBottom: 12,
        }}
      >
        REFINE DRAFT
      </p>
      <textarea
        value={refineInstruction}
        onChange={(e) => setRefineInstruction(e.target.value)}
        placeholder="Describe what to fix — or leave blank to auto-apply the feedback above..."
        style={{
          width: "100%",
          minHeight: 90,
          fontSize: 13,
          lineHeight: 1.6,
          border: "0.5px solid #e0dcd3",
          borderRadius: 8,
          padding: "12px 14px",
          resize: "vertical",
          fontFamily: "inherit",
          background: "#ffffff",
          color: "#1a1918",
          outline: "none",
          boxSizing: "border-box",
          marginBottom: 12,
        }}
      />
      {refineError && (
        <p style={{ fontSize: 12, color: "#b34e4e", marginTop: -8, marginBottom: 8 }}>{refineError}</p>
      )}
      <div style={{ display: "flex", gap: 8 }}>
        <button
          onClick={handleApplyFeedback}
          disabled={refineLoading}
          style={{
            flex: 1,
            borderRadius: 8,
            background: "#1a1918",
            color: "#ffffff",
            fontSize: 13,
            fontWeight: 500,
            padding: "11px 0",
            border: "none",
            cursor: refineLoading ? "not-allowed" : "pointer",
            opacity: refineLoading ? 0.6 : 1,
            transition: "opacity 0.15s",
          }}
        >
          {refineLoading ? "Refining…" : "Apply feedback"}
        </button>
        <button
          onClick={handleRefine}
          disabled={refineLoading}
          style={{
            flex: 1,
            borderRadius: 8,
            border: "0.5px solid #e0dcd3",
            background: "#ffffff",
            color: "#6b6862",
            fontSize: 13,
            fontWeight: 500,
            padding: "11px 0",
            cursor: refineLoading ? "not-allowed" : "pointer",
            opacity: refineLoading ? 0.6 : 1,
            transition: "opacity 0.15s",
          }}
        >
          Refine with note
        </button>
      </div>
    </div>
    ) : null
  ) : null;

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      className={splitActive ? "" : "-mx-8 -mt-10 -mb-10 bg-page flex flex-col"}
      style={
        splitActive
          ? {
              position: "fixed",
              top: 0,
              left: "14rem",
              right: 0,
              bottom: 0,
              display: "flex",
              flexDirection: "column",
              background: "#faf9f7",
              zIndex: 10,
            }
          : { minHeight: "100vh" }
      }
    >

      {/* Topbar */}
      <div
        style={{ borderBottom: "0.5px solid #e0dcd3", height: "52px" }}
        className="flex items-center px-8 bg-page shrink-0"
      >
        <div className="flex items-baseline gap-3">
          <span className="text-sm font-medium text-text-primary">Create Post</span>
          <span className="text-xs text-text-muted">
            {loading
              ? "Generating your draft…"
              : !postGenerated
                ? "Set up your post"
                : "Review and refine"}
          </span>
        </div>
      </div>

      {/* ── Split layout (wide viewport, post generated, analysis open) ─────── */}
      {splitActive ? (
        <div style={{ display: "flex", flex: 1, overflow: "hidden" }}>

          {/* Left panel — post */}
          <div
            style={{
              flex: 1,
              minWidth: 0,
              overflow: "hidden",
              padding: "32px 40px",
              borderRight: "0.5px solid #e0dcd3",
              display: "flex",
              flexDirection: "column",
            }}
          >
            {/* Topic header */}
            {topic && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 12, flexShrink: 0 }}>
                <span style={{ fontSize: 10.5, fontWeight: 500, letterSpacing: "0.08em", textTransform: "uppercase", color: "#969288", flexShrink: 0 }}>
                  TOPIC
                </span>
                <span style={{ fontSize: 14, fontWeight: 500, color: "#1a1918", lineHeight: 1.4 }}>
                  {topic}
                </span>
              </div>
            )}

            {/* Post box — fills remaining space */}
            <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
              <div
                className="rounded-2xl border border-border-subtle bg-card shadow-card focus-within:shadow-card-hover focus-within:border-border transition-all duration-300"
                style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "32px 36px" }}
              >
                <textarea
                  value={editedPost}
                  onChange={(e) => setEditedPost(e.target.value)}
                  className="w-full h-full resize-none outline-none bg-transparent"
                  style={{ fontSize: 16, lineHeight: 1.8, color: "#1a1918", fontFamily: "inherit", border: "none", display: "block" }}
                />
              </div>
            </div>

            {/* Action row */}
            <div className="flex gap-2 flex-shrink-0 mt-3">
              {(
                [
                  { label: copied ? "Copied!" : "Copy", onClick: handleCopy, disabled: false },
                  { label: visuals.length > 0 ? "View visuals" : "Generate visuals", onClick: visuals.length > 0 ? () => { setVisualsVisible(true); setAnalysisOpen(false); } : handleGenerateVisuals, disabled: visualsLoading },
                  { label: "Regenerate", onClick: () => generate(), disabled: loading },
                  { label: "Hide analysis", onClick: () => setAnalysisOpen(false), disabled: false },
                ] as { label: string; onClick: () => void; disabled: boolean }[]
              ).map(({ label, onClick, disabled }) => (
                <button
                  key={label}
                  onClick={onClick}
                  disabled={disabled}
                  className="flex-1 rounded-xl border border-border-subtle text-text-secondary font-semibold hover:border-border hover:text-text-primary hover:shadow-card transition-all duration-200 bg-card disabled:opacity-50"
                  style={{ padding: "10px 18px", fontSize: 13 }}
                >
                  {label}
                </button>
              ))}
            </div>

            <p className="text-xs text-text-hint flex-shrink-0 mt-2">{lastSaved ? saveStatusText : "Auto-saved to history"}</p>
          </div>

          {/* Right panel — analysis */}
          <div
            style={{
              width: 480,
              flexShrink: 0,
              overflowY: "auto",
              padding: "28px 36px",
              background: "#faf9f7",
            }}
          >
            {analysisPanelContent}
          </div>
        </div>

      ) : postGenerated && !loading && !visualsVisible ? (
        // ── Full-height writing surface (single column, post state) ─────────
        <div style={{ height: "calc(100vh - 52px)", display: "flex", flexDirection: "column", overflow: "hidden" }}>
          <div style={{ maxWidth: 780, margin: "0 auto", width: "100%", height: "100%", display: "flex", flexDirection: "column", padding: "24px 32px" }}>

            {/* Restored session banner */}
            {restored && (
              <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-2.5" style={{ flexShrink: 0, marginBottom: 12 }}>
                <p className="text-xs text-text-secondary">Restored your last session</p>
                <button
                  onClick={() => {
                    clearSession();
                    setResult(null);
                    setEditedPost("");
                    setVisuals([]);
                    setVisualsVisible(false);
                    setAnalysisOpen(false);
                  }}
                  className="text-text-muted hover:text-text-secondary text-xl leading-none ml-4"
                  aria-label="Dismiss"
                >
                  ×
                </button>
              </div>
            )}

            {/* Post meta row */}
            <div className="flex items-center justify-between" style={{ flexShrink: 0, marginBottom: 12 }}>
              <div className="flex items-center gap-2">
                <span className="text-xs px-2 py-0.5 rounded-full bg-stat border border-border text-text-muted">
                  {FORMAT_BADGE[format] ?? format}
                </span>
                <span className="text-xs text-text-muted capitalize">{tone}</span>
              </div>
              <button
                onClick={() => { setResult(null); setEditedPost(""); setAnalysisOpen(false); }}
                className="text-xs text-text-muted hover:text-text-secondary transition-colors"
              >
                ← Start over
              </button>
            </div>

            {/* Topic header */}
            {topic && (
              <div style={{ display: "flex", alignItems: "baseline", gap: 10, marginBottom: 12, flexShrink: 0 }}>
                <span style={{ fontSize: 10.5, fontWeight: 500, letterSpacing: "0.08em", textTransform: "uppercase", color: "#969288", flexShrink: 0 }}>TOPIC</span>
                <span style={{ fontSize: 14, fontWeight: 500, color: "#1a1918", lineHeight: 1.4 }}>{topic}</span>
              </div>
            )}

            {/* Post box — fills all remaining space */}
            <div style={{ flex: 1, minHeight: 0, display: "flex", flexDirection: "column" }}>
              <div
                className="rounded-2xl border border-border-subtle bg-card shadow-card focus-within:shadow-card-hover focus-within:border-border transition-all duration-300"
                style={{ flex: 1, minHeight: 0, overflowY: "auto", padding: "32px 36px" }}
              >
                <textarea
                  value={editedPost}
                  onChange={(e) => setEditedPost(e.target.value)}
                  className="w-full h-full resize-none outline-none bg-transparent"
                  style={{ fontSize: 16, lineHeight: 1.8, color: "#1a1918", fontFamily: "inherit", border: "none", display: "block" }}
                />
              </div>
            </div>

            {/* Action row */}
            <div className="flex gap-2 flex-wrap" style={{ flexShrink: 0, marginTop: 12 }}>
              <button
                onClick={handleCopy}
                className="flex-1 rounded-lg border border-border text-text-secondary font-medium hover:border-text-primary hover:text-text-primary transition-colors bg-card"
                style={{ padding: "10px 18px", fontSize: 13 }}
              >
                {copied ? "Copied!" : "Copy"}
              </button>
              <button
                onClick={visuals.length > 0 ? () => { setVisualsVisible(true); setAnalysisOpen(false); } : handleGenerateVisuals}
                disabled={visualsLoading}
                className="flex-1 rounded-xl border border-border-subtle text-text-secondary font-semibold hover:border-border hover:text-text-primary hover:shadow-card transition-all duration-200 bg-card disabled:opacity-50"
                style={{ padding: "10px 18px", fontSize: 13 }}
              >
                {visuals.length > 0 ? "View visuals" : "Generate visuals"}
              </button>
              <button
                onClick={() => generate()}
                disabled={loading}
                className="flex-1 rounded-xl border border-border-subtle text-text-secondary font-semibold hover:border-border hover:text-text-primary hover:shadow-card transition-all duration-200 bg-card disabled:opacity-50"
                style={{ padding: "10px 18px", fontSize: 13 }}
              >
                Regenerate
              </button>
              <button
                onClick={() => {
                  setAnalysisOpen(true);
                  if (!result?.scored && !scoreLoading) {
                    handleScore();
                  } else if (!isWide) {
                    setTimeout(() => analysisRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
                  }
                }}
                disabled={scoreLoading}
                className="flex-1 rounded-lg border border-border text-text-secondary font-medium hover:border-text-primary hover:text-text-primary transition-colors bg-card disabled:opacity-50"
                style={{ padding: "10px 18px", fontSize: 13 }}
              >
                {result?.scored ? "View authenticity analysis" : scoreLoading ? "Scoring…" : "Score this post"}
              </button>
            </div>

            <p className="text-xs text-text-hint" style={{ flexShrink: 0, marginTop: 8 }}>{lastSaved ? saveStatusText : "Auto-saved to history"}</p>

            {/* Analysis stacked below post (narrow viewport only) */}
            {analysisOpen && !isWide && (
              <div
                ref={analysisRef}
                style={{ marginTop: 24, paddingTop: 24, borderTop: "0.5px solid #e0dcd3", flexShrink: 0 }}
              >
                {analysisPanelContent}
              </div>
            )}

          </div>
        </div>

      ) : (
        // ── Scrollable column (configure / spinner / visuals) ────────────────
        <div className="flex-1 overflow-y-auto">
          <div style={{ maxWidth: 780, margin: "0 auto", padding: "32px 40px" }}>

            {/* Restored session banner */}
            {restored && !loading && (
              <div className="flex items-center justify-between rounded-lg border border-border bg-surface px-4 py-2.5 mb-6">
                <p className="text-xs text-text-secondary">Restored your last session</p>
                <button
                  onClick={() => {
                    clearSession();
                    setResult(null);
                    setEditedPost("");
                    setVisuals([]);
                    setVisualsVisible(false);
                    setAnalysisOpen(false);
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
              <div className="rounded-lg border border-border bg-card overflow-hidden mb-6">
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

            {/* ── Configure form ──────────────────────────────────────────── */}
            {!postGenerated && !loading && (
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
                    className="w-full rounded-xl border border-border-subtle bg-card px-4 py-3 text-[15px] font-medium text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary shadow-sm focus-within:shadow-md focus-within:border-border transition-all duration-200"
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
                        className={`flex-1 px-4 py-2.5 rounded-xl text-[14px] font-semibold border transition-all duration-200 ${
                          format === f.id
                            ? "border-text-primary bg-surface text-text-primary shadow-sm ring-1 ring-text-primary ring-opacity-10"
                            : "border-border-subtle text-text-secondary hover:text-text-primary hover:bg-surface hover:border-border bg-card shadow-sm"
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
                        className={`flex-1 px-4 py-3 rounded-xl text-sm border transition-all duration-200 text-left ${
                          tone === t.id
                            ? "border-text-primary bg-surface text-text-primary shadow-sm ring-1 ring-text-primary ring-opacity-10"
                            : "border-border-subtle text-text-secondary hover:text-text-primary hover:bg-surface hover:border-border bg-card shadow-sm"
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
                    className="w-full rounded-xl border border-border-subtle bg-card px-4 py-3 text-[15px] text-text-primary placeholder:text-text-hint focus:outline-none focus:border-text-primary resize-none shadow-sm focus-within:shadow-md focus-within:border-border transition-all duration-200"
                  />
                </div>

                {error && <p className="text-sm text-score-red">{error}</p>}

                <button
                  onClick={() => generate()}
                  disabled={loading}
                  className="w-full rounded-xl bg-amber text-white font-bold tracking-wide py-3.5 text-[15px] hover:opacity-90 disabled:opacity-50 disabled:cursor-not-allowed shadow-float hover:shadow-card-hover hover:-translate-y-0.5 transition-all duration-200"
                >
                  Generate
                </button>
              </div>
            )}

            {/* ── Generating spinner ──────────────────────────────────────── */}
            {loading && (
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

            {/* ── Visuals ─────────────────────────────────────────────────── */}
            {postGenerated && !loading && visualsVisible && (
              <div className="space-y-5">
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
      )}

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
