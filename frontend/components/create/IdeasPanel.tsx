"use client";

import { FORMAT_BADGE, type Suggestion } from "./config";

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
                      <p className="text-xs text-outline mt-0.5">
                        {focus.trim()
                          ? `Focused on: ${focus.trim()}`
                          : "Ideas drawn from your full knowledge base"}
                      </p>
                    )}
                  </div>
                  <div className="flex items-center gap-3">
                    {!loading && (
                      <button
                        onClick={onRefresh}
                        className="text-xs text-secondary hover:text-on-surface border border-surface-container-high rounded-lg px-2.5 py-1 transition-colors"
                      >
                        Refresh
                      </button>
                    )}
                    <button
                      onClick={onDismiss}
                      className="text-outline hover:text-on-surface transition-colors text-xl leading-none"
                    >
                      ×
                    </button>
                  </div>
                </div>

                {loading && (
                  <div className="px-5 py-6 text-sm text-outline">Thinking…</div>
                )}

                {!loading && suggestions.length === 0 && (
                  <div className="px-5 py-6 text-sm text-outline">
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
                          <div className="mt-1 flex items-center gap-2">
                            <span className="text-xs px-2 py-0.5 rounded-full bg-surface-container-low border border-surface-container-high text-outline">
                              {FORMAT_BADGE[s.format] ?? s.format}
                            </span>
                          </div>
                          <p className="mt-1 text-xs text-outline leading-relaxed">{s.angle}</p>
                        </div>
                        <button
                          onClick={() => onUse(s, i)}
                          className={`text-xs whitespace-nowrap rounded-lg px-3 py-1.5 transition-colors border flex-shrink-0 ${
                            selectedIndex === i
                              ? "border-surface-container-high bg-surface-container-lowest text-outline"
                              : "border-surface-container-high bg-surface-container-lowest text-secondary hover:bg-surface-container-low"
                          }`}
                        >
                          {selectedIndex === i ? "Selected" : "Use this"}
                        </button>
                      </div>
                    ))}
                  </div>
                )}
              </div>
  );
}
