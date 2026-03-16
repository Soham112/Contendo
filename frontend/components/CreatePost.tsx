"use client";

import { useRef, useState } from "react";

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

function downloadSVGAsPNG(svgCode: string, filename: string) {
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
  if (!ctx) return;

  const img = new Image();
  const blob = new Blob([svgCode], { type: "image/svg+xml" });
  const url = URL.createObjectURL(blob);

  img.onload = () => {
    ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
    const link = document.createElement("a");
    link.download = filename;
    link.href = canvas.toDataURL("image/png");
    link.click();
    URL.revokeObjectURL(url);
  };
  img.src = url;
}

function DiagramCard({ visual }: { visual: Visual }) {
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
      <div className="px-5 py-3 border-t border-gray-100">
        <button
          onClick={() =>
            downloadSVGAsPNG(visual.svg_code!, `diagram-${visual.position}.png`)
          }
          className="text-xs border border-gray-200 rounded-lg px-3 py-1.5 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors"
        >
          Download PNG
        </button>
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
  const [saved, setSaved] = useState(false);
  const [saving, setSaving] = useState(false);

  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [suggestionsVisible, setSuggestionsVisible] = useState(false);
  const [suggestionsLoading, setSuggestionsLoading] = useState(false);

  const [visuals, setVisuals] = useState<Visual[]>([]);
  const [visualsLoading, setVisualsLoading] = useState(false);
  const [visualsVisible, setVisualsVisible] = useState(false);

  const topicRef = useRef<HTMLInputElement>(null);

  const generate = async () => {
    if (!topic.trim()) {
      setError("Topic is required.");
      return;
    }
    setError("");
    setLoading(true);
    setResult(null);
    setSaved(false);
    setVisuals([]);
    setVisualsVisible(false);

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

  const handleSave = async () => {
    if (!result) return;
    setSaving(true);
    try {
      const res = await fetch(`${API}/log-post`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          topic,
          format,
          tone,
          content: editedPost,
          authenticity_score: result.score,
        }),
      });
      if (!res.ok) throw new Error("Save failed");
      setSaved(true);
    } catch {
      // silently fail — non-critical
    } finally {
      setSaving(false);
    }
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
      setVisuals(data.visuals ?? []);
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
    try {
      const res = await fetch(`${API}/suggestions?count=5`);
      if (!res.ok) throw new Error("Failed to fetch suggestions");
      const data = await res.json();
      setSuggestions(data.suggestions ?? []);
    } catch {
      setSuggestions([]);
    } finally {
      setSuggestionsLoading(false);
    }
  };

  const handleUseSuggestion = (s: Suggestion) => {
    setTopic(s.title);
    const fmt = s.format as Format;
    if (FORMATS.find((f) => f.id === fmt)) setFormat(fmt);
    setSuggestionsVisible(false);
    setSuggestions([]);
    topicRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    topicRef.current?.focus();
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

      {/* Get ideas button */}
      <div>
        <button
          onClick={handleGetIdeas}
          disabled={suggestionsLoading}
          className="text-sm border border-gray-200 rounded-xl px-4 py-2 text-gray-600 hover:border-gray-400 hover:text-gray-900 transition-colors bg-white disabled:opacity-50"
        >
          {suggestionsLoading ? "Finding fresh angles from your memory..." : "Get ideas"}
        </button>
      </div>

      {/* Suggestions panel */}
      {suggestionsVisible && (
        <div className="rounded-xl border border-gray-200 bg-white shadow-sm overflow-hidden">
          <div className="flex items-center justify-between px-5 py-3 border-b border-gray-100">
            <p className="text-sm font-medium text-gray-700">
              {suggestionsLoading ? "Loading..." : `${suggestions.length} idea${suggestions.length !== 1 ? "s" : ""} from your memory`}
            </p>
            <button
              onClick={() => { setSuggestionsVisible(false); setSuggestions([]); }}
              className="text-gray-400 hover:text-gray-700 transition-colors text-lg leading-none"
            >
              ×
            </button>
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
                <div key={i} className="px-5 py-4 flex items-start justify-between gap-4">
                  <div className="flex-1 min-w-0">
                    <p className="text-sm font-semibold text-gray-900 leading-snug">
                      {s.title}
                    </p>
                    <div className="mt-1 flex items-center gap-2">
                      <span className="text-xs px-2 py-0.5 rounded-full bg-gray-100 text-gray-500">
                        {FORMAT_BADGE[s.format] ?? s.format}
                      </span>
                    </div>
                    <p className="mt-1 text-xs text-gray-500 leading-relaxed">{s.angle}</p>
                  </div>
                  <button
                    onClick={() => handleUseSuggestion(s)}
                    className="text-xs whitespace-nowrap border border-gray-900 bg-gray-900 text-white rounded-lg px-3 py-1.5 hover:bg-gray-700 transition-colors"
                  >
                    Use this
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

      {/* Result */}
      {result && (
        <div className="space-y-6 pt-2 border-t border-gray-200">
          {/* Score */}
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
                onClick={handleSave}
                disabled={saving || saved}
                className="flex-1 rounded-xl border border-gray-200 text-gray-600 font-medium py-2.5 text-sm hover:border-gray-400 hover:text-gray-900 transition-colors bg-white disabled:opacity-50"
              >
                {saved ? "Saved to history" : saving ? "Saving..." : "Save to history"}
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
          </div>

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
