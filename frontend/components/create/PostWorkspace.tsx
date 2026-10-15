"use client";

import type { FormEvent, MouseEvent, ReactNode, RefObject } from "react";
import { motion } from "motion/react";
import { transition } from "@/components/ui/motion";
import GroundingNotice, { type Grounding } from "@/components/GroundingNotice";
import { OpinionPostLabel } from "@/components/LowCoverageNotice";
import PostPreviewPanel from "@/components/preview/PostPreviewPanel";
import PublishPanel from "@/components/publishing/PublishPanel";
import type { PostStats } from "@/lib/post-text";
import { DraftHeading, DragHandle, PostMetaBar, SplitHeading } from "./PostChrome";

/**
 * A generated post: the editor canvas with its headings, actions, preview and
 * publish panel, in single-column or split (with analysis) layout.
 *
 * The editor div sits at a STABLE unconditional tree position: when
 * splitActive toggles only CSS changes, so React reuses the editor DOM node and
 * its innerHTML is never lost.
 */
export default function PostWorkspace({
  splitActive, splitRatio, isWide, containerRef, onDragStart, topic, tone, onStartOver, actions, mobileActions,
  editorRef, opinionMode, hinted, onEditorFocus, onEditorInput, onEditorSelect,
  text, grounding, postId, traceId, postStats, saveStatus, analysisOpen, analysisRef, analysisPanel, visualsPanel,
}: {
  splitActive: boolean;
  splitRatio: number;
  isWide: boolean;
  containerRef: RefObject<HTMLDivElement>;
  onDragStart: (e: MouseEvent) => void;
  topic: string;
  tone: string;
  onStartOver: () => void;
  /** The action buttons as a column (desktop rail). */
  actions: ReactNode;
  /** The same actions as a row, for phones and tablets. */
  mobileActions: ReactNode;
  editorRef: RefObject<HTMLDivElement>;
  opinionMode: boolean;
  /** Whether the editor has been focused once (hides the "Click to edit" label). */
  hinted: boolean;
  onEditorFocus: () => void;
  onEditorInput: (e: FormEvent<HTMLDivElement>) => void;
  onEditorSelect: () => void;
  text: string;
  grounding: Grounding | null | undefined;
  postId: number | null;
  traceId: string | null;
  postStats: PostStats;
  saveStatus: string;
  analysisOpen: boolean;
  analysisRef: RefObject<HTMLDivElement>;
  analysisPanel: ReactNode;
  visualsPanel: ReactNode;
}) {
  return (
        <motion.div
          initial={{ opacity: 0 }}
          animate={{ opacity: 1 }}
          transition={transition.slow}
          ref={containerRef}
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
            {splitActive && <SplitHeading topic={topic} tone={tone} />}

            {/* Single-column mode: header + status row (sibling, not ancestor of editor) */}
            {!splitActive && <DraftHeading topic={topic} tone={tone} onStartOver={onStartOver} />}

            {/* ── Canvas + actions ─────────────────────────────────────────────
                Every div from here down to <div ref={editorRef}> is
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
                  {actions}
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
                    {actions}
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
                    minHeight: isWide ? "85vh" : undefined,
                  }}
                >
                  {/* Scroll / padding area — same element type, only className changes */}
                  <div
                    className={splitActive ? "h-full overflow-y-auto px-7 py-7" : "px-8 py-10 md:px-20 md:py-12"}
                    style={{ cursor: "text" }}
                  >
                    {/* Own slot before the editor wrapper: present or not, the wrapper keeps its index */}
                    {opinionMode && <OpinionPostLabel />}
                    <div style={{ position: "relative" }}>
                      {/* In-flow label, not an overlay: drawn on top of the editor it covered the post's first words */}
                      {!hinted && (
                        <div
                          aria-hidden="true"
                          style={{
                            pointerEvents: "none",
                            color: "#5b605f",
                            fontSize: "0.75rem",
                            letterSpacing: "0.05rem",
                            textTransform: "uppercase",
                            marginBottom: 8,
                            userSelect: "none",
                          }}
                        >
                          Click to edit
                        </div>
                      )}
                      {/* Single editor div — React reuses this DOM node on every layout switch */}
                      <div
                        ref={editorRef}
                        contentEditable
                        suppressContentEditableWarning
                        role="textbox"
                        aria-multiline="true"
                        aria-label="Your post"
                        onFocus={onEditorFocus}
                        onInput={onEditorInput}
                        onMouseUp={onEditorSelect}
                        onKeyUp={onEditorSelect}
                        className="manuscript-editor outline-none text-[15.5px] leading-[1.9] text-on-surface whitespace-pre-wrap"
                        style={{ fontFamily: "inherit", minHeight: splitActive ? "52vh" : isWide ? "78vh" : "30vh" }}
                      />
                    </div>
                  </div>
                </div>
                {/* END canvas card */}

                {/* Phones and tablets: the actions as a row right under the post (after the card, so its index holds). */}
                {!splitActive && <div className="lg:hidden mt-4 w-full">{mobileActions}</div>}

                <div style={{ width: "100%", marginTop: 20 }}>
                  <GroundingNotice grounding={grounding} />
                  <div className="mb-5">
                    <PostPreviewPanel content={text} />
                  </div>
                  <PublishPanel content={text} postId={postId} traceId={traceId} />
                </div>

                {/* Below-canvas content — single-column only */}
                {!splitActive && (
                  <>
                    {/* Footer: word count centred, save status on the right (stacked on phones) */}
                    <div className="mt-6 flex w-full flex-wrap items-center justify-between gap-x-4 gap-y-1 sm:relative sm:justify-center">
                      <span style={{ fontSize: 12, color: "#5b605f", letterSpacing: "0.03em" }}>
                        {postStats.wordCount} words · ~{postStats.readingTime} min read
                      </span>
                      <span className="sm:absolute sm:right-0" style={{ fontSize: 12, color: "#5b605f", fontStyle: "italic" }}>
                        {saveStatus}
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
                        {analysisPanel}
                      </div>
                    )}

                    {visualsPanel}
                  </>
                )}
              </div>
              {/* END canvas wrapper */}
            </div>
            {/* END canvas + actions */}

            {/* Split mode: footer */}
            {splitActive && (
              <>
                <div className="xl:hidden">{actions}</div>
                <PostMetaBar stats={postStats} />
                <p className="text-xs text-on-surface-variant shrink-0 mt-2">
                  {saveStatus}
                </p>
              </>
            )}
          </div>
          {/* END post area */}

          {/* Drag handle — split only */}
          {splitActive && <DragHandle onMouseDown={onDragStart} />}

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
              {analysisPanel}
            </div>
          )}
        </motion.div>
  );
}
