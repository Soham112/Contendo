"use client";

// Small UI hooks for the create screen's layout: the resizable split view and
// the "Saved just now" line.

import { useEffect, useRef, useState, type MouseEvent as ReactMouseEvent } from "react";

/** The post/analysis split: its ratio, whether the window is wide enough, and the drag handler. */
export function useSplitLayout() {
  const [splitRatio, setSplitRatio] = useState(0.75);
  const [isWide, setIsWide] = useState(true);
  const splitContainerRef = useRef<HTMLDivElement>(null);

  // Responsive width detection
  useEffect(() => {
    const check = () => setIsWide(window.innerWidth >= 900);
    check();
    window.addEventListener("resize", check);
    return () => window.removeEventListener("resize", check);
  }, []);

  const handleDragStart = (e: ReactMouseEvent) => {
    e.preventDefault();
    const startX = e.clientX;
    const startRatio = splitRatio;
    const containerWidth = splitContainerRef.current?.offsetWidth ?? window.innerWidth;

    const onMouseMove = (ev: MouseEvent) => {
      const delta = ev.clientX - startX;
      const newRatio = startRatio + delta / containerWidth;
      setSplitRatio(Math.min(0.82, Math.max(0.35, newRatio)));
    };
    const onMouseUp = () => {
      document.removeEventListener("mousemove", onMouseMove);
      document.removeEventListener("mouseup", onMouseUp);
    };
    document.addEventListener("mousemove", onMouseMove);
    document.addEventListener("mouseup", onMouseUp);
  };

  return { splitRatio, setSplitRatio, isWide, splitContainerRef, handleDragStart };
}

/** "Saved just now" / "Saved 3m ago" for the last save time, refreshed every 10 seconds. */
export function useSaveStatus(lastSaved: number | null): string {
  const [saveStatusText, setSaveStatusText] = useState("");

  useEffect(() => {
    if (!lastSaved) {
      setSaveStatusText("");
      return;
    }
    const update = () => {
      const diff = Math.floor((Date.now() - lastSaved) / 1000);
      if (diff < 60) setSaveStatusText("Saved just now");
      else setSaveStatusText(`Saved ${Math.floor(diff / 60)}m ago`);
    };
    update();
    const interval = setInterval(update, 10000);
    return () => clearInterval(interval);
  }, [lastSaved]);

  return saveStatusText;
}
