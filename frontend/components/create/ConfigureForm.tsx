"use client";

import type { RefObject } from "react";
import QuotaLine from "@/components/billing/QuotaLine";
import { LowCoverageNotice } from "@/components/LowCoverageNotice";
import type { ClosestSource } from "@/lib/api";
import type { Entitlements } from "@/lib/billing";
import type { useTracking } from "@/lib/useTracking";
import BusinessPostFields, { type BusinessPost } from "./BusinessPostFields";
import {
  FORMATS, LENGTH_META, LENGTHS, TONE_DESCRIPTIONS, TONE_DISPLAY_LABELS, TONES, type Format, type Length, type Tone,
} from "./config";

/** The form a post starts from: theme, format, tone and length. */
export default function ConfigureForm({
  business, topicRef, topic, onTopicChange, format, onFormatChange, tone, onToneChange, length, onLengthChange,
  toneDescOpacity, error, lowCoverage, loading, opinionEnabled, entitlements, onGenerate, logEvent,
}: {
  business: BusinessPost;
  topicRef: RefObject<HTMLTextAreaElement>;
  topic: string;
  onTopicChange: (value: string) => void;
  format: Format;
  onFormatChange: (value: Format) => void;
  tone: Tone;
  onToneChange: (value: Tone) => void;
  length: Length;
  onLengthChange: (value: Length) => void;
  toneDescOpacity: number;
  error: string;
  lowCoverage: ClosestSource[] | null;
  loading: boolean;
  opinionEnabled: boolean;
  entitlements: Entitlements | null;
  onGenerate: (overrides?: { context?: string }, opts?: { noSpecifics?: boolean }) => void;
  logEvent: ReturnType<typeof useTracking>["logEvent"];
}) {
  return (
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
                  <BusinessPostFields business={business} />

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
                      onChange={(e) => onTopicChange(e.target.value)}
                      onInput={(e) => {
                        const el = e.currentTarget;
                        el.style.height = "auto";
                        el.style.height = el.scrollHeight + "px";
                      }}
                      onKeyDown={(e) => {
                        if (e.key === "Enter" && !e.shiftKey) {
                          e.preventDefault();
                          onGenerate();
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
                            onClick={() => onFormatChange(f.id)}
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
                              onClick={() => onToneChange(t.id)}
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
                                onClick={() => onLengthChange(l.id)}
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

                  {lowCoverage && (
                    <LowCoverageNotice
                      sources={lowCoverage}
                      busy={loading}
                      opinionEnabled={opinionEnabled}
                      onAddSource={() =>
                        logEvent({ event_type: "button_click", page_url: "/create", button_name: "low_coverage_add_source" })
                      }
                      onWriteOpinion={() => {
                        logEvent({ event_type: "button_click", page_url: "/create", button_name: "low_coverage_write_opinion" });
                        onGenerate(undefined, { noSpecifics: true });
                      }}
                      onWriteWithDetails={(details) => {
                        logEvent({ event_type: "button_click", page_url: "/create", button_name: "low_coverage_write_with_details" });
                        onGenerate({ context: details }, { noSpecifics: true });
                      }}
                    />
                  )}

                  <div className="flex justify-center">
                    <QuotaLine entitlements={entitlements} />
                  </div>

                  {/* Generate button */}
                  <div className="flex justify-center pt-2">
                    <button
                      onClick={() => onGenerate()}
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
  );
}
