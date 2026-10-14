"use client";

import { Button } from "@/components/ui/button";

/** Offered on arrival when this tab has an unfinished draft: continue it or start fresh. */
export default function ResumeDraftPrompt({ topic, score, onContinue, onStartFresh }: {
  topic: string;
  score: number;
  onContinue: () => void;
  onStartFresh: () => void;
}) {
  return (
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
                      style={{ marginBottom: score > 0 ? 10 : 0 }}
                    >
                      {topic.length > 80
                        ? topic.slice(0, 80) + "…"
                        : topic || "Untitled draft"}
                    </p>
                    {score > 0 && (
                      <span
                        className="text-xs text-secondary"
                        style={{
                          display: "inline-block",
                          background: "var(--color-surface-container-high, #e8edeb)",
                          borderRadius: 6,
                          padding: "2px 10px",
                        }}
                      >
                        Score {score}
                      </span>
                    )}
                  </div>

                  {/* Actions */}
                  <div className="flex flex-col gap-3" style={{ alignItems: "center" }}>
                    <Button className="w-full max-w-[320px]" onClick={onContinue}>
                      Continue editing
                    </Button>
                    <Button variant="secondary" className="w-full max-w-[320px]" onClick={onStartFresh}>
                      Start fresh
                    </Button>
                  </div>
                </div>
              </div>
  );
}
