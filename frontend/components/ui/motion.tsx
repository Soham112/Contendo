"use client";

// Motion settings shared by every animated part of the app: 150–250ms,
// ease-out, no bounce. MotionConfig with reducedMotion="user" turns movement
// off for people who ask their system for reduced motion (opacity changes
// stay, so things still appear and disappear).

import { MotionConfig, type Transition } from "motion/react";
import type { ReactNode } from "react";

/** Ease-out (CSS "ease-out"). */
export const EASE_OUT: [number, number, number, number] = [0, 0, 0.58, 1];

export const transition = {
  fast: { duration: 0.15, ease: EASE_OUT } satisfies Transition,
  base: { duration: 0.2, ease: EASE_OUT } satisfies Transition,
  slow: { duration: 0.25, ease: EASE_OUT } satisfies Transition,
};

/** Fade in while rising a few pixels: steps, toasts, a freshly generated post. */
export const riseIn = {
  initial: { opacity: 0, y: 8 },
  animate: { opacity: 1, y: 0 },
  exit: { opacity: 0, y: -4 },
};

export function MotionProvider({ children }: { children: ReactNode }) {
  return (
    <MotionConfig reducedMotion="user" transition={transition.base}>
      {children}
    </MotionConfig>
  );
}
