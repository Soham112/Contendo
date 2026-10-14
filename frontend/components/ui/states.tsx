"use client";

// The three states every data screen has besides "filled": loading
// (skeletons in the content's shape, see Skeleton in ./card), empty (what to
// do next) and error (what went wrong, in plain words, with a retry).

import * as React from "react";
import { AnimatePresence, motion } from "motion/react";
import { AlertCircle, Check } from "lucide-react";
import { cn } from "@/lib/utils";
import { Button } from "./button";
import { Skeleton } from "./card";
import { riseIn, transition } from "./motion";

export function EmptyState({ title, body, action, className }: {
  title: string;
  body?: React.ReactNode;
  /** The next step, usually a Button. */
  action?: React.ReactNode;
  className?: string;
}) {
  return (
    <div className={cn("rounded-2xl bg-surface-container-low px-6 py-10 text-center", className)}>
      <h2 className="font-headline text-[1.25rem] text-on-surface">{title}</h2>
      {body && <p className="mx-auto mt-2 max-w-md text-[0.9375rem] leading-relaxed text-on-surface-variant">{body}</p>}
      {action && <div className="mt-6 flex justify-center">{action}</div>}
    </div>
  );
}

export function ErrorState({ message, onRetry, retrying = false, className }: {
  /** What went wrong, in words the user understands. */
  message: string;
  onRetry?: () => void;
  retrying?: boolean;
  className?: string;
}) {
  return (
    <div role="alert" className={cn("flex flex-col items-start gap-4 rounded-2xl bg-surface-container-low px-5 py-5 sm:flex-row sm:items-center", className)}>
      <AlertCircle size={20} aria-hidden="true" className="shrink-0 text-error" />
      <p className="flex-1 text-[0.9375rem] leading-relaxed text-on-surface">{message}</p>
      {onRetry && (
        <Button variant="secondary" size="sm" onClick={onRetry} loading={retrying}>
          Try again
        </Button>
      )}
    </div>
  );
}

/** Rows of skeleton lines for a loading list. */
export function ListSkeleton({ rows = 3, className }: { rows?: number; className?: string }) {
  return (
    <div role="status" aria-label="Loading" className={cn("flex flex-col gap-3", className)}>
      {Array.from({ length: rows }, (_, i) => (
        <div key={i} className="rounded-2xl bg-surface-container-low px-5 py-5">
          <Skeleton className="h-4 w-2/5" />
          <Skeleton className="mt-3 h-3 w-4/5" />
          <Skeleton className="mt-2 h-3 w-3/5" />
        </div>
      ))}
    </div>
  );
}

/**
 * Steps of a long-running job (e.g. writing a post); the last step stays
 * active until the job finishes.
 *
 * STOPGAP: the steps advance on a timer, because /generate returns only when
 * it is done and reports no progress. Proper fix: stream the pipeline's node
 * completions from the backend (LangGraph can stream them; serve them as
 * server-sent events) and advance a step when its node finishes.
 */
export function ProgressSteps({ steps, title, stepMs = 4000 }: { steps: string[]; title: string; stepMs?: number }) {
  const [active, setActive] = React.useState(0);
  React.useEffect(() => {
    const timer = setInterval(() => setActive((i) => Math.min(i + 1, steps.length - 1)), stepMs);
    return () => clearInterval(timer);
  }, [steps.length, stepMs]);

  return (
    <div role="status" aria-live="polite" className="mx-auto w-full max-w-sm py-16">
      <p className="font-headline text-[1.25rem] text-on-surface text-center">{title}</p>
      <ol className="mt-8 flex flex-col gap-4">
        {steps.map((step, i) => {
          const state = i < active ? "done" : i === active ? "active" : "todo";
          return (
            <li key={step} className="flex items-center gap-3" aria-current={state === "active" ? "step" : undefined}>
              <span
                aria-hidden="true"
                className={cn(
                  "grid h-6 w-6 shrink-0 place-items-center rounded-full text-[0.75rem]",
                  state === "done" && "bg-primary text-white",
                  state === "active" && "bg-primary-container text-on-primary-container",
                  state === "todo" && "bg-surface-container-high text-on-surface-variant"
                )}
              >
                {state === "done" ? <Check size={14} /> : state === "active" ? (
                  <span className="h-2 w-2 rounded-full bg-primary animate-pulse motion-reduce:animate-none" />
                ) : i + 1}
              </span>
              <AnimatePresence mode="wait" initial={false}>
                <motion.span
                  key={state}
                  {...riseIn}
                  transition={transition.fast}
                  className={cn("text-[0.9375rem]", state === "todo" ? "text-on-surface-variant" : "text-on-surface", state === "active" && "font-medium")}
                >
                  {step}
                  <span className="sr-only">{state === "done" ? " (done)" : state === "active" ? " (in progress)" : ""}</span>
                </motion.span>
              </AnimatePresence>
            </li>
          );
        })}
      </ol>
    </div>
  );
}
