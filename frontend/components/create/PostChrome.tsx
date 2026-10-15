"use client";

// The frame around the post: the workspace bar, the headings above the
// editor, the stats bar and the split-view drag handle.

import { useState, type MouseEvent } from "react";
import type { PostStats } from "@/lib/post-text";
import { Button } from "@/components/ui/button";

/** The page's breadcrumb bar (desktop only). */
export function WorkspaceBar() {
  return (
    <nav
      aria-label="Breadcrumb"
      style={{ borderBottom: "0.5px solid #dfe3e2", height: "52px" }}
      className="hidden md:flex items-center px-8 bg-background shrink-0"
    >
      <ol className="flex items-center gap-1.5">
        <li className="label-caps text-on-surface-variant" style={{ fontSize: "0.62rem", letterSpacing: "0.1em" }}>
          Workspace
        </li>
        <li aria-hidden="true" className="text-on-surface-variant mx-1 text-xs select-none">›</li>
        <li aria-current="page" className="label-caps text-on-surface" style={{ fontSize: "0.62rem", letterSpacing: "0.1em" }}>
          New post
        </li>
      </ol>
    </nav>
  );
}

/** The heading row above the editor in split view. */
export function SplitHeading({ topic, tone }: { topic: string; tone: string }) {
  return (
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
                    color: "#5b605f",
                    background: "#edeeed",
                    borderRadius: 20,
                    padding: "3px 11px",
                    lineHeight: 1.6,
                  }}
                >
                  <span style={{ color: "#58614f", fontSize: 10 }}>●</span>
                  Tone:{" "}<span
                    className="capitalize"
                    style={{ fontWeight: 500, color: "#2f3333", marginLeft: 2 }}
                  >
                    {tone}
                  </span>
                </span>
              </div>
  );
}

/** The heading and status row above the editor in single-column view. */
export function DraftHeading({ topic, tone, onStartOver }: { topic: string; tone: string; onStartOver: () => void }) {
  return (
              <div style={{ flexShrink: 0, padding: "40px 2rem 0", display: "flex", justifyContent: "center" }}>
                <div style={{ width: "100%", maxWidth: 860 }}>
                  <p className="label-caps text-secondary" style={{ fontSize: "0.6rem", letterSpacing: "0.1em", marginBottom: 6 }}>
                    MANUSCRIPT DRAFT
                  </p>
                  <h1 style={{ fontFamily: "var(--font-headline), serif", fontSize: "2rem", fontWeight: 300, color: "#2f3333", lineHeight: 1.2, margin: "0 0 0.5rem" }}>
                    {topic || "The Manuscript"}
                  </h1>
                  <p className="text-xs text-on-surface-variant">Select any passage to refine it in place.</p>
                  <div style={{ width: "100%", display: "flex", justifyContent: "flex-end", alignItems: "center", gap: 12, marginTop: 16, marginBottom: 8 }}>
                    <span style={{ display: "inline-flex", alignItems: "center", gap: 8, fontSize: 11, color: "#5b605f", background: "rgba(237,238,237,0.8)", borderRadius: 999, padding: "6px 12px", lineHeight: 1.6, backdropFilter: "blur(18px)" }}>
                      <span style={{ color: "#58614f", fontSize: 10 }}>●</span>
                      Tone:{" "}<span className="capitalize" style={{ fontWeight: 500, color: "#2f3333", marginLeft: 2 }}>{tone}</span>
                    </span>
                    <Button variant="tertiary" size="sm" onClick={onStartOver}>
                      Start over
                    </Button>
                  </div>
                </div>
              </div>
  );
}

export function PostMetaBar({ stats: postStats }: { stats: PostStats }) {
  return (
    <div className="mt-4 flex flex-wrap items-center gap-2 text-[12px] text-on-surface-variant">
      <span className="rounded-full bg-surface-container-low px-3 py-1">
        {postStats.wordCount} words
      </span>
      <span className="rounded-full bg-surface-container-low px-3 py-1">
        ~{postStats.readingTime} min read
      </span>
    </div>
  );
}

/** The handle between the post and the analysis panel in split view. */
export function DragHandle({ onMouseDown }: { onMouseDown: (e: MouseEvent) => void }) {
  const [hovered, setHovered] = useState(false);
  return (
            <div
              onMouseDown={onMouseDown}
              onMouseEnter={() => setHovered(true)}
              onMouseLeave={() => setHovered(false)}
              style={{
                width: "12px",
                cursor: "col-resize",
                flexShrink: 0,
                alignSelf: "stretch",
                background: hovered ? "rgba(88,97,79,0.06)" : "transparent",
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
                    background: hovered ? "rgba(88,97,79,0.5)" : "rgba(88,97,79,0.25)",
                    transition: "background 0.2s",
                  }}
                />
              ))}
            </div>
  );
}
