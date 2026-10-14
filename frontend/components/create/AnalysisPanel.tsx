"use client";

import type { GenerateResult } from "./config";
import { Button } from "@/components/ui/button";

/** The post's authenticity score, metric rows and focus points; or a prompt to run the analysis. */
export default function AnalysisPanel({ result, scoreLoading, onClose, onRunAnalysis }: {
  result: GenerateResult | null;
  scoreLoading: boolean;
  onClose: () => void;
  onRunAnalysis: () => void;
}) {
  // Grade derivation for metric rows
  const sc = result?.score ?? 0;
  const gradeLabel   = sc >= 85 ? "Grade 8" : sc >= 70 ? "Grade 7" : "Grade 6";
  const clarityLabel = sc >= 85 ? "Excellent" : sc >= 70 ? "Good" : "Fair";
  const engagementLabel = sc >= 85 ? "High" : sc >= 70 ? "Medium" : "Low";

  // SVG score ring
  const ringR = 54;
  const ringC = 2 * Math.PI * ringR; // ≈ 339.29
  const ringOffset = result?.scored ? ringC * (1 - result.score / 100) : ringC;

  return (
    <div>
      {/* Panel header */}
      <div className="flex items-center justify-between mb-7 shrink-0">
        <span className="label-caps text-secondary" style={{ fontSize: "0.6rem", letterSpacing: "0.1em" }}>
          ANALYSIS &amp; IMPACT
        </span>
        <Button variant="ghost" size="icon" onClick={onClose} aria-label="Close analysis" className="-mr-2 text-xl">
          ×
        </Button>
      </div>

      {scoreLoading ? (
        <div className="flex flex-col items-center justify-center py-16 gap-3">
          <div className="w-5 h-5 rounded-full border-2 border-surface-container-high border-t-primary animate-spin" />
          <p className="text-xs text-on-surface-variant">Scoring post…</p>
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
                style={{ fontFamily: "var(--font-body), system-ui, sans-serif" }}
              >
                {result.score}
              </text>
              <text
                x="65" y="79"
                textAnchor="middle"
                fontSize="8.5" fontWeight="500"
                letterSpacing="0.09em" fill="#5b605f"
                style={{ fontFamily: "var(--font-body), system-ui, sans-serif" }}
              >
                AUTHENTICITY
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
              className="text-on-surface-variant text-center mb-6 px-3 leading-relaxed"
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
                    className="label-caps text-on-surface-variant"
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
              style={{ fontFamily: "var(--font-body), system-ui, sans-serif" }}
            >
              0
            </text>
            <text
              x="65" y="79" textAnchor="middle"
              fontSize="8.5" fontWeight="500"
              letterSpacing="0.09em" fill="#aeb3b2"
              style={{ fontFamily: "var(--font-body), system-ui, sans-serif" }}
            >
              AUTHENTICITY
            </text>
          </svg>
          <p className="text-xs text-on-surface-variant text-center">Run the analysis to see how much this sounds like you.</p>
          <Button size="sm" onClick={() => { if (!result?.scored && !scoreLoading) onRunAnalysis(); }}>
            Run analysis
          </Button>

          {/* Placeholder metric rows */}
          <div className="w-full space-y-4 mt-2">
            {["READABILITY", "CLARITY", "ENGAGEMENT"].map((label) => (
              <div key={label}>
                <div className="flex items-center justify-between mb-1.5">
                  <span
                    className="label-caps text-on-surface-variant"
                    style={{ fontSize: "0.58rem", letterSpacing: "0.09em" }}
                  >
                    {label}
                  </span>
                  <span className="text-xs text-on-surface-variant">—</span>
                </div>
                <div className="h-1 rounded-full bg-surface-container-high" />
              </div>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
