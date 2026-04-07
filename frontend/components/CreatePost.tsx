"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi } from "@/lib/api";

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
const SS_LENGTH = "contentOS_last_length";
const SS_SCORED = "contentOS_last_scored";


type Format = "linkedin post" | "medium article" | "thread";
type Tone = "casual" | "technical" | "storytelling";
type Length = "concise" | "standard" | "long-form";

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

const TONE_DISPLAY_LABELS: Record<Tone, string> = {
  casual: "Casual",
  technical: "Technical",
  storytelling: "Storytelling",
};

const TONE_DESCRIPTIONS: Record<Tone, string> = {
  casual: "Conversational and direct. First-person, short sentences. Focus on clarity and utility.",
  technical: "Precise and substantive. Uses domain language without over-explaining. Respects expertise.",
  storytelling: "Narrative-first. Opens with a moment, builds tension, lands on a lesson.",
};

const LENGTHS: { id: Length; label: string }[] = [
  { id: "concise", label: "Concise" },
  { id: "standard", label: "Standard" },
  { id: "long-form", label: "Long-form" },
];

const LENGTH_META: Record<Format, Record<Length, string>> = {
  "linkedin post": {
    concise: "~100-150 words",
    standard: "~200-300 words",
    "long-form": "~400-600 words",
  },
  "medium article": {
    concise: "~350-500 words",
    standard: "~700-900 words",
    "long-form": "~1200-1600 words",
  },
  thread: {
    concise: "4-5 tweets",
    standard: "7-9 tweets",
    "long-form": "11-14 tweets",
  },
};

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

// ─── Markdown stripping ───────────────────────────────────────────────────────

