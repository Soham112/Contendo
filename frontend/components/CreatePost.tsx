"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
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
const SS_RAW_POST = "contentOS_raw_post";


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

// ─── Placeholder block helpers ────────────────────────────────────────────────

const PLACEHOLDER_RE = /\[(DIAGRAM|IMAGE):([^\]]+)\]/gi;

/** Imperatively populates the contentEditable editor with text + styled placeholder blocks. */
function setEditorContent(editor: HTMLDivElement, text: string): void {
  editor.innerHTML = "";
  PLACEHOLDER_RE.lastIndex = 0;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = PLACEHOLDER_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      editor.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
    }
    const kind = match[1].toUpperCase();
    const placeholder = match[0];
    const labelText =
      kind === "DIAGRAM" ? "📊 Visual will appear here" : "🖼 Image reminder will appear here";

    const block = document.createElement("div");
    block.setAttribute("contentEditable", "false");
    block.setAttribute("data-placeholder", placeholder);
    block.style.cssText = [
      "background:#f3f4f3",
      "border:1.5px dashed rgba(174,179,178,0.4)",
      "border-radius:0.75rem",
      "height:120px",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "font-family:Inter,sans-serif",
      "font-size:0.85rem",
      "color:#645e57",
      "user-select:none",
      "cursor:default",
      "margin:8px 0",
      "pointer-events:none",
    ].join(";");
    block.textContent = labelText;
    editor.appendChild(block);
    lastIndex = match.index + placeholder.length;
  }

  if (lastIndex < text.length) {
    editor.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
}

/** Extracts raw post text from the editor, converting placeholder blocks back to their original text. */
function extractTextFromEditor(el: HTMLElement): string {
  // Fast path: no placeholders in the DOM
  if (!el.querySelector("[data-placeholder]")) {
    return el.innerText.replace(/\u00a0/g, " ");
  }

  const parts: string[] = [];

  function traverse(node: Node) {
    if (node.nodeType === Node.TEXT_NODE) {
      parts.push(node.textContent ?? "");
    } else if (node instanceof HTMLElement) {
      const placeholder = node.getAttribute("data-placeholder");
      if (placeholder !== null) {
        parts.push(placeholder);
        return;
      }
      if (node.tagName === "BR") {
        parts.push("\n");
        return;
      }
      // Handle block-level containers inserted by browser (Enter key in contenteditable)
      const isBlock = node.tagName === "DIV" || node.tagName === "P";
      if (isBlock && parts.length > 0 && parts[parts.length - 1] !== "\n") {
        parts.push("\n");
      }
      node.childNodes.forEach(traverse);
      if (isBlock && parts.length > 0 && parts[parts.length - 1] !== "\n") {
        parts.push("\n");
      }
    }
  }

  el.childNodes.forEach(traverse);
  return parts.join("").replace(/\u00a0/g, " ");
}

/** Strip [DIAGRAM:...] and [IMAGE:...] placeholders from text for clipboard. */
function stripPlaceholders(text: string): string {
  return text.replace(/\[(DIAGRAM|IMAGE):[^\]]+\]/gi, "").replace(/\n{3,}/g, "\n\n").trim();
}

// ─── DiagramBlock ─────────────────────────────────────────────────────────────

interface DiagramBlockProps {
  visual: Visual;
  api: ReturnType<typeof useApi>;
  onActiveVersionChange: (position: number, svgCode: string) => void;
}

