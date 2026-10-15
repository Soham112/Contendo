"use client";

import type { RefObject } from "react";
import QuotaLine from "@/components/billing/QuotaLine";
import { LowCoverageNotice } from "@/components/LowCoverageNotice";
import { Button } from "@/components/ui/button";
import { ChoiceGroup } from "@/components/ui/choice-group";
import { Label, Textarea } from "@/components/ui/field";
import { ErrorState } from "@/components/ui/states";
import type { ClosestSource } from "@/lib/api";
import type { Entitlements } from "@/lib/billing";
import type { useTracking } from "@/lib/useTracking";
import BusinessPostFields, { type BusinessPost } from "./BusinessPostFields";
import { TONE_DESCRIPTIONS, TONE_DISPLAY_LABELS, TONES, type Tone } from "./config";

/** The form a post starts from: topic and tone. Posts are LinkedIn posts, and
 *  the backend sets their length. */
export default function ConfigureForm({
  business, topicRef, topic, onTopicChange, tone, onToneChange,
  toneDescOpacity, error, lowCoverage, loading, opinionEnabled, entitlements, onGenerate, logEvent,
}: {
  business: BusinessPost;
  topicRef: RefObject<HTMLTextAreaElement>;
  topic: string;
  onTopicChange: (value: string) => void;
  tone: Tone;
  onToneChange: (value: Tone) => void;
  toneDescOpacity: number;
  error: string;
  lowCoverage: ClosestSource[] | null;
  loading: boolean;
  opinionEnabled: boolean;
  entitlements: Entitlements | null;
  onGenerate: (overrides?: { context?: string }, opts?: { noSpecifics?: boolean }) => void;
  logEvent: ReturnType<typeof useTracking>["logEvent"];
}) {
  const hasTopic = topic.trim().length > 0;
  return (
    <div className="mx-auto max-w-[600px]">
      <div className="mb-8">
        <h1 className="font-headline text-[2.25rem] sm:text-[3rem] leading-tight text-on-surface">Draft a new thought</h1>
        <p className="mt-1.5 text-[0.9375rem] text-on-surface-variant">Shape your idea and let your memory do the rest.</p>
      </div>

      <form
        className="space-y-8"
        onSubmit={(e) => {
          e.preventDefault();
          if (hasTopic) onGenerate();
        }}
      >
        <BusinessPostFields business={business} />

        <div>
          <Label htmlFor="post-topic">What is the post about?</Label>
          <Textarea
            id="post-topic"
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
                if (hasTopic) onGenerate();
              }
            }}
            placeholder="What story are we telling today?"
            className="min-h-12 resize-none overflow-hidden text-[1rem] font-medium"
            aria-describedby={error ? "post-error" : undefined}
          />
        </div>

        <div>
          <ChoiceGroup
            legend="Tone"
            value={tone}
            onChange={onToneChange}
            options={TONES.map((t) => ({ value: t.id, label: TONE_DISPLAY_LABELS[t.id] }))}
          />
          <p
            aria-live="polite"
            className="mt-2 max-w-[420px] text-[0.8125rem] leading-normal text-on-surface-variant"
            style={{ opacity: toneDescOpacity, transition: "opacity 0.2s ease-out" }}
          >
            {TONE_DESCRIPTIONS[tone]}
          </p>
        </div>

        {error && <div id="post-error"><ErrorState message={error} onRetry={hasTopic ? () => onGenerate() : undefined} /></div>}

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

        <div className="flex justify-center pt-2">
          <Button type="submit" size="lg" className="w-full sm:w-[280px]" loading={loading} disabled={!hasTopic} disabledReason="Add a topic to continue">
            Create post
          </Button>
        </div>
      </form>
    </div>
  );
}
