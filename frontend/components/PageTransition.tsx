"use client";

import { useEffect, useState } from "react";

// A short fade-and-rise when a page opens (200ms, ease-out; fade only when
// the user asks for reduced motion). The settled state must be
// `transform: none`, not translateY(0): any other transform makes this element
// the containing block for position: fixed children, and the create screen's
// split view is position: fixed.
export default function PageTransition({ children }: { children: React.ReactNode }) {
  const [entered, setEntered] = useState(false);
  const [reduced, setReduced] = useState(false);

  useEffect(() => {
    setReduced(window.matchMedia?.("(prefers-reduced-motion: reduce)").matches ?? false);
    const frame = requestAnimationFrame(() => setEntered(true));
    return () => cancelAnimationFrame(frame);
  }, []);

  return (
    <div
      style={{
        opacity: entered ? 1 : 0,
        transform: entered || reduced ? "none" : "translateY(8px)",
        transition: reduced ? "opacity 150ms ease-out" : "opacity 200ms ease-out, transform 200ms ease-out",
      }}
    >
      {children}
    </div>
  );
}