function DiagramBlock({ visual, api, onActiveVersionChange }: DiagramBlockProps) {
  const [versions, setVersions] = useState<string[]>(visual.svg_code ? [visual.svg_code] : []);
  const [activeVersion, setActiveVersion] = useState(0);
  const [inputValue, setInputValue] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [refinementError, setRefinementError] = useState("");
  const [inputFocused, setInputFocused] = useState(false);

  if (!visual.svg_code) {
    return (
      <div
        style={{
          borderRadius: "0.75rem",
          background: "#f3f4f3",
          padding: "20px 24px",
        }}
      >
        <p style={{ color: "#81543c", fontSize: "0.85rem", fontFamily: "Inter, sans-serif" }}>
          Diagram generation failed — try again
        </p>
        <p style={{ color: "#81543c", fontSize: "0.75rem", opacity: 0.7, marginTop: 4, fontFamily: "Inter, sans-serif" }}>
          {visual.description}
        </p>
      </div>
    );
  }

  const handleVersionClick = (idx: number) => {
    setActiveVersion(idx);
    onActiveVersionChange(visual.position, versions[idx]);
  };

  const handleUpdate = async () => {
    if (!inputValue.trim() || isLoading) return;
    setIsLoading(true);
    setRefinementError("");
    try {
      const res = await api.refineVisual(
        versions[activeVersion],
        inputValue,
        visual.description
      );
      if (!res.ok) throw new Error("Refinement failed");
      const data = await res.json();
      const newSvg: string = data.svg_code;
      const newVersions = [...versions, newSvg];
      setVersions(newVersions);
      const newIdx = newVersions.length - 1;
      setActiveVersion(newIdx);
      setInputValue("");
      onActiveVersionChange(visual.position, newSvg);
    } catch {
      setRefinementError("Refinement failed — try again");
    } finally {
      setIsLoading(false);
    }
  };

  return (
    <div
      style={{
        borderRadius: "0.75rem",
        background: "#ffffff",
        boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)",
        overflow: "hidden",
      }}
    >
      {/* Header */}
      <div style={{ padding: "12px 16px", borderBottom: "none" }}>
        <p style={{ fontSize: "0.8rem", color: "#645e57", fontFamily: "Inter, sans-serif" }}>
          {visual.description.length > 70
            ? visual.description.slice(0, 70) + "…"
            : visual.description}
        </p>
      </div>

      {/* SVG display */}
      <div
        className="p-4 overflow-x-auto"
        dangerouslySetInnerHTML={{ __html: versions[activeVersion] }}
      />

      {/* Controls */}
      <div
        style={{
          padding: "12px 16px 16px",
          background: "#f3f4f3",
          display: "flex",
          flexDirection: "column",
          gap: 10,
        }}
      >
        {/* Version pills */}
        {versions.length > 1 && (
          <div style={{ display: "flex", gap: 6, flexWrap: "wrap" }}>
            {versions.map((_, idx) => (
              <button
                key={idx}
                onClick={() => handleVersionClick(idx)}
                style={{
                  padding: "4px 12px",
                  borderRadius: 999,
                  fontSize: "0.72rem",
                  border: idx === activeVersion ? "1px solid #58614f" : "none",
                  background: idx === activeVersion ? "#eef0eb" : "#e8e9e8",
                  color: idx === activeVersion ? "#58614f" : "#645e57",
                  cursor: "pointer",
                  fontFamily: "Inter, sans-serif",
                  fontWeight: idx === activeVersion ? 500 : 400,
                }}
              >
                v{idx + 1}
              </button>
            ))}
          </div>
        )}

        {/* Refinement input row */}
        <div style={{ display: "flex", gap: 8, alignItems: "center" }}>
          <input
            value={inputValue}
            onChange={(e) => setInputValue(e.target.value)}
            onKeyDown={(e) => { if (e.key === "Enter") handleUpdate(); }}
            onFocus={() => setInputFocused(true)}
            onBlur={() => setInputFocused(false)}
            placeholder="Describe what to change…"
            disabled={isLoading}
            style={{
              flex: 1,
              background: "#f3f4f3",
              border: "none",
              borderBottom: inputFocused ? "1.5px solid #58614f" : "1.5px solid #aeb3b2",
              padding: "6px 0",
              fontSize: "0.85rem",
              color: "#2f3333",
              outline: "none",
              fontFamily: "Inter, sans-serif",
              transition: "border-color 0.15s",
            }}
          />
          <button
            onClick={handleUpdate}
            disabled={isLoading || !inputValue.trim()}
            style={{
              background: "linear-gradient(135deg, #58614f, #4c5543)",
              color: "#ffffff",
              border: "none",
              borderRadius: "0.75rem",
              padding: "6px 16px",
              fontSize: "0.8rem",
              cursor: isLoading || !inputValue.trim() ? "not-allowed" : "pointer",
              opacity: isLoading || !inputValue.trim() ? 0.5 : 1,
              fontFamily: "Inter, sans-serif",
              whiteSpace: "nowrap",
            }}
          >
            {isLoading ? "Updating…" : "Update →"}
          </button>
        </div>

        {refinementError && (
          <p style={{ fontSize: "0.78rem", color: "#81543c", fontFamily: "Inter, sans-serif" }}>
            {refinementError}
          </p>
        )}
      </div>
    </div>
  );
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
  const [visualsPanelEntered, setVisualsPanelEntered] = useState(false);

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
  const [splitRatio, setSplitRatio] = useState(0.75);
  const [isHandleHovered, setIsHandleHovered] = useState(false);
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
  const [editorHinted, setEditorHinted] = useState(false);

  const topicRef = useRef<HTMLTextAreaElement>(null);
  const analysisRef = useRef<HTMLDivElement>(null);
  const inlineInputRef = useRef<HTMLInputElement>(null);
  const postEditorRef = useRef<HTMLDivElement>(null);
  const splitContainerRef = useRef<HTMLDivElement>(null);

  // Tracks whether the last editedPost change came from user typing (to skip DOM re-sync)
  const isUserInput = useRef(false);
  // Tracks what was last programmatically rendered so we don't re-render on unrelated deps changes
  const lastRenderedPost = useRef<string>("");
  // Tracks currently-active SVG per diagram position for history patching
  const activeDiagramSvgsRef = useRef<Record<number, string>>({});
  // Stores the original generated post text with [DIAGRAM:/IMAGE:] placeholders intact
  // (editedPost stores the clean version; rawPostRef is used for /generate-visuals)
  const rawPostRef = useRef<string>("");

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
      sessionStorage.setItem(SS_RAW_POST, rawPostRef.current);
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

  // Drive slide-in animation for the visuals panel
  useEffect(() => {
    if (visualsVisible) {
      requestAnimationFrame(() => setVisualsPanelEntered(true));
    } else {
      setVisualsPanelEntered(false);
    }
  }, [visualsVisible]);

  // useLayoutEffect (not useEffect) so the editor is populated synchronously
  // after every DOM commit — before the browser paints. This eliminates the
  // blank-canvas flash that occurred when analysisOpen or other deps caused a
  // branch switch (split ↔ single-column), because the new editor div is always
  // empty on mount and a deferred requestAnimationFrame could fire too late or
  // be cancelled by the effect cleanup when the layout changed quickly.
  useLayoutEffect(() => {
    if (!editedPost) return;
    const editor = postEditorRef.current;
    if (!editor) return;
    // Skip DOM re-sync when the change came from user typing in the editor.
    // The browser already updated the DOM; overwriting it would disrupt the cursor.
    // EXCEPTION: if the editor is empty (just remounted after a layout branch switch),
    // always repopulate regardless — otherwise the canvas stays blank.
    if (isUserInput.current && editor.innerHTML !== "") {
      isUserInput.current = false;
      return;
    }
    isUserInput.current = false;
    // Re-render when content changed OR when editor was remounted (empty after branch switch).
    if (editedPost !== lastRenderedPost.current || editor.innerHTML === "") {
      setEditorContent(editor, editedPost);
      lastRenderedPost.current = editedPost;
    }
  // analysisOpen + isWide + visualsVisible determine which branch (split vs single-column)
  // is rendered. loading gates post-gen mount after generate.
  }, [editedPost, analysisOpen, isWide, visualsVisible, loading]);

  const clearSession = () => {
    [SS_POST, SS_SCORE, SS_FEEDBACK, SS_ITERATIONS, SS_VISUALS, SS_IDEAS, SS_CURRENT_POST_ID, SS_TOPIC, SS_FORMAT, SS_TONE, SS_LENGTH, SS_SCORED, SS_RAW_POST].forEach((k) =>
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

      // Only require the post text itself. Secondary keys (score, feedback,
      // iterations) are provided as graceful defaults when missing — e.g. when
      // SS_POST was written by handleInlineEdit but a full persistence-effect
      // flush hadn't run yet. Without this, postGenerated stays false and the
      // post canvas never renders.
      if (savedPost) {
        const restoredResult: GenerateResult = {
          post: savedPost,
          score: Number(savedScore) || 0,
          score_feedback: (() => {
            try { return savedFeedback ? JSON.parse(savedFeedback) : []; }
            catch { return []; }
          })(),
          iterations: Number(savedIterations) || 1,
          // null = old session before lazy scoring — default to unscored so the
          // user can still run analysis; true = previously scored, preserve that.
          scored: savedScored === "true",
        };
        setResult(restoredResult);
        setEditedPost(savedPost);
        // Restore raw post (with placeholders) for /generate-visuals calls
        const savedRawPost = sessionStorage.getItem(SS_RAW_POST);
        rawPostRef.current = savedRawPost ?? savedPost;
        if (savedVisuals) {
          try {
            const parsedVisuals = JSON.parse(savedVisuals);
            setVisuals(parsedVisuals);
            if (parsedVisuals.length > 0) setVisualsVisible(true);
          } catch { /* ignore */ }
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
     SS_CURRENT_POST_ID, SS_TOPIC, SS_FORMAT, SS_TONE, SS_LENGTH, SS_SCORED, SS_SHOW_ANALYSIS, SS_RAW_POST].forEach((k) =>
      sessionStorage.removeItem(k)
    );
    rawPostRef.current = "";
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
      // Store raw post (with placeholders) for /generate-visuals, strip for display/editing
      rawPostRef.current = data.post;
      const cleanPost = stripPlaceholders(data.post);
      setResult(data);
      setEditedPost(cleanPost);
      setEditorHinted(false);
      await autoSavePost(data, cleanPost);
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
    isUserInput.current = true;
    const nextValue = extractTextFromEditor(e.currentTarget);
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
    await navigator.clipboard.writeText(stripMarkdown(stripPlaceholders(editedPost)));
    setCopiedLinkedIn(true);
    showToast("Copied for LinkedIn", "success");
    setTimeout(() => setCopiedLinkedIn(false), 1500);
  };

  const handleCopyMedium = async () => {
    await navigator.clipboard.writeText(stripPlaceholders(editedPost));
    setCopiedMedium(true);
    showToast("Copied for Medium", "success");
    setTimeout(() => setCopiedMedium(false), 1500);
  };

  const handleGenerateVisuals = async () => {
    setVisualsLoading(true);
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
      // Use the raw post (with [DIAGRAM:/IMAGE:] placeholders) so the backend can parse them
      const res = await api.generateVisuals(rawPostRef.current || editedPost);
      if (!res.ok) throw new Error("Visuals generation failed");
      const data = await res.json();
      const newVisuals: Visual[] = data.visuals ?? [];
      setVisuals(newVisuals);

      // Seed the active-version tracker with initial SVGs
      const svgsByPosition: Record<number, string> = {};
      newVisuals.forEach((v) => {
        if (v.type === "diagram" && v.svg_code) {
          svgsByPosition[v.position] = v.svg_code;
        }
      });
      activeDiagramSvgsRef.current = svgsByPosition;

      const diagrams = newVisuals
        .filter((v) => v.type === "diagram" && v.svg_code)
        .map((v) => ({ position: v.position, description: v.description, svg_code: v.svg_code }));
      if (diagrams.length > 0) {
        await patchHistory({ svg_diagrams: diagrams });
      }

      // Slide panel in after successful generation
      if (newVisuals.length > 0) {
        setVisualsVisible(true);
      }
    } catch {
      setVisuals([]);
    } finally {
      setVisualsLoading(false);
    }
  };

  const handleDiagramVersionChange = async (position: number, svgCode: string) => {
    activeDiagramSvgsRef.current[position] = svgCode;
    // Patch history with the active version for every diagram
    const diagrams = visuals
      .filter((v) => v.type === "diagram")
      .map((v) => ({
        position: v.position,
        description: v.description,
        svg_code: activeDiagramSvgsRef.current[v.position] ?? v.svg_code,
      }))
      .filter((d) => d.svg_code !== null);
    if (diagrams.length > 0) {
      await patchHistory({ svg_diagrams: diagrams });
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
      setSplitRatio(Math.min(0.82, Math.max(0.35, newRatio)));
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
              const current = extractTextFromEditor(postEditorRef.current);
              if (current && current !== editedPost) setEditedPost(current);
            }
            setAnalysisOpen(false);
            setSplitRatio(0.75);
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

  const iconSize = splitActive ? 16 : 22;
  const btnGap = splitActive ? 16 : 32;
  const btnLabelStyle: React.CSSProperties = {
    fontSize: splitActive ? 7 : 9,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#5b605f",
    fontWeight: 500,
  };

  const postActionButtons = (
    <div style={{ display: "flex", flexDirection: "column", gap: btnGap, alignItems: "center" }}>
      <button
        onClick={() => setDrawerOpen(true)}
        disabled={loading}
        title="Regenerate"
        style={splitActive ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.5 : 1, padding: "4px 6px", borderRadius: 8 } : actionBtnStyle(loading)}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M1 4v6h6" /><path d="M3.51 15a9 9 0 1 0 .49-4" />
        </svg>
        <span style={btnLabelStyle}>Regenerate</span>
      </button>

      <button
        onClick={() => {
            // Snapshot current DOM content before the layout branch switches.
            // Without this, content typed-but-not-yet-persisted would be lost
            // when the split layout remounts the editor div.
            if (postEditorRef.current) {
              const current = extractTextFromEditor(postEditorRef.current);
              if (current && current !== editedPost) setEditedPost(current);
            }
            setAnalysisOpen(true);
            if (!result?.scored && !scoreLoading) handleScore();
            else if (!isWide) setTimeout(() => analysisRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
          }}
        title="Analyse"
        style={splitActive ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: "pointer", padding: "4px 6px", borderRadius: 8 } : actionBtnStyle()}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <rect x="3" y="12" width="4" height="9" /><rect x="10" y="7" width="4" height="14" /><rect x="17" y="3" width="4" height="18" />
        </svg>
        <span style={btnLabelStyle}>Analyse</span>
      </button>

      <button
        onClick={
          visualsLoading
            ? undefined
            : visualsVisible
            ? () => setVisualsVisible(false)
            : visuals.length > 0
            ? () => setVisualsVisible(true)
            : handleGenerateVisuals
        }
        disabled={visualsLoading}
        title={visualsLoading ? "Generating visuals…" : visualsVisible ? "Hide visuals" : "Generate visuals"}
        style={splitActive ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: visualsLoading ? "not-allowed" : "pointer", opacity: visualsLoading ? 0.5 : 1, padding: "4px 6px", borderRadius: 8 } : actionBtnStyle(visualsLoading)}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
        <span style={btnLabelStyle}>{visualsLoading ? "Generating" : visualsVisible ? "Hide" : "Visuals"}</span>
      </button>

      <button
        onClick={handleCopyLinkedIn}
        title="Copy for LinkedIn"
        style={splitActive ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: "pointer", padding: "4px 6px", borderRadius: 8 } : actionBtnStyle()}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M16 8a6 6 0 0 0-12 0v8a6 6 0 0 0 12 0" />
          <path d="M8 8v8" />
        </svg>
        <span style={btnLabelStyle}>{copiedLinkedIn ? "Copied!" : "LinkedIn"}</span>
      </button>

      <button
        onClick={handleCopyMedium}
        title="Copy for Medium"
        style={splitActive ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: "pointer", padding: "4px 6px", borderRadius: 8 } : actionBtnStyle()}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M4 4h16v16H4z" />
          <path d="M8 8l3.5 5L15 8" />
        </svg>
        <span style={btnLabelStyle}>{copiedMedium ? "Copied!" : "Medium"}</span>
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
        className="hidden md:flex items-center justify-between px-8 bg-background shrink-0"
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

      {/* ── Post layout: unified split / single-column ───────────────────────── */}
      {/* The <div ref={postEditorRef}> lives at a STABLE unconditional tree     */}
      {/* position inside this single branch. When splitActive toggles, only CSS  */}
      {/* changes — React reuses the editor DOM node and its innerHTML is never    */}
      {/* lost, eliminating the blank-canvas flash caused by branch-switching.    */}
      {postGenerated && !loading ? (
        <div
          ref={splitContainerRef}
          style={{
            display: "flex",
            flex: 1,
            overflow: splitActive ? "hidden" : undefined,
          }}
        >
          {/* ── Post area ──────────────────────────────────────────────────── */}
          <div
            style={splitActive ? {
              flex: `0 0 ${splitRatio * 100}%`,
              display: "flex",
              flexDirection: "column",
              padding: "32px 16px 32px 8px",
              overflow: "hidden",
            } : {
              flex: 1,
              display: "flex",
              flexDirection: "column",
              overflowY: "auto",
            }}
          >
            {/* Split mode: manuscript heading row (sibling, not ancestor of editor) */}
            {splitActive && (
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
            )}

            {/* Single-column mode: header + status row (sibling, not ancestor of editor) */}
            {!splitActive && (
              <div style={{ flexShrink: 0, padding: "40px 2rem 0", display: "flex", justifyContent: "center" }}>
                <div style={{ width: "100%", maxWidth: 860 }}>
                  <p className="label-caps text-secondary" style={{ fontSize: "0.6rem", letterSpacing: "0.1em", marginBottom: 6 }}>
                    MANUSCRIPT DRAFT
                  </p>
                  <h1 style={{ fontFamily: "Noto Serif, serif", fontSize: "2rem", fontWeight: 300, color: "#2f3333", lineHeight: 1.2, margin: "0 0 0.5rem" }}>
                    {topic || "The Manuscript"}
                  </h1>
                  <p className="text-xs text-outline">Select any passage to refine it in place.</p>
                  <div style={{ width: "100%", display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginTop: 16, marginBottom: 8 }}>
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
                </div>
              </div>
            )}

            {/* ── Canvas + actions ─────────────────────────────────────────────
                Every div from here down to <div ref={postEditorRef}> is
                UNCONDITIONAL — no ternary or && in the ancestor chain.
                React therefore reuses the same DOM nodes on every layout
                switch and the editor innerHTML is always preserved.          */}
            <div
              style={splitActive ? {
                flex: "1 1 0",
                minHeight: 0,
                display: "flex",
                gap: 24,
              } : {
                display: "flex",
                justifyContent: "center",
                padding: "0 2rem 48px",
              }}
            >
              {/* Action buttons column — split mode sidebar (sibling of canvas wrapper) */}
              {splitActive && (
                <div className="hidden xl:block w-[210px] shrink-0 pt-6">
                  {postActionButtons}
                </div>
              )}

              {/* Canvas wrapper — always at a stable child index */}
              <div
                style={splitActive ? {
                  flex: 1,
                  minHeight: 0,
                  overflow: "hidden",
                  display: "flex",
                  flexDirection: "column",
                } : {
                  width: "100%",
                  maxWidth: 860,
                  position: "relative",
                }}
              >
                {/* Action buttons — single-column: absolute left of canvas (sibling of card) */}
                {!splitActive && (
                  <div
                    className="hidden lg:flex"
                    style={{ position: "absolute", right: "100%", marginRight: 24, top: 0, flexDirection: "column" }}
                  >
                    {postActionButtons}
                  </div>
                )}

                {/* ── Canvas card — same element type, stable child index, only CSS changes */}
                <div
                  className={splitActive ? "rounded-[28px] bg-surface-container-lowest shadow-[0px_4px_20px_rgba(47,51,51,0.04),0px_12px_40px_rgba(47,51,51,0.06)] transition-all duration-300" : ""}
                  style={splitActive ? {
                    flex: 1,
                    minHeight: 0,
                    overflow: "hidden",
                    cursor: "text",
                  } : {
                    borderRadius: 28,
                    background: "#ffffff",
                    boxShadow: "0px 4px 20px rgba(47,51,51,0.04), 0px 12px 40px rgba(47,51,51,0.06)",
                    overflow: "hidden",
                    minHeight: "85vh",
                  }}
                >
                  {/* Scroll / padding area — same element type, only className changes */}
                  <div
                    className={splitActive ? "h-full overflow-y-auto px-7 py-7" : "px-8 py-10 md:px-20 md:py-12"}
                    style={{ cursor: "text" }}
                  >
                    <div style={{ position: "relative" }}>
                      {!editorHinted && (
                        <div
                          style={{
                            position: "absolute",
                            top: 0,
                            left: 0,
                            pointerEvents: "none",
                            color: "rgba(119,124,123,0.38)",
                            fontSize: "15.5px",
                            lineHeight: "1.9",
                            fontFamily: "inherit",
                            userSelect: "none",
                          }}
                        >
                          Click to edit…
                        </div>
                      )}
                      {/* Single editor div — React reuses this DOM node on every layout switch */}
                      <div
                        ref={postEditorRef}
                        contentEditable
                        suppressContentEditableWarning
                        role="textbox"
                        aria-multiline="true"
                        onFocus={() => setEditorHinted(true)}
                        onInput={handlePostEditorInput}
                        onMouseUp={handlePostEditorSelection}
                        onKeyUp={handlePostEditorSelection}
                        className="manuscript-editor outline-none text-[15.5px] leading-[1.9] text-on-surface whitespace-pre-wrap"
                        style={{ fontFamily: "inherit", minHeight: splitActive ? "52vh" : "78vh" }}
                      />
                    </div>
                  </div>
                </div>
                {/* END canvas card */}

                {/* Below-canvas content — single-column only */}
                {!splitActive && (
                  <>
                    <div className="lg:hidden" style={{ width: "100%", marginTop: 20 }}>
                      {postActionButtons}
                    </div>

                    {/* Footer — word count centered, last-edited right */}
                    <div style={{ width: "100%", display: "flex", justifyContent: "center", marginTop: "1.5rem", position: "relative" }}>
                      <span style={{ fontSize: 11, color: "rgba(91,96,95,0.4)", letterSpacing: "0.05em" }}>
                        {postStats.wordCount} words · ~{postStats.readingTime} min read
                        {format === "thread" && ` · ~${postStats.tweetCount} tweets`}
                      </span>
                      <span style={{ position: "absolute", right: 0, fontSize: 10, color: "rgba(91,96,95,0.3)", fontStyle: "italic" }}>
                        {lastSaved ? saveStatusText : "Auto-saved to history"}
                      </span>
                    </div>

                    {/* Analysis panel stacked below on narrow viewports */}
                    {analysisOpen && !isWide && (
                      <div
                        ref={analysisRef}
                        style={{
                          width: "100%",
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

                    {/* Visuals panel */}
                    {visualsVisible && (
                      <div
                        style={{
                          marginTop: 40,
                          opacity: visualsPanelEntered ? 1 : 0,
                          transform: visualsPanelEntered ? "translateY(0)" : "translateY(16px)",
                          transition: "opacity 300ms ease-out, transform 300ms ease-out",
                        }}
                      >
                        <div
                          style={{
                            display: "flex",
                            alignItems: "center",
                            justifyContent: "space-between",
                            marginBottom: 20,
                          }}
                        >
                          <p
                            className="label-caps text-secondary"
                            style={{ fontSize: "0.6rem", letterSpacing: "0.1em" }}
                          >
                            VISUALS
                          </p>
                          <div style={{ display: "flex", alignItems: "center", gap: 10 }}>
                            <button
                              onClick={handleGenerateVisuals}
                              disabled={visualsLoading}
                              style={{
                                fontSize: "0.78rem",
                                color: "#645e57",
                                background: "#f3f4f3",
                                border: "none",
                                borderRadius: "0.5rem",
                                padding: "4px 12px",
                                cursor: visualsLoading ? "not-allowed" : "pointer",
                                opacity: visualsLoading ? 0.5 : 1,
                                fontFamily: "Inter, sans-serif",
                              }}
                            >
                              {visualsLoading ? "Scanning…" : "Regenerate"}
                            </button>
                            <button
                              onClick={() => setVisualsVisible(false)}
                              style={{
                                background: "none",
                                border: "none",
                                cursor: "pointer",
                                color: "#aeb3b2",
                                fontSize: "1.1rem",
                                lineHeight: 1,
                                padding: "2px 4px",
                              }}
                              aria-label="Close visuals panel"
                            >
                              ×
                            </button>
                          </div>
                        </div>

                        {visualsLoading && (
                          <div
                            style={{
                              display: "flex",
                              flexDirection: "column",
                              alignItems: "center",
                              padding: "48px 0",
                              gap: 12,
                            }}
                          >
                            <div className="w-8 h-8 rounded-full border-2 border-surface-container-high border-t-primary animate-spin" />
                            <p style={{ fontSize: "0.85rem", color: "#645e57", fontFamily: "Inter, sans-serif" }}>
                              Scanning post for visual opportunities…
                            </p>
                          </div>
                        )}

                        {!visualsLoading && visuals.length === 0 && (
                          <div
                            style={{
                              borderRadius: "0.75rem",
                              background: "#f3f4f3",
                              padding: "20px 24px",
                            }}
                          >
                            <p style={{ fontSize: "0.85rem", color: "#645e57", fontFamily: "Inter, sans-serif" }}>
                              No visual placeholders found in post.
                            </p>
                          </div>
                        )}

                        {!visualsLoading && (
                          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                            {visuals.map((v, i) =>
                              v.type === "diagram" ? (
                                <DiagramBlock
                                  key={i}
                                  visual={v}
                                  api={api}
                                  onActiveVersionChange={handleDiagramVersionChange}
                                />
                              ) : (
                                <ImageReminderCard key={i} visual={v} />
                              )
                            )}
                          </div>
                        )}
                      </div>
                    )}
                    {/* END visuals panel */}
                  </>
                )}
              </div>
              {/* END canvas wrapper */}
            </div>
            {/* END canvas + actions */}

            {/* Split mode: footer */}
            {splitActive && (
              <>
                <div className="xl:hidden">{postActionButtons}</div>
                {postMetaBar}
                <p className="text-xs text-outline-variant shrink-0 mt-2">
                  {lastSaved ? saveStatusText : "Auto-saved to history"}
                </p>
              </>
            )}
          </div>
          {/* END post area */}

          {/* Drag handle — split only */}
          {splitActive && (
            <div
              onMouseDown={handleDragStart}
              onMouseEnter={() => setIsHandleHovered(true)}
              onMouseLeave={() => setIsHandleHovered(false)}
              style={{
                width: "12px",
                cursor: "col-resize",
                flexShrink: 0,
                alignSelf: "stretch",
                background: isHandleHovered ? "rgba(88,97,79,0.06)" : "transparent",
                transition: "background 0.2s",
                display: "flex",
                flexDirection: "column",
                alignItems: "center",
                justifyContent: "center",
                gap: "4px",
              }}
            >
              {[0, 1, 2].map(i => (
                <div
                  key={i}
                  style={{
                    width: "6px",
                    height: "1.5px",
                    borderRadius: "2px",
                    background: isHandleHovered ? "rgba(88,97,79,0.5)" : "rgba(88,97,79,0.25)",
                    transition: "background 0.2s",
                  }}
                />
              ))}
            </div>
          )}

          {/* Analysis panel — split only */}
          {splitActive && (
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
          )}
        </div>

      ) : (
        // ── Scrollable column (configure / spinner / visuals) ────────────────
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 md:px-10" style={{ maxWidth: 900, margin: "0 auto", paddingTop: "32px", paddingBottom: "32px" }}>

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
                  <div className="flex flex-col md:flex-row gap-6 md:gap-12 items-start">
                    {/* Format — vertical pills */}
                    <div className="w-full md:w-[38%] shrink-0">
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
                    <div className="w-full md:w-[62%] shrink-0">
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
                        <div className="w-full">
                          <div className="flex md:grid md:grid-cols-3 gap-2 w-full">
                          {LENGTHS.map((l) => {
                            const isActive = length === l.id;
                            return (
                              <button
                                key={l.id}
                                onClick={() => setLength(l.id)}
                                className={`w-full flex-1 md:flex-none min-h-[54px] px-2 md:px-4 py-3 md:py-2.5 rounded-md transition-all border text-left flex flex-col justify-center ${
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
                                <div className="text-sm md:text-[13px] font-medium leading-tight">{l.label}</div>
                                <div
                                  className="text-xs md:text-[11px] leading-tight mt-0.5"
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
