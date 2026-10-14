"use client";

import { useState } from "react";
import { useApi } from "@/lib/api";
import { SS_IDEAS, type Suggestion } from "./config";

// How many ideas to ask for. No focus topic: ideas come from the whole knowledge base.
const IDEA_COUNT = 8;
const IDEA_FOCUS = "";

/** The ideas panel's state: fetch, restore, pick and dismiss post ideas. */
export function useIdeas(onPick: (suggestion: Suggestion) => void) {
  const api = useApi();
  const [suggestions, setSuggestions] = useState<Suggestion[]>([]);
  const [visible, setVisible] = useState(false);
  const [loading, setLoading] = useState(false);
  const [selectedIndex, setSelectedIndex] = useState<number | null>(null);

  /** Show a saved list again (nothing happens for an empty one). */
  const restore = (list: Suggestion[]) => {
    if (list.length > 0) { setSuggestions(list); setVisible(true); }
  };

  const reset = () => {
    setSuggestions([]);
    setVisible(false);
    setSelectedIndex(null);
  };

  const refresh = async () => {
    setLoading(true);
    setVisible(true);
    setSuggestions([]);
    setSelectedIndex(null);
    try {
      const res = await api.getSuggestions(IDEA_COUNT, IDEA_FOCUS.trim() || undefined);
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
      setLoading(false);
    }
  };

  const use = (suggestion: Suggestion, index: number) => {
    onPick(suggestion);
    setSelectedIndex(index);
  };

  const dismiss = () => {
    reset();
    try { sessionStorage.removeItem(SS_IDEAS); } catch { /* ignore */ }
  };

  return { suggestions, visible, loading, selectedIndex, focus: IDEA_FOCUS, restore, reset, refresh, use, dismiss };
}
