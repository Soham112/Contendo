import * as React from "react";
import { cn } from "@/lib/utils";

// A card (DESIGN.md "Cards & Lists"): a lighter sheet on the page, rounded,
// no border. `tone="low"` sits one step darker, for cards on a white surface.
export function Card({
  className, tone = "lowest", interactive = false, ...props
}: React.HTMLAttributes<HTMLDivElement> & { tone?: "lowest" | "low"; interactive?: boolean }) {
  return (
    <div
      className={cn(
        "rounded-2xl p-5 sm:p-6",
        tone === "lowest" ? "bg-surface-container-lowest" : "bg-surface-container-low",
        interactive && "transition-colors duration-150 ease-out hover:bg-surface-container-highest",
        className
      )}
      {...props}
    />
  );
}

/** A loading placeholder in the shape of the content it stands for. */
export function Skeleton({ className, ...props }: React.HTMLAttributes<HTMLDivElement>) {
  return <div aria-hidden="true" className={cn("rounded-lg bg-surface-container-high animate-pulse motion-reduce:animate-none", className)} {...props} />;
}
