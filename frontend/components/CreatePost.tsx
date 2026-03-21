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

function ScoreRing({ score }: { score: number }) {
  const color =
    score >= 75 ? "text-green-600" : score >= 50 ? "text-yellow-600" : "text-red-500";
  return (
    <div className={`text-4xl font-bold tabular-nums ${color}`}>
      {score}
      <span className="text-lg text-gray-400 font-normal">/100</span>
    </div>
  );
}

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
      <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4">
        <p className="text-sm font-medium text-red-600">
          Diagram generation failed — try regenerating the post
        </p>
        <p className="text-xs text-red-400 mt-1">{visual.description}</p>
      </div>
    );
  }

  const handleOpen = async () => {
    try {
      const dataURL = await svgToDataURL(visual.svg_code!);
      const win = window.open();
      if (win) {
        win.document.write(
          `<html><body style="margin:0;background:#f5f5f5;display:flex;justify-content:center;padding:24px">` +
          `<img src="${dataURL}" style="max-width:100%;border-radius:8px;box-shadow:0 2px 12px rgba(0,0,0,.15)" />` +
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
    <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
      <div className="px-5 py-3 border-b border-gray-100">
        <p className="text-sm font-medium text-gray-700">
          Diagram —{" "}
          <span className="font-normal text-gray-500">
            {visual.description.length > 60
              ? visual.description.slice(0, 60) + "…"
              : visual.description}
          </span>
        </p>
      </div>
      <div
        className="p-4 overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: visual.svg_code }}
      />
      <div className="px-5 py-3 border-t border-gray-100 space-y-2">
        <div className="flex items-center gap-3">
          <button
            onClick={handleOpen}
            className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors"
          >
            Open as PNG
          </button>
          {pngState === "opened" && (
            <span className="text-xs text-gray-500">
              PNG opened in new tab — right-click the image and select <strong>Save Image</strong> to download
            </span>
          )}
          {pngState === "blocked" && (
            <span className="text-xs text-gray-500">
              Popup blocked — right-click the image below and select <strong>Save Image</strong>
            </span>
          )}
        </div>
        {pngState === "blocked" && fallbackDataURL && (
          // eslint-disable-next-line @next/next/no-img-element
          <img
            src={fallbackDataURL}
            alt="diagram PNG"
            className="max-w-full rounded-lg border border-gray-200"
          />
        )}
      </div>
    </div>
  );
}

function ImageReminderCard({ visual }: { visual: Visual }) {
  return (
    <div className="rounded-xl border-2 border-dashed border-gray-200 bg-gray-50 px-5 py-4 space-y-1">
      <p className="text-xs font-semibold uppercase tracking-widest text-gray-400">
        Add your own visual
      </p>
      <p className="text-sm text-gray-500 leading-relaxed">{visual.reminder_text}</p>
    </div>
  );
}

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

  const topicRef = useRef<HTMLInputElement>(null);

  // Restore session from sessionStorage on mount
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
    } catch {
      // corrupt sessionStorage — ignore
    }
  }, []);

  // Persist session to sessionStorage whenever result or visuals change
  useEffect(() => {
    if (!result) return;
    try {
      sessionStorage.setItem(SS_POST, editedPost);
      sessionStorage.setItem(SS_SCORE, String(result.score));
      sessionStorage.setItem(SS_FEEDBACK, JSON.stringify(result.score_feedback));
      sessionStorage.setItem(SS_ITERATIONS, String(result.iterations));
      sessionStorage.setItem(SS_VISUALS, JSON.stringify(visuals));
    } catch {
      // sessionStorage full or unavailable — ignore
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

  // Pre-fill refinement instruction from latest feedback
  useEffect(() => {
    if (!result || result.score_feedback.length === 0) return;
    const items = result.score_feedback.slice(0, 3);
    setRefineInstruction("Fix the following issues: " + items.map((f) => f.trim().replace(/\.+$/, "")).join(". ") + ".");
  }, [result]);

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
      // auto-save failure is non-critical — silently ignore
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

      // Explicitly persist to sessionStorage
      try {
        sessionStorage.setItem(SS_POST, data.refined_draft);
        sessionStorage.setItem(SS_SCORE, String(data.score));
        sessionStorage.setItem(SS_FEEDBACK, JSON.stringify(data.score_feedback));
      } catch {
        // ignore
      }

      // Update history entry in place
      await patchHistory({ content: data.refined_draft, authenticity_score: data.score });
    } catch (e: unknown) {
      setRefineError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setRefineLoading(false);
    }
  };

  const generate = async () => {
    if (!topic.trim()) {
      setError("Topic is required.");
      return;
    }
    setError("");
    setLoading(true);
    setResult(null);
    setVisuals([]);
    setVisualsVisible(false);
    clearSession();

    try {
      const res = await fetch(`${API}/generate`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ topic, format, tone, context }),
      });

      if (!res.ok) {
        const err = await res.json();
        throw new Error(err.detail ?? "Generation failed");
      }

      const data: GenerateResult = await res.json();
      setResult(data);
      setEditedPost(data.post);

      // Auto-save immediately after generation
      await autoSavePost(data, data.post);
    } catch (e: unknown) {
      setError(e instanceof Error ? e.message : "Something went wrong.");
    } finally {
      setLoading(false);
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

      // Patch history entry with generated diagrams
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

  return (
    <div className="space-y-8">
      {/* Header */}
      <div>
        <h1 className="text-2xl font-semibold text-gray-900">Create Post</h1>
        <p className="mt-1 text-gray-500 text-sm">
          Generate content in your voice, grounded in your knowledge base.
        </p>
      </div>

      {/* Get ideas row */}
      <div className="flex flex-wrap items-center gap-3">
        <button
          onClick={handleGetIdeas}
          disabled={suggestionsLoading}
          className="text-sm border border-gray-200 rounded-xl px-4 py-2 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors bg-white disabled:opacity-50"
        >
          {suggestionsLoading ? "Finding angles..." : "Get ideas"}
        </button>
        <div className="flex items-center gap-1.5">
          <label className="text-xs text-gray-400">How many?</label>
          <input
            type="number"
            min={3}
            max={15}
            value={ideaCount}
            onChange={(e) => setIdeaCount(Math.min(15, Math.max(3, Number(e.target.value))))}
            className="w-14 rounded-lg border border-gray-200 bg-white px-2 py-1.5 text-xs text-gray-700 focus:outline-none focus:border-gray-400 text-center"
          />
        </div>
        <input
          type="text"
          value={ideaTopic}
          onChange={(e) => setIdeaTopic(e.target.value)}
          placeholder="Focus on a topic (optional) — e.g. 'production ML', 'career lessons'"
          className="flex-1 min-w-48 rounded-xl border border-gray-200 bg-white px-3 py-2 text-xs text-gray-700 placeholder:text-gray-400 focus:outline-none focus:border-gray-400"
        />
      </div>

      {/* Suggestions panel */}
      {suggestionsVisible && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <div>
              <p className="text-sm font-medium text-gray-700">
                {suggestionsLoading ? "Loading..." : `${suggestions.length} idea${suggestions.length !== 1 ? "s" : ""} from your memory`}
              </p>
              {!suggestionsLoading && (
                <p className="text-xs text-gray-400 mt-0.5">
                  {ideaTopic.trim() ? `Focused on: ${ideaTopic.trim()}` : "Ideas drawn from your full knowledge base"}
                </p>
              )}
            </div>
            <div className="flex items-center gap-3">
              {!suggestionsLoading && (
                <button
                  onClick={handleGetIdeas}
                  className="text-xs text-gray-500 hover:text-gray-900 border border-gray-200 rounded-lg px-2.5 py-1 transition-colors"
                >
                  Refresh
                </button>
              )}
              <button
                onClick={handleDismissIdeas}
                className="text-gray-400 hover:text-gray-700 transition-colors text-lg leading-none"
              >
                ×
              </button>
            </div>
          </div>

          {suggestionsLoading && (
            <div className="px-5 py-6 text-sm text-gray-400">Thinking...</div>
          )}

          {!suggestionsLoading && suggestions.length === 0 && (
            <div className="px-5 py-6 text-sm text-gray-400">
              No suggestions returned. Try adding more content to your memory first.
            </div>
          )}

          {!suggestionsLoading && suggestions.length > 0 && (
            <div className="divide-y divide-gray-100">
              {suggestions.map((s, i) => (
                <div
                  key={i}
                  className={`px-5 py-4 flex items-start justify-between gap-4 transition-colors ${
                    selectedIdeaIndex === i ? "bg-gray-50" : ""
                  }`}
                >
                  <div className="flex-1 min-w-0">
                    <div className="flex items-center gap-2">
                      {selectedIdeaIndex === i && (
                        <span className="text-green-600 text-xs font-medium">✓</span>
                      )}
                      <p className="text-sm font-semibold text-gray-900 leading-snug">
                        {s.title}
                      </p>
                    </div>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                        {FORMAT_BADGE[s.format] ?? s.format}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500 leading-relaxed">{s.angle}</p>
                  </div>
                  <button
                    onClick={() => handleUseSuggestion(s, i)}
                    className={`text-xs whitespace-nowrap rounded-lg px-3 py-1.5 transition-colors border ${
                      selectedIdeaIndex === i
                        ? "border-gray-300 bg-white text-gray-500"
                        : "border-gray-900 bg-gray-900 text-white hover:bg-gray-700"
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

      {/* Form */}
      <div className="space-y-6">
        {/* Topic */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Topic
          </label>
          <input
            ref={topicRef}
            type="text"
            value={topic}
            onChange={(e) => setTopic(e.target.value)}
            onKeyDown={(e) => e.key === "Enter" && generate()}
            placeholder="What do you want to write about?"
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 shadow-sm"
          />
        </div>

        {/* Format */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Format
          </label>
          <div className="flex gap-2">
            {FORMATS.map((f) => (
              <button
                key={f.id}
                onClick={() => setFormat(f.id)}
                className={`flex-1 px-4 py-2.5 rounded-xl text-sm font-medium border transition-colors ${
                  format === f.id
                    ? "border-gray-900 bg-gray-900 text-white"
                    : "border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-400 bg-white"
                }`}
              >
                {f.label}
              </button>
            ))}
          </div>
        </div>

        {/* Tone */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Tone
          </label>
          <div className="flex gap-2">
            {TONES.map((t) => (
              <button
                key={t.id}
                onClick={() => setTone(t.id)}
                className={`flex-1 px-4 py-2.5 rounded-xl text-sm border transition-colors text-left ${
                  tone === t.id
                    ? "border-gray-900 bg-gray-900 text-white"
                    : "border-gray-200 text-gray-500 hover:text-gray-800 hover:border-gray-400 bg-white"
                }`}
              >
                <div className="font-medium">{t.label}</div>
                <div className={`text-xs mt-0.5 ${tone === t.id ? "text-white/60" : "text-gray-400"}`}>
                  {t.description}
                </div>
              </button>
            ))}
          </div>
        </div>

        {/* Optional context */}
        <div>
          <label className="block text-sm font-medium text-gray-700 mb-2">
            Additional context{" "}
            <span className="font-normal text-gray-400">(optional)</span>
          </label>
          <textarea
            value={context}
            onChange={(e) => setContext(e.target.value)}
            placeholder="Specific angle, story, or data point you want included..."
            rows={3}
            className="w-full rounded-xl border border-gray-200 bg-white px-4 py-3 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 resize-none shadow-sm"
          />
        </div>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <button
          onClick={generate}
          disabled={loading}
          className="w-full rounded-xl bg-gray-900 text-white font-medium py-3 text-sm hover:bg-gray-700 disabled:opacity-50 disabled:cursor-not-allowed transition-colors"
        >
          {loading ? (
            <span className="flex items-center justify-center gap-2">
              <svg className="animate-spin h-4 w-4" viewBox="0 0 24 24" fill="none">
                <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
              </svg>
              Generating...
            </span>
          ) : (
            "Generate"
          )}
        </button>
      </div>

      {/* Restored session banner */}
      {restored && (
        <div className="flex items-center justify-between rounded-xl border border-blue-100 bg-blue-50 px-4 py-2.5">
          <p className="text-xs text-blue-600">Restored your last session</p>
          <button
            onClick={() => { clearSession(); setResult(null); setEditedPost(""); setVisuals([]); setVisualsVisible(false); }}
            className="text-blue-400 hover:text-blue-700 text-lg leading-none ml-4"
            aria-label="Dismiss"
          >
            ×
          </button>
        </div>
      )}

      {/* Result */}
      {result && (
        <div className="space-y-6 pt-2 border-t border-gray-200">

          {/* Editable post */}
          <div className="space-y-3">
            <p className="text-xs uppercase tracking-widest text-gray-400">Post</p>
            <textarea
              value={editedPost}
              onChange={(e) => setEditedPost(e.target.value)}
              rows={16}
              className="w-full rounded-xl border border-gray-200 bg-white px-4 py-4 text-sm text-gray-800 focus:outline-none focus:border-gray-400 resize-none leading-relaxed shadow-sm"
            />
            <div className="flex gap-3">
              <button
                onClick={handleCopy}
                className="flex-1 rounded-xl border border-gray-200 text-gray-600 font-medium py-2.5 text-sm hover:border-gray-400 hover:text-gray-900 transition-colors bg-white"
              >
                {copied ? "Copied!" : "Copy"}
              </button>
              <button
                onClick={handleGenerateVisuals}
                disabled={visualsLoading}
                className="flex-1 rounded-xl border border-gray-200 text-gray-600 font-medium py-2.5 text-sm hover:border-gray-400 hover:text-gray-900 transition-colors bg-white disabled:opacity-50"
              >
                {visualsLoading ? "Scanning post..." : "Generate visuals"}
              </button>
              <button
                onClick={generate}
                disabled={loading}
                className="flex-1 rounded-xl bg-gray-900 text-white font-medium py-2.5 text-sm hover:bg-gray-700 disabled:opacity-50 transition-colors"
              >
                Regenerate
              </button>
            </div>
            <p className="text-xs text-gray-400">Auto-saved to history</p>
          </div>

          {/* Analysis toggle */}
          <div>
            <button
              onClick={() => setShowAnalysis((v) => !v)}
              className="text-xs text-gray-400 hover:text-gray-700 transition-colors underline underline-offset-2"
            >
              {showAnalysis ? "Hide authenticity analysis" : "Show authenticity analysis"}
            </button>
          </div>

          {/* Analysis section — hidden by default */}
          {showAnalysis && (
            <>
              {/* Score + feedback */}
              <div className="flex items-start justify-between">
                <div>
                  <p className="text-xs uppercase tracking-widest text-gray-400 mb-2">
                    Authenticity score
                  </p>
                  <ScoreRing score={result.score} />
                  <p className="text-xs text-gray-400 mt-1">
                    {result.iterations} humanizer iteration{result.iterations !== 1 ? "s" : ""}
                  </p>
                </div>
                {result.score_feedback.length > 0 && (
                  <div className="max-w-xs space-y-1">
                    <p className="text-xs uppercase tracking-widest text-gray-400 mb-2">
                      Feedback
                    </p>
                    {result.score_feedback.slice(0, 4).map((f, i) => (
                      <p key={i} className="text-xs text-gray-500 leading-relaxed">
                        — {f}
                      </p>
                    ))}
                  </div>
                )}
              </div>

              {/* Refine section */}
              <div className="rounded-xl border border-gray-200 bg-white shadow-sm p-5 space-y-3">
                <p className="text-xs uppercase tracking-widest text-gray-400">Refine draft</p>
                <textarea
                  value={refineInstruction}
                  onChange={(e) => setRefineInstruction(e.target.value)}
                  rows={3}
                  placeholder="Describe what to fix — e.g. Fix the following issues: the hook is too generic. The second paragraph lacks specificity."
                  className="w-full rounded-xl border border-gray-200 bg-gray-50 px-4 py-3 text-sm text-gray-800 placeholder:text-gray-400 focus:outline-none focus:border-gray-400 resize-none"
                />
                {refineError && <p className="text-xs text-amber-600">{refineError}</p>}
                <button
                  onClick={handleRefine}
                  disabled={refineLoading}
                  className="rounded-xl border border-gray-200 text-gray-600 font-medium px-4 py-2 text-sm hover:border-gray-400 hover:text-gray-900 transition-colors bg-white disabled:opacity-50"
                >
                  {refineLoading ? (
                    <span className="flex items-center gap-2">
                      <svg className="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none">
                        <circle className="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" strokeWidth="4" />
                        <path className="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8v8H4z" />
                      </svg>
                      Refining...
                    </span>
                  ) : (
                    "Refine draft"
                  )}
                </button>
              </div>
            </>
          )}

          {/* Visuals panel */}
          {visualsVisible && (
            <div className="space-y-4 pt-2">
              <p className="text-xs uppercase tracking-widest text-gray-400">Visuals</p>

              {visualsLoading && (
                <p className="text-sm text-gray-400">
                  Scanning post for visual opportunities...
                </p>
              )}

              {!visualsLoading && visuals.length === 0 && (
                <div className="rounded-xl border border-gray-200 bg-white px-5 py-4">
                  <p className="text-sm text-gray-400">
                    No visual placeholders found. Add{" "}
                    <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">
                      [DIAGRAM: description]
                    </code>{" "}
                    or{" "}
                    <code className="text-xs bg-gray-100 px-1 py-0.5 rounded">
                      [IMAGE: description]
                    </code>{" "}
                    to your post and try again.
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
      )}
    </div>
  );
}
