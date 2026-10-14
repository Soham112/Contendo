"use client";

import { useState } from "react";
import DiagramView from "@/components/DiagramView";
import type { useApi } from "@/lib/api";
import { svgToPngDataURL } from "@/lib/svg";
import type { Visual } from "./config";

// ─── DiagramBlock ─────────────────────────────────────────────────────────────

interface DiagramBlockProps {
  visual: Visual;
  api: ReturnType<typeof useApi>;
  onActiveVersionChange: (position: number, svgCode: string) => void;
}

export function DiagramBlock({ visual, api, onActiveVersionChange }: DiagramBlockProps) {
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
        <p style={{ color: "#81543c", fontSize: "0.85rem", fontFamily: "var(--font-body), sans-serif" }}>
          Diagram generation failed — try again
        </p>
        <p style={{ color: "#81543c", fontSize: "0.75rem", opacity: 0.7, marginTop: 4, fontFamily: "var(--font-body), sans-serif" }}>
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
        <p style={{ fontSize: "0.8rem", color: "#645e57", fontFamily: "var(--font-body), sans-serif" }}>
          {visual.description.length > 70
            ? visual.description.slice(0, 70) + "…"
            : visual.description}
        </p>
      </div>

      {/* SVG display */}
      <DiagramView
        className="p-4 overflow-x-auto"
        svg={versions[activeVersion]}
        description={visual.description}
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
                  fontFamily: "var(--font-body), sans-serif",
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
              fontFamily: "var(--font-body), sans-serif",
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
              fontFamily: "var(--font-body), sans-serif",
              whiteSpace: "nowrap",
            }}
          >
            {isLoading ? "Updating…" : "Update →"}
          </button>
        </div>

        {refinementError && (
          <p style={{ fontSize: "0.78rem", color: "#81543c", fontFamily: "var(--font-body), sans-serif" }}>
            {refinementError}
          </p>
        )}
      </div>
    </div>
  );
}

export function DiagramCard({ visual }: { visual: Visual }) {
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
      const dataURL = await svgToPngDataURL(visual.svg_code!);
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
      <DiagramView className="p-4 overflow-x-auto" svg={visual.svg_code} description={visual.description} />
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

export function ImageReminderCard({ visual }: { visual: Visual }) {
  return (
    <div className="rounded-xl border-2 border-dashed border-outline-variant bg-surface-container px-5 py-4 space-y-1">
      <p className="label-caps text-outline-variant">
        Add your own visual
      </p>
      <p className="text-sm text-outline leading-relaxed">{visual.reminder_text}</p>
    </div>
  );
}

/** The visuals panel under the post: a diagram or image reminder per placeholder. */
export function VisualsPanel({ entered, visuals, loading, api, onRegenerate, onClose, onVersionChange }: {
  entered: boolean;
  visuals: Visual[];
  loading: boolean;
  api: ReturnType<typeof useApi>;
  onRegenerate: () => void;
  onClose: () => void;
  onVersionChange: (position: number, svgCode: string) => void;
}) {
  return (
                      <div
                        style={{
                          marginTop: 40,
                          opacity: entered ? 1 : 0,
                          transform: entered ? "translateY(0)" : "translateY(16px)",
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
                              onClick={onRegenerate}
                              disabled={loading}
                              style={{
                                fontSize: "0.78rem",
                                color: "#645e57",
                                background: "#f3f4f3",
                                border: "none",
                                borderRadius: "0.5rem",
                                padding: "4px 12px",
                                cursor: loading ? "not-allowed" : "pointer",
                                opacity: loading ? 0.5 : 1,
                                fontFamily: "var(--font-body), sans-serif",
                              }}
                            >
                              {loading ? "Scanning…" : "Regenerate"}
                            </button>
                            <button
                              onClick={onClose}
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

                        {loading && (
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
                            <p style={{ fontSize: "0.85rem", color: "#645e57", fontFamily: "var(--font-body), sans-serif" }}>
                              Scanning post for visual opportunities…
                            </p>
                          </div>
                        )}

                        {!loading && visuals.length === 0 && (
                          <div
                            style={{
                              borderRadius: "0.75rem",
                              background: "#f3f4f3",
                              padding: "20px 24px",
                            }}
                          >
                            <p style={{ fontSize: "0.85rem", color: "#645e57", fontFamily: "var(--font-body), sans-serif" }}>
                              No visual placeholders found in post.
                            </p>
                          </div>
                        )}

                        {!loading && (
                          <div style={{ display: "flex", flexDirection: "column", gap: "2rem" }}>
                            {visuals.map((v, i) =>
                              v.type === "diagram" ? (
                                <DiagramBlock
                                  key={i}
                                  visual={v}
                                  api={api}
                                  onActiveVersionChange={onVersionChange}
                                />
                              ) : (
                                <ImageReminderCard key={i} visual={v} />
                              )
                            )}
                          </div>
                        )}
                      </div>
  );
}