function stripMarkdown(text: string): string {
  return text
    .replace(/\[([^\]]+)\]\([^)]+\)/g, "$1")
    .replace(/\*\*([^*]+)\*\*/g, "$1")
    .replace(/__([^_]+)__/g, "$1")
    .replace(/\*([^*\n]+)\*/g, "$1")
    .replace(/_([^_\n]+)_/g, "$1")
    .replace(/`([^`]+)`/g, "$1")
    .replace(/^#{1,6}\s+/gm, "");
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
    if (!ctx) {
      reject(new Error("No canvas context"));
      return;
    }

    const img = new Image();
    const blob = new Blob([svgCode], { type: "image/svg+xml" });
    const url = URL.createObjectURL(blob);

    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      URL.revokeObjectURL(url);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => {
      URL.revokeObjectURL(url);
      reject(new Error("Image load failed"));
    };
    img.src = url;
  });
}

function getSelectionOffsetsWithin(node: HTMLElement) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;

  const range = selection.getRangeAt(0);
  if (!node.contains(range.commonAncestorContainer)) return null;

  const preRange = document.createRange();
  preRange.selectNodeContents(node);
  preRange.setEnd(range.startContainer, range.startOffset);

  const selectedText = range.toString();
  const start = preRange.toString().length;

  return {
    start,
    end: start + selectedText.length,
    text: selectedText,
  };
}

function DiagramCard({ visual }: { visual: Visual }) {
  const [pngState, setPngState] = useState<"idle" | "opened" | "blocked">("idle");
  const [fallbackDataURL, setFallbackDataURL] = useState<string | null>(null);

  if (!visual.svg_code) {
    return (
      <div className="rounded-xl border border-error-container bg-error-container/20 px-5 py-4">
        <p className="text-sm font-medium text-error">
          Diagram generation failed — try regenerating the post
        </p>
        <p className="text-xs text-error opacity-70 mt-1">{visual.description}</p>
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
    <div className="rounded-xl border border-surface-container-high bg-surface-container-lowest overflow-hidden">
      <div className="px-5 py-3 border-b border-surface-container-high">
        <p className="text-sm font-medium text-secondary">
          Diagram —{" "}
          <span className="font-normal text-outline">
            {visual.description.length > 60
              ? visual.description.slice(0, 60) + "…"
              : visual.description}
          </span>
        </p>
      </div>
      <div className="p-4 overflow-x-auto" dangerouslySetInnerHTML={{ __html: visual.svg_code }} />
      <div className="px-5 py-3 border-t border-surface-container-high space-y-2">
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpen}
            className="text-xs border border-surface-container-high rounded-lg px-3 py-1.5 text-secondary hover:border-outline-variant hover:text-on-surface transition-colors"
          >
            Open as PNG
          </button>
          {pngState === "opened" && (
            <span className="text-xs text-outline">
              PNG opened in new tab — right-click and <strong>Save Image</strong>
            </span>
          )}
          {pngState === "blocked" && (
            <span className="text-xs text-outline">
              Popup blocked — right-click the image below and <strong>Save Image</strong>
            </span>
          )}
        </div>
        {pngState === "blocked" && fallbackDataURL && (
          // eslint-disable-next-line @next/next/no-img-element
          <img src={fallbackDataURL} alt="diagram PNG" className="max-w-full rounded-xl border border-surface-container-high" />
        )}
      </div>
    </div>
  );
}

function ImageReminderCard({ visual }: { visual: Visual }) {
  return (
    <div className="rounded-xl border-2 border-dashed border-outline-variant bg-surface-container px-5 py-4 space-y-1">
      <p className="label-caps text-outline-variant">
        Add your own visual
      </p>
      <p className="text-sm text-outline leading-relaxed">{visual.reminder_text}</p>
    </div>
  );
}

// ─── Settings Drawer ──────────────────────────────────────────────────────────

interface DrawerProps {
  initialTopic: string;
  initialFormat: Format;
  initialTone: Tone;
  initialLength: Length;
  initialContext: string;
  onCancel: () => void;
  onRegenerate: (overrides: { topic: string; format: Format; tone: Tone; length: Length; context: string }) => void;
}

function SettingsDrawer({ initialTopic, initialFormat, initialTone, initialLength, initialContext, onCancel, onRegenerate }: DrawerProps) {
  const [dTopic, setDTopic] = useState(initialTopic);
  const [dFormat, setDFormat] = useState<Format>(initialFormat);
  const [dTone, setDTone] = useState<Tone>(initialTone);
  const [dLength, setDLength] = useState<Length>(initialLength);
  const [dContext, setDContext] = useState(initialContext);

  return (
    <>
      {/* Backdrop */}
      <div
        className="fixed inset-0 bg-black/10 z-40"
        onClick={onCancel}
      />
      {/* Drawer panel */}
      <div className="fixed top-0 right-0 h-full w-80 bg-background border-l border-surface-container-high z-50 flex flex-col shadow-card">
        {/* Header */}
        <div
          style={{ borderBottom: "0.5px solid #dfe3e2", height: "52px" }}
          className="flex items-center justify-between px-5 shrink-0"
        >
          <p className="text-sm font-medium text-on-surface font-headline">Regenerate settings</p>
          <button
            onClick={onCancel}
            className="text-outline hover:text-on-surface transition-colors text-xl leading-none"
            aria-label="Close"
          >
            ×
          </button>
        </div>

        {/* Body */}
        <div className="flex-1 overflow-y-auto px-5 py-6 space-y-6">
          {/* Topic */}
          <div>
            <label className="label-caps text-secondary block mb-2">Topic</label>
            <input
              type="text"
              value={dTopic}
              onChange={(e) => setDTopic(e.target.value)}
              placeholder="What do you want to write about?"
              className="input-editorial w-full px-0 py-2 text-sm font-medium text-on-surface placeholder:text-outline-variant focus:outline-none"
            />
          </div>

          {/* Format */}
          <div>
            <label className="label-caps text-secondary block mb-2">Format</label>
            <div className="space-y-1.5">
              {FORMATS.map((f) => (
                <button
                  key={f.id}
                  onClick={() => setDFormat(f.id)}
                  className={`w-full px-3 py-2 rounded-lg text-sm text-left transition-colors ${
                    dFormat === f.id
                      ? "btn-primary text-white font-medium"
                      : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
                  }`}
                >
                  {f.label}
                </button>
              ))}
            </div>
          </div>

          {/* Tone */}
          <div>
            <label className="label-caps text-secondary block mb-2">Tone</label>
            <div className="space-y-1.5">
              {TONES.map((t) => (
                <button
                  key={t.id}
                  onClick={() => setDTone(t.id)}
                  className={`w-full px-3 py-2.5 rounded-lg text-sm text-left transition-colors ${
                    dTone === t.id
                      ? "btn-primary text-white"
                      : "bg-surface-container text-secondary hover:bg-surface-container-high hover:text-on-surface"
                  }`}
                >
                  <div className="font-medium">{t.label}</div>
                  <div className={`text-xs mt-0.5 ${dTone === t.id ? "text-white/70" : "text-outline"}`}>
                    {t.description}
                  </div>
                </button>
              ))}
            </div>
          </div>

          {/* Length */}
          <div>
            <label className="label-caps text-secondary block mb-2">Length</label>
            <div className="flex flex-wrap gap-2">
              {LENGTHS.map((l) => (
                <button
                  key={l.id}
                  onClick={() => setDLength(l.id)}
                  className={`px-4 py-2 rounded-lg text-[13px] transition-all border ${
                    dLength === l.id
                      ? "btn-primary text-white border-transparent font-medium"
                      : "border-outline-variant text-secondary hover:border-outline hover:text-on-surface bg-transparent"
                  }`}
                >
                  {l.label}
                </button>
              ))}
            </div>
          </div>

          {/* Context */}
          <div>
            <label className="label-caps text-secondary block mb-2">
              Additional context{" "}
              <span className="normal-case font-normal text-outline-variant">(optional)</span>
            </label>
            <textarea
              value={dContext}
              onChange={(e) => setDContext(e.target.value)}
              placeholder="Specific angle, story, or data point..."
              rows={3}
              className="input-editorial w-full px-0 py-2 text-sm text-on-surface placeholder:text-outline-variant focus:outline-none resize-none"
            />
          </div>
        </div>

        {/* Footer */}
        <div
          style={{ borderTop: "0.5px solid #dfe3e2" }}
          className="px-5 py-4 flex gap-2 shrink-0"
        >
          <button
            onClick={onCancel}
            className="flex-1 rounded-lg border border-surface-container-high text-secondary text-sm py-2 hover:border-outline-variant hover:text-on-surface transition-colors bg-surface-container-lowest"
          >
            Cancel
          </button>
          <button
            onClick={() => onRegenerate({ topic: dTopic, format: dFormat, tone: dTone, length: dLength, context: dContext })}
            className="flex-1 btn-primary rounded-lg text-white text-sm font-medium py-2 hover:opacity-90 transition-opacity"
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
  const api = useApi();
  const [topic, setTopic] = useState("");
  const [format, setFormat] = useState<Format>("linkedin post");
  const [tone, setTone] = useState<Tone>("casual");
  const [length, setLength] = useState<Length>("standard");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [editedPost, setEditedPost] = useState("");
  const [error, setError] = useState("");
  const [copiedLinkedIn, setCopiedLinkedIn] = useState(false);
  const [copiedMedium, setCopiedMedium] = useState(false);

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
  const [toneDescOpacity, setToneDescOpacity] = useState(0);

  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [splitRatio, setSplitRatio] = useState(0.55);
  const [isWide, setIsWide] = useState(true);
  const [currentPostId, setCurrentPostId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showInterstitial, setShowInterstitial] = useState(false);
  const [interstitialTopic, setInterstitialTopic] = useState("");
  const [interstitialScore, setInterstitialScore] = useState(0);

  const [inlineSelection, setInlineSelection] = useState<{
    start: number;
    end: number;
    text: string;
    rect: DOMRect | null;
  } | null>(null);
  const [inlineInstruction, setInlineInstruction] = useState("");
  const [inlineLoading, setInlineLoading] = useState(false);

  const topicRef = useRef<HTMLTextAreaElement>(null);
  const analysisRef = useRef<HTMLDivElement>(null);
  const inlineInputRef = useRef<HTMLInputElement>(null);
  const postEditorRef = useRef<HTMLDivElement>(null);
  const splitContainerRef = useRef<HTMLDivElement>(null);

  // Responsive width detection
  useEffect(() => {
    const check = () => setIsWide(window.innerWidth >= 900);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  // On mount: show interstitial if a saved post exists, else go to idle with prefill
  useEffect(() => {
    try {
      const savedLength = sessionStorage.getItem(SS_LENGTH);
      if (savedLength === "concise" || savedLength === "standard" || savedLength === "long-form") {
        setLength(savedLength);
      }

      const savedPost = sessionStorage.getItem(SS_POST);
      if (savedPost) {
        // A saved post exists — show the interstitial and defer all restoration
        setInterstitialTopic(sessionStorage.getItem(SS_TOPIC) || "");
        setInterstitialScore(Number(sessionStorage.getItem(SS_SCORE)) || 0);
        setShowInterstitial(true);

        // Restore non-post preferences immediately (ideas panel, analysis open state)
        const savedIdeas = sessionStorage.getItem(SS_IDEAS);
        if (savedIdeas) {
          try {
            const parsedIdeas: Suggestion[] = JSON.parse(savedIdeas);
            if (parsedIdeas.length > 0) { setSuggestions(parsedIdeas); setSuggestionsVisible(true); }
          } catch { /* ignore */ }
        }
        const savedShowAnalysis = sessionStorage.getItem(SS_SHOW_ANALYSIS);
        if (savedShowAnalysis !== null) setAnalysisOpen(savedShowAnalysis === "true");
      } else {
        // No saved post — idle state; apply any prefill from Ideas screen
        const savedIdeas = sessionStorage.getItem(SS_IDEAS);
        if (savedIdeas) {
          try {
            const parsedIdeas: Suggestion[] = JSON.parse(savedIdeas);
            if (parsedIdeas.length > 0) { setSuggestions(parsedIdeas); setSuggestionsVisible(true); }
          } catch { /* ignore */ }
        }
        const savedShowAnalysis = sessionStorage.getItem(SS_SHOW_ANALYSIS);
        if (savedShowAnalysis !== null) setAnalysisOpen(savedShowAnalysis === "true");

        const prefillTopic = sessionStorage.getItem("contentOS_last_topic");
        const prefillFormat = sessionStorage.getItem("contentOS_prefill_format");
        if (prefillTopic) setTopic(prefillTopic);
        if (prefillFormat) setFormat(prefillFormat as Format);
        sessionStorage.removeItem("contentOS_last_topic");
        sessionStorage.removeItem("contentOS_prefill_format");
      }
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
      sessionStorage.setItem(SS_LENGTH, length);
      sessionStorage.setItem(SS_SCORED, String(result.scored));
    } catch {
      // ignore
    }
  }, [result, editedPost, visuals, topic, format, tone, length]);

  // Persist analysisOpen preference
  useEffect(() => {
    try {
      sessionStorage.setItem(SS_SHOW_ANALYSIS, String(analysisOpen));
    } catch {
      // ignore
    }
  }, [analysisOpen]);

  // Fade tone description in when tone changes
  useEffect(() => {
    setToneDescOpacity(0);
    const t = setTimeout(() => setToneDescOpacity(1), 50);
    return () => clearTimeout(t);
  }, [tone]);

  useEffect(() => {
    if (!editedPost) return;

    const frame = requestAnimationFrame(() => {
      const editor = postEditorRef.current;
      if (editor && editor.innerText !== editedPost) {
        editor.innerText = editedPost;
      }
    });

    return () => cancelAnimationFrame(frame);
  // analysisOpen + isWide + visualsVisible together determine which branch (split vs single-column)
  // is rendered. loading gates post-gen mount after generate, so include it to re-run sync on mount.
  }, [editedPost, analysisOpen, isWide, visualsVisible, loading]);

  const clearSession = () => {
    [SS_POST, SS_SCORE, SS_FEEDBACK, SS_ITERATIONS, SS_VISUALS, SS_IDEAS, SS_CURRENT_POST_ID, SS_TOPIC, SS_FORMAT, SS_TONE, SS_LENGTH, SS_SCORED].forEach((k) =>
      sessionStorage.removeItem(k)
    );
    setCurrentPostId(null);
    setSuggestions([]);
    setSuggestionsVisible(false);
    setSelectedIdeaIndex(null);
  };

  // Restore full session from storage — called when user clicks "Continue editing"
  const handleContinueEditing = () => {
    try {
      const savedPost = sessionStorage.getItem(SS_POST);
      const savedScore = sessionStorage.getItem(SS_SCORE);
      const savedFeedback = sessionStorage.getItem(SS_FEEDBACK);
      const savedIterations = sessionStorage.getItem(SS_ITERATIONS);
      const savedVisuals = sessionStorage.getItem(SS_VISUALS);
      const savedScored = sessionStorage.getItem(SS_SCORED);
      const savedTopic = sessionStorage.getItem(SS_TOPIC);
      const savedFormat = sessionStorage.getItem(SS_FORMAT);
      const savedTone = sessionStorage.getItem(SS_TONE);
      const savedLength = sessionStorage.getItem(SS_LENGTH);
      const savedPostId = sessionStorage.getItem(SS_CURRENT_POST_ID);

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
          try { setVisuals(JSON.parse(savedVisuals)); } catch { /* ignore */ }
        }
        if (savedTopic) setTopic(savedTopic);
        if (savedFormat) setFormat(savedFormat as Format);
        if (savedTone) setTone(savedTone as Tone);
        if (savedLength === "concise" || savedLength === "standard" || savedLength === "long-form") {
          setLength(savedLength);
        }
        if (savedPostId) setCurrentPostId(Number(savedPostId));
      }
    } catch {
      // corrupt storage — fall through to idle
    }
    setShowInterstitial(false);
  };

  // Discard saved session and start blank — called when user clicks "Start fresh"
  const handleStartFresh = () => {
    [SS_POST, SS_SCORE, SS_FEEDBACK, SS_ITERATIONS, SS_VISUALS, SS_IDEAS,
     SS_CURRENT_POST_ID, SS_TOPIC, SS_FORMAT, SS_TONE, SS_LENGTH, SS_SCORED, SS_SHOW_ANALYSIS].forEach((k) =>
      sessionStorage.removeItem(k)
    );
    sessionStorage.removeItem("contentOS_last_topic");

    const prefillFormat = sessionStorage.getItem("contentOS_prefill_format");
    if (prefillFormat) {
      setFormat(prefillFormat as Format);
      sessionStorage.removeItem("contentOS_prefill_format");
    }

    setResult(null);
    setEditedPost("");
    setLength("standard");
    setVisuals([]);
    setVisualsVisible(false);
    setAnalysisOpen(false);
    setCurrentPostId(null);
    setSuggestions([]);
    setSuggestionsVisible(false);
    setSelectedIdeaIndex(null);
    setShowInterstitial(false);
  };

  const autoSavePost = async (data: GenerateResult, postContent: string) => {
    try {
      const res = await api.logPost({
        topic,
        format,
        tone,
        content: postContent,
        authenticity_score: data.score,
        svg_diagrams: null,
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
      await api.patchPost(postId, fields);
      setLastSaved(Date.now());
    } catch {
      // patch failure is non-critical
    }
  };

  const handleScore = async () => {
    if (!result || scoreLoading) return;
    setScoreLoading(true);
    try {
      const res = await api.scorePost(editedPost);
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
    length?: Length;
    context?: string;
  }) => {
    const t = overrides?.topic ?? topic;
    const f = overrides?.format ?? format;
    const tn = overrides?.tone ?? tone;
    const len = overrides?.length ?? length;
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
    if (overrides?.length !== undefined) setLength(overrides.length);
    if (overrides?.context !== undefined) setContext(overrides.context);

    try {
      const res = await api.generatePost({ topic: t, format: f, tone: tn, length: len, context: ctx });

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

  const handlePostEditorSelection = () => {
    const el = postEditorRef.current;
    if (!el) return;

    const domSelection = window.getSelection();
    const selection = getSelectionOffsetsWithin(el);
    if (!selection) {
      setInlineSelection(null);
      return;
    }

    const rect = domSelection && domSelection.rangeCount > 0 ? domSelection.getRangeAt(0).getBoundingClientRect() : null;
    setInlineSelection({
      start: selection.start,
      end: selection.end,
      text: selection.text,
      rect,
    });
  };

  const handlePostEditorInput = (e: React.FormEvent<HTMLDivElement>) => {
    const nextValue = e.currentTarget.innerText.replace(/\u00a0/g, " ");
    setEditedPost(nextValue);
  };

  const handleInlineEdit = async () => {
    if (!inlineSelection || !inlineInstruction.trim() || inlineLoading) return;
    setInlineLoading(true);
    try {
      const result = await api.refineSelection(
        inlineSelection.text,
        inlineInstruction,
        editedPost
      );
      const rewrittenText = result.rewritten_text;
      const newPost =
        editedPost.slice(0, inlineSelection.start) +
        rewrittenText +
        editedPost.slice(inlineSelection.end);

      setEditedPost(newPost);
      try {
        sessionStorage.setItem(SS_POST, newPost);
        sessionStorage.setItem("contentOS_last_post", newPost);
      } catch {
        // ignore
      }

      await patchHistory({ content: newPost });
    } catch (err) {
      console.error("Inline edit failed:", err);
    } finally {
      setInlineLoading(false);
      setInlineSelection(null);
      setInlineInstruction("");
    }
  };

  const dismissInlineToolbar = () => {
    setInlineSelection(null);
    setInlineInstruction("");
  };

  const handleInlineKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleInlineEdit();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      dismissInlineToolbar();
    }
  };

  useEffect(() => {
    if (inlineSelection) {
      const timer = setTimeout(() => inlineInputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [inlineSelection]);

  const handleCopyLinkedIn = async () => {
    await navigator.clipboard.writeText(stripMarkdown(editedPost));
    setCopiedLinkedIn(true);
    showToast("Copied for LinkedIn", "success");
    setTimeout(() => setCopiedLinkedIn(false), 1500);
  };

  const handleCopyMedium = async () => {
    await navigator.clipboard.writeText(editedPost);
    setCopiedMedium(true);
    showToast("Copied for Medium", "success");
    setTimeout(() => setCopiedMedium(false), 1500);
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
      const res = await api.generateVisuals(editedPost);
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
      const res = await api.getSuggestions(ideaCount, ideaTopic.trim() || undefined);
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

  const handleDragStart = (e: React.MouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startRatio = splitRatio;
    const containerWidth = splitContainerRef.current?.offsetWidth ?? window.innerWidth;

    const onMouseMove = (ev: MouseEvent) => {
      const delta = ev.clientX - startX;
      const newRatio = startRatio + delta / containerWidth;
      setSplitRatio(Math.min(0.75, Math.max(0.35, newRatio)));
    };
    const onMouseUp = () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  const handleDrawerRegenerate = (overrides: { topic: string; format: Format; tone: Tone; length: Length; context: string }) => {
    setDrawerOpen(false);
    generate(overrides);
  };

  // ─── Derived state ────────────────────────────────────────────────────────

  const postGenerated = !!result;
  const splitActive = postGenerated && analysisOpen && isWide && !visualsVisible;


  // Grade derivation for metric rows
  const sc = result?.score ?? 0;
  const gradeLabel   = sc >= 85 ? "Grade 8" : sc >= 70 ? "Grade 7" : "Grade 6";
  const clarityLabel = sc >= 85 ? "Excellent" : sc >= 70 ? "Good" : "Fair";
  const engagementLabel = sc >= 85 ? "High" : sc >= 70 ? "Medium" : "Low";

  // SVG score ring
  const ringR = 54;
  const ringC = 2 * Math.PI * ringR; // ≈ 339.29
  const ringOffset = result?.scored ? ringC * (1 - result.score / 100) : ringC;

  // ─── Analysis panel (right column) ──────────────────────────────────────

  const analysisPanelContent = (
    <div>
      {/* Panel header */}
      <div className="flex items-center justify-between mb-7 shrink-0">
        <span className="label-caps text-secondary" style={{ fontSize: "0.6rem", letterSpacing: "0.1em" }}>
          ANALYSIS &amp; IMPACT
        </span>
        <button
          onClick={() => {
            // Snapshot current DOM content into state before the layout branch
            // switches. Without this, the remounting single-column div could render
            // empty if the user edited the post while the analysis panel was open.
            if (postEditorRef.current) {
              const current = postEditorRef.current.innerText.replace(/\u00a0/g, " ");
              if (current && current !== editedPost) setEditedPost(current);
            }
            setAnalysisOpen(false);
            setSplitRatio(0.55);
          }}
          className="text-outline hover:text-on-surface transition-colors text-xl leading-none"
          aria-label="Close analysis"
        >
          ×
        </button>
      </div>

      {scoreLoading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-5 h-5 rounded-full border-2 border-surface-container-high border-t-primary animate-spin" />
          <p className="text-xs text-outline">Scoring post…</p>
        </div>
      ) : result?.scored ? (
        <>
          {/* Score ring */}
          <div className="flex flex-col items-center mb-5">
            <svg width="130" height="130" viewBox="0 0 130 130">
              <circle cx="65" cy="65" r={ringR} fill="none" stroke="#e6e9e8" strokeWidth="8" />
              <circle
                cx="65" cy="65" r={ringR} fill="none"
                stroke="#58614f" strokeWidth="8"
                strokeLinecap="round"
                strokeDasharray={ringC}
                strokeDashoffset={ringOffset}
                transform="rotate(-90 65 65)"
                style={{ transition: "stroke-dashoffset 0.7s ease" }}
              />
              <text
                x="65" y="62"
                textAnchor="middle"
                fontSize="26" fontWeight="700" fill="#2f3333"
                fontFamily="Inter, system-ui, sans-serif"
              >
                {result.score}
              </text>
              <text
                x="65" y="79"
                textAnchor="middle"
                fontSize="8.5" fontWeight="500"
                letterSpacing="0.09em" fill="#777c7b"
                fontFamily="Inter, system-ui, sans-serif"
              >
                AUTHSCORE
              </text>
            </svg>
          </div>

          {/* Quote from first feedback item */}
          {result.score_feedback.length > 0 ? (
            <p
              className="font-headline italic text-secondary text-center mb-6 px-3 leading-relaxed"
              style={{ fontSize: 13 }}
            >
              &ldquo;{result.score_feedback[0]}&rdquo;
            </p>
          ) : (
            <p
              className="text-outline-variant text-center mb-6 px-3 leading-relaxed"
              style={{ fontSize: 13 }}
            >
              Your narrative voice analysis will appear here.
            </p>
          )}

          {/* Metric rows */}
          <div className="space-y-4 mb-6">
            {(
              [
                { label: "READABILITY", value: gradeLabel },
                { label: "CLARITY",     value: clarityLabel },
                { label: "ENGAGEMENT",  value: engagementLabel },
              ] as { label: string; value: string }[]
            ).map(({ label, value }) => (
              <div key={label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    className="label-caps text-outline"
                    style={{ fontSize: "0.58rem", letterSpacing: "0.09em" }}
                  >
                    {label}
                  </span>
                  <span className="text-xs font-medium text-on-surface">{value}</span>
                </div>
                <div className="h-1 rounded-full bg-surface-container-high overflow-hidden">
                  <div
                    className="h-full rounded-full bg-primary transition-all duration-700"
                    style={{ width: `${result.score}%` }}
                  />
                </div>
              </div>
            ))}
          </div>

          <div style={{ borderTop: "0.5px solid #dfe3e2", marginBottom: 20 }} />

          {/* Focus Points */}
          {result.score_feedback.length > 0 && (
            <div className="mb-6">
              <p
                className="label-caps text-secondary mb-3"
                style={{ fontSize: "0.58rem", letterSpacing: "0.1em" }}
              >
                FOCUS POINTS
              </p>
              <div className="space-y-3">
                {result.score_feedback.slice(1).map((f, i) => (
                  <div key={i} className="bg-surface-container rounded-lg px-4 py-3">
                    <p className="font-headline italic text-secondary leading-relaxed" style={{ fontSize: 12.5 }}>
                      &ldquo;{f}&rdquo;
                    </p>
                    <p
                      className={`label-caps mt-2 ${i % 2 === 0 ? "text-primary" : "text-tertiary"}`}
                      style={{ fontSize: "0.53rem", letterSpacing: "0.1em" }}
                    >
                      {i % 2 === 0 ? "STRONG POINT" : "NEEDS ATTENTION"}
                    </p>
                  </div>
                ))}
              </div>
            </div>
          )}

        </>
      ) : (
        /* Placeholder — score not yet run */
        <div className="flex flex-col items-center py-6 gap-4">
          <svg width="130" height="130" viewBox="0 0 130 130">
            <circle cx="65" cy="65" r={ringR} fill="none" stroke="#e6e9e8" strokeWidth="8" />
            <circle
              cx="65" cy="65" r={ringR} fill="none"
              stroke="#dfe3e2" strokeWidth="8"
              strokeDasharray={ringC} strokeDashoffset={ringC}
              transform="rotate(-90 65 65)"
            />
            <text
              x="65" y="62" textAnchor="middle"
              fontSize="26" fontWeight="500" fill="#aeb3b2"
              fontFamily="Inter, system-ui, sans-serif"
            >
              0
            </text>
            <text
              x="65" y="79" textAnchor="middle"
              fontSize="8.5" fontWeight="500"
              letterSpacing="0.09em" fill="#aeb3b2"
              fontFamily="Inter, system-ui, sans-serif"
            >
              AUTHSCORE
            </text>
          </svg>
          <p className="text-xs text-outline text-center">Run analysis to see your authscore.</p>
          <button
            onClick={() => { if (!result?.scored && !scoreLoading) handleScore(); }}
            className="btn-primary text-white text-xs font-medium rounded-lg px-5 py-2 hover:opacity-90 transition-opacity"
          >
            Run Analysis
          </button>

          {/* Placeholder metric rows */}
          <div className="w-full space-y-4 mt-2">
            {["READABILITY", "CLARITY", "ENGAGEMENT"].map((label) => (
              <div key={label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    className="label-caps text-outline-variant"
                    style={{ fontSize: "0.58rem", letterSpacing: "0.09em" }}
                  >
                    {label}
                  </span>
                  <span className="text-xs text-outline-variant">—</span>
                </div>
                <div className="h-1 rounded-full bg-surface-container-high" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );

  // ─── Shared action buttons for post view ─────────────────────────────────

  const actionBtnStyle = (disabled?: boolean): React.CSSProperties => ({
    display: "flex",
    flexDirection: "column",
    alignItems: "center",
    gap: 6,
    background: "rgba(255,255,255,0.78)",
    borderRadius: 14,
    padding: "12px 14px",
    border: "none",
    cursor: disabled ? "not-allowed" : "pointer",
    backdropFilter: "blur(20px)",
    opacity: disabled ? 0.5 : 1,
    transition: "background 0.15s",
    boxShadow: "0 1px 4px rgba(47,51,51,0.06)",
    minWidth: 52,
  });

  const actionLabelStyle: React.CSSProperties = {
    fontSize: 9,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#5b605f",
    fontWeight: 500,
  };

  const collapsedIconStyle = (disabled?: boolean): React.CSSProperties => ({
    display: "flex",
    alignItems: "center",
    justifyContent: "center",
    background: "none",
    border: "none",
    cursor: disabled ? "not-allowed" : "pointer",
    opacity: disabled ? 0.4 : 1,
    padding: 4,
    borderRadius: 8,
    transition: "color 0.15s",
    color: "rgba(91,96,95,0.5)",
  });

  const postActionButtons = splitActive ? (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, alignItems: "center" }}>
      {[
        {
          onClick: () => setDrawerOpen(true), disabled: loading, title: "Regenerate",
          icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M1 4v6h6" /><path d="M3.51 15a9 9 0 1 0 .49-4" /></svg>,
        },
        {
          onClick: () => { setAnalysisOpen(true); if (!result?.scored && !scoreLoading) handleScore(); else if (!isWide) setTimeout(() => analysisRef.current?.scrollIntoView({ behavior: "smooth" }), 50); },
          disabled: false, title: "Analyse",
          icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="12" width="4" height="9" /><rect x="10" y="7" width="4" height="14" /><rect x="17" y="3" width="4" height="18" /></svg>,
        },
        {
          onClick: visuals.length > 0 ? () => { setVisualsVisible(true); setAnalysisOpen(false); } : handleGenerateVisuals,
          disabled: visualsLoading, title: "Visuals",
          icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><rect x="3" y="3" width="18" height="18" rx="2" ry="2" /><circle cx="8.5" cy="8.5" r="1.5" /><polyline points="21 15 16 10 5 21" /></svg>,
        },
        {
          onClick: handleCopyLinkedIn, disabled: false, title: copiedLinkedIn ? "Copied!" : "Copy for LinkedIn",
          icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M16 8a6 6 0 0 0-12 0v8a6 6 0 0 0 12 0" /><path d="M8 8v8" /></svg>,
        },
        {
          onClick: handleCopyMedium, disabled: false, title: copiedMedium ? "Copied!" : "Copy for Medium",
          icon: <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2"><path d="M4 4h16v16H4z" /><path d="M8 8l3.5 5L15 8" /></svg>,
        },
      ].map(({ onClick, disabled, title, icon }) => (
        <button
          key={title}
          onClick={onClick}
          disabled={disabled}
          title={title}
          style={collapsedIconStyle(disabled)}
          onMouseEnter={e => { if (!disabled) (e.currentTarget as HTMLButtonElement).style.color = "#58614f"; }}
          onMouseLeave={e => { (e.currentTarget as HTMLButtonElement).style.color = "rgba(91,96,95,0.5)"; }}
        >
          {icon}
        </button>
      ))}
    </div>
  ) : (
    <div style={{ display: "flex", flexDirection: "column", gap: 20, alignItems: "center" }}>
      <button onClick={() => setDrawerOpen(true)} disabled={loading} title="Regenerate" style={actionBtnStyle(loading)}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M1 4v6h6" /><path d="M3.51 15a9 9 0 1 0 .49-4" />
        </svg>
        <span style={actionLabelStyle}>Regenerate</span>
      </button>

      <button
        onClick={() => {
          setAnalysisOpen(true);
          if (!result?.scored && !scoreLoading) handleScore();
          else if (!isWide) setTimeout(() => analysisRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
        }}
        title="Analyse"
        style={actionBtnStyle()}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <rect x="3" y="12" width="4" height="9" /><rect x="10" y="7" width="4" height="14" /><rect x="17" y="3" width="4" height="18" />
        </svg>
        <span style={actionLabelStyle}>Analyse</span>
      </button>

      <button
        onClick={visuals.length > 0 ? () => { setVisualsVisible(true); setAnalysisOpen(false); } : handleGenerateVisuals}
        disabled={visualsLoading}
        title={visuals.length > 0 ? "Visuals" : "Gen. Visuals"}
        style={actionBtnStyle(visualsLoading)}
      >
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
        <span style={actionLabelStyle}>{visuals.length > 0 ? "Visuals" : "Visuals"}</span>
      </button>

      <button onClick={handleCopyLinkedIn} title="Copy for LinkedIn" style={actionBtnStyle()}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M16 8a6 6 0 0 0-12 0v8a6 6 0 0 0 12 0" />
          <path d="M8 8v8" />
        </svg>
        <span style={actionLabelStyle}>{copiedLinkedIn ? "Copied!" : "LinkedIn"}</span>
      </button>

      <button onClick={handleCopyMedium} title="Copy for Medium" style={actionBtnStyle()}>
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M4 4h16v16H4z" />
          <path d="M8 8l3.5 5L15 8" />
        </svg>
        <span style={actionLabelStyle}>{copiedMedium ? "Copied!" : "Medium"}</span>
      </button>
    </div>
  );

  // ─── Post metadata bar ────────────────────────────────────────────────────

  const postStats = useMemo(() => {
    const wordCount = editedPost.trim().split(/\s+/).filter(Boolean).length;
    const charCount = editedPost.length;
    const readingTime = Math.round((wordCount / 200) * 2) / 2;
    const tweetCount = Math.ceil(charCount / 280);
    return { wordCount, charCount, readingTime, tweetCount };
  }, [editedPost]);

  const postMetaBar = (
    <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px] text-outline-variant">
      <span className="rounded-full bg-surface-container-low px-3 py-1">
        {postStats.wordCount} words
      </span>
      <span className="rounded-full bg-surface-container-low px-3 py-1">
        ~{postStats.readingTime} min read
      </span>
      {format === "thread" && (
        <span className="rounded-full bg-surface-container-low px-3 py-1">
          ~{postStats.tweetCount} tweets
        </span>
      )}
    </div>
  );

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      className={splitActive ? "" : "-mx-10 -mt-10 -mb-10 bg-background flex flex-col"}
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
              background: "#faf9f8",
              zIndex: 10,
            }
          : { minHeight: "100vh" }
      }
    >

      {/* ── Header bar ──────────────────────────────────────────────────────── */}
      <div
        style={{ borderBottom: "0.5px solid #dfe3e2", height: "52px" }}
        className="flex items-center justify-between px-8 bg-background shrink-0"
      >
        {/* Breadcrumb */}
        <div className="flex items-center gap-1.5">
          <span
            className="label-caps text-outline"
            style={{ fontSize: "0.62rem", letterSpacing: "0.1em" }}
          >
            WORKSPACE
          </span>
          <span className="text-outline-variant mx-1 text-xs select-none">›</span>
          <span
            className="label-caps text-on-surface"
            style={{ fontSize: "0.62rem", letterSpacing: "0.1em" }}
          >
            NEW CREATION
          </span>
        </div>

        {/* Right controls */}
        <div className="flex items-center gap-3">
          <div className="flex items-center gap-2 rounded-lg border border-surface-container-high bg-surface-container-lowest px-3 py-1.5">
            <svg
              width="12" height="12" viewBox="0 0 24 24"
              fill="none" stroke="currentColor" strokeWidth="2"
              className="text-outline-variant shrink-0"
            >
              <circle cx="11" cy="11" r="8" /><path d="m21 21-4.35-4.35" />
            </svg>
            <input
              placeholder="Search atelier..."
              className="text-xs text-on-surface bg-transparent outline-none w-32 placeholder:text-outline-variant"
            />
          </div>
          <button className="text-outline hover:text-on-surface transition-colors">
            <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
              <path d="M18 8A6 6 0 0 0 6 8c0 7-3 9-3 9h18s-3-2-3-9" />
              <path d="M13.73 21a2 2 0 0 1-3.46 0" />
            </svg>
          </button>
          <div className="w-7 h-7 rounded-full bg-primary-container flex items-center justify-center shrink-0">
            <span className="text-[11px] font-semibold text-on-primary-container select-none">S</span>
          </div>
        </div>
      </div>

      {/* ── Split layout (wide, post generated, analysis open) ──────────────── */}
      {splitActive ? (
        <div ref={splitContainerRef} style={{ display: "flex", flex: 1, overflow: "hidden" }}>

          {/* Left — manuscript */}
          <div
            style={{
              flex: `0 0 ${splitRatio * 100}%`,
              display: "flex",
              flexDirection: "column",
              padding: "32px 40px",
              overflow: "hidden",
            }}
          >
            {/* Manuscript heading row */}
            <div
              style={{
                display: "flex",
                alignItems: "center",
                justifyContent: "space-between",
                marginBottom: 16,
                flexShrink: 0,
              }}
            >
              <h2
                className="font-headline"
                style={{ fontSize: 22, fontWeight: 400, color: "#2f3333", margin: 0 }}
              >
                {topic || 'The Manuscript'}
              </h2>
              <span
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 6,
                  fontSize: 11,
                  color: "#777c7b",
                  background: "#edeeed",
                  borderRadius: 20,
                  padding: "3px 11px",
                  lineHeight: 1.6,
                }}
              >
                <span style={{ color: "#58614f", fontSize: 10 }}>●</span>
                AI Refined:{" "}
                <span
                  className="capitalize"
                  style={{ fontWeight: 500, color: "#2f3333", marginLeft: 2 }}
                >
                  {tone}
                </span>{" "}
                Tone
              </span>
            </div>

            <div className="flex-1 min-h-0 flex gap-6">
              <div className="hidden xl:block w-[210px] shrink-0 pt-6">
                {postActionButtons}
              </div>

              {/* Post canvas */}
              <div style={{ flex: 1, minHeight: 0, overflow: "hidden", display: "flex", flexDirection: "column" }}>
                <div className="rounded-[28px] bg-surface-container-lowest shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] transition-all duration-300" style={{ flex: 1, minHeight: 0, overflow: "hidden" }}>
                  <div className="h-full overflow-y-auto px-7 py-7">
                    <div
                      ref={postEditorRef}
                      contentEditable
                      suppressContentEditableWarning
                      role="textbox"
                      aria-multiline="true"
                      onInput={handlePostEditorInput}
                      onMouseUp={handlePostEditorSelection}
                      onKeyUp={handlePostEditorSelection}
                      className="manuscript-editor min-h-[52vh] outline-none text-[15.5px] leading-[1.9] text-on-surface whitespace-pre-wrap"
                      style={{ fontFamily: "inherit" }}
                    />
                  </div>
                </div>
              </div>
            </div>

            <div className="xl:hidden">{postActionButtons}</div>
            {postMetaBar}

            <p className="text-xs text-outline-variant shrink-0 mt-2">
              {lastSaved ? saveStatusText : "Auto-saved to history"}
            </p>
          </div>

          {/* Drag handle */}
          <div
            onMouseDown={handleDragStart}
            style={{
              width: "4px",
              cursor: "col-resize",
              flexShrink: 0,
              alignSelf: "stretch",
              background: "transparent",
              transition: "background 0.2s",
            }}
            onMouseEnter={e => e.currentTarget.style.background = "rgba(88,97,79,0.15)"}
            onMouseLeave={e => e.currentTarget.style.background = "transparent"}
          />

          {/* Right — analysis panel */}
          <div
            style={{
              flex: `0 0 ${(1 - splitRatio) * 100 - 0.5}%`,
              height: "100%",
              overflowY: "auto",
              padding: "28px 32px",
              background: "#faf9f8",
            }}
          >
            {analysisPanelContent}
          </div>
        </div>

      ) : postGenerated && !loading && !visualsVisible ? (
        // ── Single-column manuscript (panel closed or narrow) ────────────────
        <div style={{ flex: 1, overflowY: "auto", display: "flex", flexDirection: "column", alignItems: "center", width: "100%", padding: "40px 24px 48px" }}>

          {/* Header — label, serif title, subtitle */}
          <div style={{ width: "100%", maxWidth: 768 }}>
            <p className="label-caps text-secondary" style={{ fontSize: "0.6rem", letterSpacing: "0.1em", marginBottom: 6 }}>
              MANUSCRIPT DRAFT
            </p>
            <h1 style={{ fontFamily: "Noto Serif, serif", fontSize: "2rem", fontWeight: 300, color: "#2f3333", lineHeight: 1.2, marginBottom: "0.5rem", margin: "0 0 0.5rem" }}>
              {topic || "The Manuscript"}
            </h1>
            <p className="text-xs text-outline">Select any passage to refine it in place.</p>
          </div>

          {/* Status row — right-aligned, sits directly above the canvas */}
          <div style={{ width: "100%", maxWidth: 768, display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginTop: 16, marginBottom: 8 }}>
            <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 11, color: "#777c7b", background: "rgba(237,238,237,0.8)", borderRadius: 999, padding: "6px 12px", lineHeight: 1.6, backdropFilter: "blur(18px)" }}>
              <span style={{ color: "#58614f", fontSize: 10 }}>●</span>
              AI Refined:{" "}
              <span className="capitalize" style={{ fontWeight: 500, color: "#2f3333", marginLeft: 2 }}>{tone}</span>{" "}
              Tone
            </span>
            <button
              onClick={() => { setResult(null); setEditedPost(""); setAnalysisOpen(false); }}
              className="text-xs text-outline hover:text-secondary transition-colors"
            >
              ← Start over
            </button>
          </div>

          {/* Canvas + action stack wrapper */}
          <div style={{ position: "relative", width: "100%", maxWidth: 768 }}>
            {/* Action stack — absolute, anchored left of canvas on large screens */}
            <div
              className="hidden lg:flex"
              style={{ position: "absolute", right: "100%", marginRight: 32, top: 0, flexDirection: "column" }}
            >
              {postActionButtons}
            </div>

            {/* Canvas card */}
            <div
              style={{
                borderRadius: 28,
                background: "#ffffff",
                boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)",
                overflow: "hidden",
                minHeight: "85vh",
              }}
            >
              <div className="px-8 py-10 md:px-20 md:py-12">
                  <div
                    ref={postEditorRef}
                  contentEditable
                  suppressContentEditableWarning
                  role="textbox"
                  aria-multiline="true"
                  onInput={handlePostEditorInput}
                  onMouseUp={handlePostEditorSelection}
                  onKeyUp={handlePostEditorSelection}
                    className="manuscript-editor outline-none text-[15.5px] leading-[1.9] text-on-surface whitespace-pre-wrap"
                  style={{ fontFamily: "inherit", minHeight: "78vh" }}
                />
              </div>
            </div>
          </div>

          {/* Mobile action buttons */}
          <div className="lg:hidden" style={{ width: "100%", maxWidth: 768, marginTop: 20 }}>
            {postActionButtons}
          </div>

          {/* Footer — word count centered, last-edited right */}
          <div style={{ width: "100%", maxWidth: 768, display: "flex", justifyContent: "center", marginTop: "1.5rem", position: "relative" }}>
            <span style={{ fontSize: 11, color: "rgba(91,96,95,0.4)", letterSpacing: "0.05em" }}>
              {postStats.wordCount} words · ~{postStats.readingTime} min read
              {format === "thread" && ` · ~${postStats.tweetCount} tweets`}
            </span>
            <span style={{ position: "absolute", right: 0, fontSize: 10, color: "rgba(91,96,95,0.3)", fontStyle: "italic" }}>
              {lastSaved ? saveStatusText : "Auto-saved to history"}
            </span>
          </div>

          {/* Analysis panel (stacked below on narrow viewports) */}
          {analysisOpen && !isWide && (
            <div
              ref={analysisRef}
              style={{
                width: "100%",
                maxWidth: 768,
                marginTop: 24,
                paddingTop: 24,
                borderTop: "0.5px solid #dfe3e2",
                maxHeight: "50vh",
                overflowY: "auto",
              }}
            >
              {analysisPanelContent}
            </div>
          )}
        </div>

      ) : (
        // ── Scrollable column (configure / spinner / visuals) ────────────────
        <div className="flex-1 overflow-y-auto">
          <div style={{ maxWidth: 900, margin: "0 auto", padding: "32px 40px" }}>

            {/* Ideas panel */}
            {suggestionsVisible && (
              <div className="rounded-xl border border-surface-container-high bg-surface-container-lowest overflow-hidden mb-6">
                <div className="flex items-center justify-between px-5 py-3 border-b border-surface-container-high">
                  <div>
                    <p className="text-sm font-medium text-on-surface">
                      {suggestionsLoading
                        ? "Finding ideas…"
                        : `${suggestions.length} idea${suggestions.length !== 1 ? "s" : ""} from your memory`}
                    </p>
                    {!suggestionsLoading && (
                      <p className="text-xs text-outline mt-0.5">
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
                        className="text-xs text-secondary hover:text-on-surface border border-surface-container-high rounded-lg px-2.5 py-1 transition-colors"
                      >
                        Refresh
                      </button>
                    )}
                    <button
                      onClick={handleDismissIdeas}
                      className="text-outline hover:text-on-surface transition-colors text-xl leading-none"
                    >
                      ×
                    </button>
                  </div>
                </div>

                {suggestionsLoading && (
                  <div className="px-5 py-6 text-sm text-outline">Thinking…</div>
                )}

                {!suggestionsLoading && suggestions.length === 0 && (
                  <div className="px-5 py-6 text-sm text-outline">
                    No suggestions returned. Try adding more content to your memory first.
                  </div>
                )}

                {!suggestionsLoading && suggestions.length > 0 && (
                  <div className="divide-y divide-surface-container-high">
                    {suggestions.map((s, i) => (
                      <div
                        key={i}
                        className={`px-5 py-4 flex items-start justify-between gap-4 transition-colors ${
                          selectedIdeaIndex === i ? "bg-surface-container-low" : ""
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            {selectedIdeaIndex === i && (
                              <span className="text-primary text-xs font-medium">✓</span>
                            )}
                            <p className="text-sm font-medium text-on-surface leading-snug">{s.title}</p>
                          </div>
                          <div className="mt-1 flex items-center gap-2">
                            <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container-low border border-surface-container-high text-outline">
                              {FORMAT_BADGE[s.format] ?? s.format}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-outline leading-relaxed">{s.angle}</p>
                        </div>
                        <button
                          onClick={() => handleUseSuggestion(s, i)}
                          className={`text-xs whitespace-nowrap rounded-lg px-3 py-1.5 transition-colors border flex-shrink-0 ${
                            selectedIdeaIndex === i
                              ? "border-surface-container-high bg-surface-container-lowest text-outline"
                              : "border-surface-container-high bg-surface-container-lowest text-secondary hover:bg-surface-container-low"
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

            {/* ── Interstitial: continue vs start fresh ───────────────────── */}
            {showInterstitial && (
              <div
                style={{
                  display: "flex",
                  flexDirection: "column",
                  alignItems: "center",
                  justifyContent: "center",
                  minHeight: "60vh",
                  padding: "40px 24px",
                }}
              >
                <div style={{ maxWidth: 480, width: "100%", textAlign: "center" }}>
                  <p className="text-xs text-tertiary tracking-widest uppercase mb-3">
                    Welcome Back
                  </p>
                  <h2
                    className="font-headline text-on-surface"
                    style={{ fontSize: 26, fontWeight: 400, marginBottom: 28 }}
                  >
                    Continue your last draft?
                  </h2>

                  {/* Preview card */}
                  <div
                    className="bg-surface-container rounded-xl"
                    style={{ padding: "16px 20px", marginBottom: 28, textAlign: "left" }}
                  >
                    <p
                      className="text-sm text-on-surface"
                      style={{ marginBottom: interstitialScore > 0 ? 10 : 0 }}
                    >
                      {interstitialTopic.length > 80
                        ? interstitialTopic.slice(0, 80) + "…"
                        : interstitialTopic || "Untitled draft"}
                    </p>
                    {interstitialScore > 0 && (
                      <span
                        className="text-xs text-secondary"
                        style={{
                          display: "inline-block",
                          background: "var(--color-surface-container-high, #e8edeb)",
                          borderRadius: 6,
                          padding: "2px 10px",
                        }}
                      >
                        Score {interstitialScore}
                      </span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col gap-3" style={{ alignItems: "center" }}>
                    <button
                      className="btn-primary"
                      style={{ width: "100%", maxWidth: 320 }}
                      onClick={handleContinueEditing}
                    >
                      Continue editing
                    </button>
                    <button
                      className="ghost-border"
                      style={{ width: "100%", maxWidth: 320 }}
                      onClick={handleStartFresh}
                    >
                      Start fresh
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ── Configure form ──────────────────────────────────────────── */}
            {!postGenerated && !loading && !showInterstitial && (
              <div style={{ maxWidth: 600, margin: "0 auto" }}>
                {/* Editorial header */}
                <div className="mb-8">
                  <h1 className="font-headline text-[3rem] text-on-surface leading-tight">
                    Draft a new thought
                  </h1>
                  <p className="text-sm text-secondary mt-1.5">
                    Shape your idea and let your memory do the rest.
                  </p>
                </div>

                <div className="space-y-8">
                  {/* Topic */}
                  <div>
                    <label
                      className="label-caps text-secondary block mb-2.5"
                      style={{ fontSize: "0.62rem", letterSpacing: "0.09em" }}
                    >
                      THE CENTRAL THEME
                    </label>
                    <textarea
                      ref={topicRef}
                      rows={1}
                      value={topic}
                      onChange={(e) => setTopic(e.target.value)}
                      onInput={(e) => {
                        const el = e.currentTarget;
                        el.style.height = "auto";
                        el.style.height = el.scrollHeight + "px";
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          generate();
                        }
                      }}
                      placeholder="What story are we telling today?"
                      className="w-full px-4 py-3.5 rounded-lg border border-outline-variant bg-surface-container-lowest text-[15px] font-medium text-on-surface placeholder:text-outline-variant focus:outline-none focus:border-primary transition-colors"
                      style={{ resize: "none", overflow: "hidden" }}
                    />
                  </div>

                  {/* Format & Tone side-by-side */}
                  <div className="flex gap-12 items-start">
                    {/* Format — vertical pills */}
                    <div className="w-[38%] shrink-0">
                      <label
                        className="label-caps text-secondary block mb-3"
                        style={{ fontSize: "0.62rem", letterSpacing: "0.09em" }}
                      >
                        FORMAT
                      </label>
                      <div className="space-y-2">
                        {FORMATS.map((f) => (
                          <button
                            key={f.id}
                            onClick={() => setFormat(f.id)}
                            className={`w-full px-3 py-2 rounded-lg text-[13px] text-left transition-all border ${
                              format === f.id
                                ? "btn-primary text-white border-transparent font-medium"
                                : "border-outline-variant text-secondary hover:border-outline hover:text-on-surface bg-transparent"
                            }`}
                          >
                            {f.label}
                          </button>
                        ))}
                      </div>
                      <blockquote
                        className="mt-5 pl-3 italic text-[13px] text-[color:var(--color-text-tertiary)]"
                        style={{ borderLeft: "2px solid rgba(88, 97, 79, 0.4)" }}
                      >
                        The interface should not demand attention; it should provide a vessel for it.
                      </blockquote>
                    </div>

                    {/* Right column — tone row, tone context line, length row */}
                    <div className="w-[62%] shrink-0">
                      <div>
                        <label
                          className="label-caps text-secondary block mb-3"
                          style={{ fontSize: "0.62rem", letterSpacing: "0.09em" }}
                        >
                          VOICE &amp; RESONANCE
                        </label>
                        <div className="flex flex-wrap gap-2">
                          {TONES.map((t) => (
                            <button
                              key={t.id}
                              onClick={() => setTone(t.id)}
                              className={`px-4 py-2 rounded-md text-[13px] transition-all border ${
                                tone === t.id
                                  ? "bg-primary text-white border-transparent font-medium"
                                  : "text-on-surface hover:text-on-surface bg-transparent"
                              }`}
                              style={
                                tone === t.id
                                  ? undefined
                                  : { borderColor: "rgba(174, 179, 178, 0.15)" }
                              }
                            >
                              {TONE_DISPLAY_LABELS[t.id]}
                            </button>
                          ))}
                        </div>
                      </div>

                      <p
                        style={{
                          marginTop: 8,
                          fontSize: 12,
                          color: "var(--color-text-variant, var(--color-text-tertiary))",
                          lineHeight: 1.5,
                          maxWidth: 420,
                          opacity: toneDescOpacity,
                          transition: "opacity 0.2s ease",
                        }}
                      >
                        {TONE_DESCRIPTIONS[tone]}
                      </p>

                      <div className="mt-4">
                        <label
                          className="label-caps text-secondary block mb-3"
                          style={{ fontSize: "0.62rem", letterSpacing: "0.09em" }}
                        >
                          LENGTH
                        </label>
                        <div className="grid grid-cols-3 gap-2">
                          {LENGTHS.map((l) => {
                            const isActive = length === l.id;
                            return (
                              <button
                                key={l.id}
                                onClick={() => setLength(l.id)}
                                className={`w-full min-h-[54px] px-4 py-2.5 rounded-md transition-all border text-left flex flex-col justify-center ${
                                  isActive
                                    ? "bg-primary text-white border-transparent"
                                    : "text-on-surface hover:text-on-surface bg-transparent"
                                }`}
                                style={
                                  isActive
                                    ? undefined
                                    : { borderColor: "rgba(174, 179, 178, 0.15)" }
                                }
                              >
                                <div className="text-[13px] font-medium leading-tight">{l.label}</div>
                                <div
                                  className="text-[11px] leading-tight mt-0.5"
                                  style={{ opacity: isActive ? 0.7 : 0.55 }}
                                >
                                  {LENGTH_META[format][l.id]}
                                </div>
                              </button>
                            );
                          })}
                        </div>
                      </div>
                    </div>
                  </div>

                  {error && <p className="text-sm text-error">{error}</p>}

                  {/* Generate button */}
                  <div className="flex justify-center pt-2">
                    <button
                      onClick={() => generate()}
                      disabled={loading}
                      className="btn-primary text-white rounded-xl font-bold tracking-widest uppercase text-[13px] flex items-center gap-2.5 py-3.5 px-8 disabled:opacity-50 hover:opacity-90 hover:-translate-y-0.5 transition-all duration-200 shadow-card hover:shadow-card-hover"
                      style={{ width: 280, justifyContent: "center" }}
                    >
                      <svg width="15" height="15" viewBox="0 0 24 24" fill="currentColor">
                        <path d="M12 2l2.09 6.43H21l-5.47 3.97 2.09 6.43L12 15l-5.62 3.83 2.09-6.43L3 8.43h6.91z" />
                      </svg>
                      CREATE POST →
                    </button>
                  </div>
                </div>
              </div>
            )}

            {/* ── Generating spinner ──────────────────────────────────────── */}
            {loading && (
              <div className="flex flex-col items-center justify-center py-20 gap-5 text-center">
                <div className="w-10 h-10 rounded-full border-2 border-surface-container-high border-t-primary animate-spin" />
                <div>
                  <p className="text-sm font-medium text-on-surface font-headline">
                    Generating your draft
                  </p>
                  <p className="text-xs text-outline mt-1">
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
                    className="text-xs text-outline hover:text-secondary transition-colors"
                  >
                    ← Back to post
                  </button>
                  <button
                    onClick={handleGenerateVisuals}
                    disabled={visualsLoading}
                    className="text-xs border border-surface-container-high rounded-lg px-3 py-1.5 text-secondary hover:border-outline-variant hover:text-on-surface transition-colors bg-surface-container-lowest disabled:opacity-50"
                  >
                    {visualsLoading ? "Scanning…" : "Regenerate visuals"}
                  </button>
                </div>

                {visualsLoading && (
                  <div className="flex flex-col items-center justify-center py-16 gap-4 text-center">
                    <div className="w-8 h-8 rounded-full border-2 border-surface-container-high border-t-primary animate-spin" />
                    <p className="text-sm text-outline">Scanning post for visual opportunities…</p>
                  </div>
                )}

                {!visualsLoading && visuals.length === 0 && (
                  <div className="rounded-xl border border-surface-container-high bg-surface-container-lowest px-5 py-5">
                    <p className="text-sm text-outline leading-relaxed">
                      No visual placeholders found. Add{" "}
                      <code className="text-xs bg-surface-container-low px-1 py-0.5 rounded">[DIAGRAM: description]</code>
                      {" "}or{" "}
                      <code className="text-xs bg-surface-container-low px-1 py-0.5 rounded">[IMAGE: description]</code>
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
          initialLength={length}
          initialContext={context}
          onCancel={() => setDrawerOpen(false)}
          onRegenerate={handleDrawerRegenerate}
        />
      )}

      {inlineSelection && postGenerated && (
        <>
          <div
            onClick={dismissInlineToolbar}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 999,
              background: "transparent",
            }}
          />

          <div
            style={{
              position: "fixed",
              top: (inlineSelection.rect?.top ?? 200) - 56,
              left:
                (inlineSelection.rect?.left ?? 0) +
                (inlineSelection.rect?.width ?? 0) / 2,
              transform: "translateX(-50%)",
              zIndex: 1000,
              background: "rgba(243, 244, 243, 0.82)",
              borderRadius: "999px",
              padding: "8px 10px 8px 12px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              boxShadow:
                "0px 4px 20px rgba(47,51,51,0.08), 0px 12px 40px rgba(47,51,51,0.08)",
              minWidth: "320px",
              maxWidth: "420px",
              backdropFilter: "blur(20px)",
              border: "1px solid rgba(174, 179, 178, 0.18)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inlineInputRef}
              value={inlineInstruction}
              onChange={(e) => setInlineInstruction(e.target.value)}
              onKeyDown={handleInlineKeyDown}
              placeholder="Edit instruction..."
              disabled={inlineLoading}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#2f3333",
                fontSize: "13px",
                fontFamily: "Inter, sans-serif",
              }}
            />
            <button
              onClick={handleInlineEdit}
              disabled={inlineLoading || !inlineInstruction.trim()}
              style={{
                background: "linear-gradient(135deg, #58614f 0%, #4c5543 100%)",
                border: "none",
                borderRadius: "999px",
                color: "#ffffff",
                fontSize: "13px",
                padding: "6px 12px",
                cursor: inlineLoading ? "wait" : "pointer",
                opacity: !inlineInstruction.trim() || inlineLoading ? 0.5 : 1,
                fontFamily: "Inter, sans-serif",
              }}
            >
              {inlineLoading ? "..." : "→"}
            </button>
            <button
              onClick={dismissInlineToolbar}
              style={{
                background: "transparent",
                border: "none",
                color: "#777c7b",
                fontSize: "13px",
                padding: "4px 6px",
                cursor: "pointer",
                fontFamily: "Inter, sans-serif",
              }}
            >
              ✕
            </button>
          </div>
        </>
      )}

    </div>
  );
}
