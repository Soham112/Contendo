"use client";

import { useEffect, useRef, useState } from "react";
import { useApi } from "@/lib/api";
import type { useTracking } from "@/lib/useTracking";
import type { Visual } from "./config";

type Diagram = { position: number; description: string; svg_code: string | null };

/** The visuals panel's state: generate diagrams for the post's placeholders and track each one's chosen version. */
export function useVisuals({ logEvent, beforeGenerate, sourceText, saveDiagrams }: {
  logEvent: ReturnType<typeof useTracking>["logEvent"];
  /** Runs once generation starts, before the request (closes analysis, makes sure the post is saved). */
  beforeGenerate: () => Promise<void>;
  /** The post text with its [DIAGRAM:/IMAGE:] placeholders. */
  sourceText: () => string;
  saveDiagrams: (diagrams: Diagram[]) => Promise<void>;
}) {
  const api = useApi();
  const [visuals, setVisuals] = useState<Visual[]>([]);
  const [loading, setLoading] = useState(false);
  const [visible, setVisible] = useState(false);
  const [entered, setEntered] = useState(false);
  // Tracks currently-active SVG per diagram position for history patching
  const activeSvgs = useRef<Record<number, string>>({});

  // Drive slide-in animation for the visuals panel
  useEffect(() => {
    if (visible) {
      requestAnimationFrame(() => setEntered(true));
    } else {
      setEntered(false);
    }
  }, [visible]);

  const generate = async () => {
    logEvent({ event_type: "button_click", page_url: "/create", button_name: "generate_visuals_btn" });
    setLoading(true);
    setVisuals([]);
    await beforeGenerate();

    try {
      // Use the raw post (with [DIAGRAM:/IMAGE:] placeholders) so the backend can parse them
      const res = await api.generateVisuals(sourceText());
      if (!res.ok) throw new Error("Visuals generation failed");
      const data = await res.json();
      const newVisuals: Visual[] = data.visuals ?? [];
      setVisuals(newVisuals);

      // Seed the active-version tracker with initial SVGs
      const svgsByPosition: Record<number, string> = {};
      newVisuals.forEach((v) => {
        if (v.type === "diagram" && v.svg_code) {
          svgsByPosition[v.position] = v.svg_code;
        }
      });
      activeSvgs.current = svgsByPosition;

      const diagrams = newVisuals
        .filter((v) => v.type === "diagram" && v.svg_code)
        .map((v) => ({ position: v.position, description: v.description, svg_code: v.svg_code }));
      if (diagrams.length > 0) {
        await saveDiagrams(diagrams);
      }

      // Slide panel in after successful generation
      if (newVisuals.length > 0) {
        setVisible(true);
      }
    } catch {
      setVisuals([]);
    } finally {
      setLoading(false);
    }
  };

  const changeVersion = async (position: number, svgCode: string) => {
    activeSvgs.current[position] = svgCode;
    // Patch history with the active version for every diagram
    const diagrams = visuals
      .filter((v) => v.type === "diagram")
      .map((v) => ({
        position: v.position,
        description: v.description,
        svg_code: activeSvgs.current[v.position] ?? v.svg_code,
      }))
      .filter((d) => d.svg_code !== null);
    if (diagrams.length > 0) {
      await saveDiagrams(diagrams);
    }
  };

  /** Show saved visuals again. */
  const restore = (list: Visual[]) => {
    setVisuals(list);
    if (list.length > 0) setVisible(true);
  };

  const reset = () => {
    setVisuals([]);
    setVisible(false);
  };

  return { visuals, loading, visible, setVisible, entered, generate, changeVersion, restore, reset };
}
