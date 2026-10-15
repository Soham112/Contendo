"use client";

import { type Suggestion } from "./config";
import { Button } from "@/components/ui/button";

/** Post ideas drawn from the user's memory, each with a "Use this" button. */
export default function IdeasPanel({ loading, suggestions, focus, selectedIndex, onRefresh, onDismiss, onUse }: {
  loading: boolean;
  suggestions: Suggestion[];
  /** The topic the ideas were focused on, if any. */
  focus: string;
  selectedIndex: number | null;
  onRefresh: () => void;
  onDismiss: () => void;
  onUse: (suggestion: Suggestion, index: number) => void;
}) {
  return (
              <div className="rounded-xl border border-surface-container-high bg-surface-container-lowest overflow-hidden mb-6">
                <div className="flex items-center justify-between px-5 py-3 border-b border-surface-container-high">
                  <div>
                    <p className="text-sm font-medium text-on-surface">
                      {loading
                        ? "Finding ideas…"
                        : `${suggestions.length} idea${suggestions.length !== 1 ? "s" : ""} from your memory`}
                    </p>
                    {!loading && (
                      <p className="text-xs text-on-surface-variant mt-0.5">
                        {focus.trim()
                          ? `Focused on: ${focus.trim()}`
                          : "Ideas drawn from your full knowledge base"}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    {!loading && (
                      <Button variant="secondary" size="sm"
                        onClick={onRefresh}
                      >
                        Refresh
                      </Button>
                    )}
                    <Button variant="ghost" size="icon" onClick={onDismiss} aria-label="Close ideas" className="text-xl">
                      ×
                    </Button>
                  </div>
                </div>

                {loading && (
                  <div className="px-5 py-6 text-sm text-on-surface-variant">Thinking…</div>
                )}

                {!loading && suggestions.length === 0 && (
                  <div className="px-5 py-6 text-sm text-on-surface-variant">
                    No suggestions returned. Try adding more content to your memory first.
                  </div>
                )}

                {!loading && suggestions.length > 0 && (
                  <div className="divide-y divide-surface-container-high">
                    {suggestions.map((s, i) => (
                      <div
                        key={i}
                        className={`px-5 py-4 flex items-start justify-between gap-4 transition-colors ${
                          selectedIndex === i ? "bg-surface-container-low" : ""
                        }`}
                      >
                        <div className="flex-1 min-w-0">
                          <div className="flex items-center gap-2">
                            {selectedIndex === i && (
                              <span className="text-primary text-xs font-medium">✓</span>
                            )}
                            <p className="text-sm font-medium text-on-surface leading-snug">{s.title}</p>
                          </div>
                          <p className="mt-1 text-xs text-on-surface-variant leading-relaxed">{s.angle}</p>
                        </div>
                        <Button
                          variant={selectedIndex === i ? "secondary" : "primary"}
                          size="sm"
                          onClick={() => onUse(s, i)}
                          aria-pressed={selectedIndex === i}
                          className="shrink-0"
                        >
                          {selectedIndex === i ? "Selected" : "Use this"}
                        </Button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
  );
}
