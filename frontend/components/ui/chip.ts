// The one style for toggle chips (a choice among several, or an on/off tag):
// a bordered pill, solid sage when selected. A plain module so server and
// client components can both use it. Pair it with aria-pressed.

import { cn } from "@/lib/utils";

export function chipClass(selected: boolean, className?: string): string {
  return cn(
    "inline-flex min-h-11 sm:min-h-9 shrink-0 items-center gap-1.5 rounded-full border px-4 text-[0.875rem] transition-colors duration-150 ease-out",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    selected
      ? "border-primary bg-primary text-white font-medium"
      : "border-outline bg-surface-container-lowest text-on-surface hover:bg-surface-container-low",
    className
  );
}
