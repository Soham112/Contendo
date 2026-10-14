// The button classes, in a plain module (not "use client") so server
// components can style a Link as a button too: buttonVariants({ variant: "cta" }).

import { cva } from "class-variance-authority";

// The one button system (DESIGN.md §5 and the 2026-10-13 addendum):
// - primary: sage gradient, the main action inside the app.
// - cta: terracotta, the main call to action on public and upgrade screens.
// - secondary: quiet and outlined, for actions beside a primary one; reads on any surface.
// - ghost: no fill or border, for icon-only buttons such as close.
// - tertiary: text with an underline, for low-emphasis actions.
// - destructive: for deleting or disconnecting.
// Disabled buttons stay readable (AA contrast) instead of fading out.
export const buttonVariants = cva(
  [
    "relative inline-flex items-center justify-center gap-2 whitespace-nowrap font-medium select-none",
    "transition-[background-color,color,box-shadow,opacity] duration-150 ease-out",
    "focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-primary focus-visible:ring-offset-2 focus-visible:ring-offset-background",
    "disabled:cursor-not-allowed aria-busy:cursor-wait",
  ],
  {
    variants: {
      variant: {
        primary:
          "btn-primary text-white hover:brightness-110 disabled:bg-none disabled:bg-surface-container-high disabled:text-on-surface-variant disabled:hover:brightness-100",
        cta:
          "bg-tertiary text-on-tertiary hover:bg-tertiary-dim disabled:bg-surface-container-high disabled:text-on-surface-variant",
        secondary:
          "border border-outline-variant bg-transparent text-on-surface hover:bg-surface-container-high disabled:text-on-surface-variant disabled:hover:bg-transparent",
        ghost:
          "bg-transparent text-on-surface-variant hover:bg-surface-container-high hover:text-on-surface disabled:text-on-surface-variant disabled:hover:bg-transparent",
        tertiary:
          "bg-transparent text-on-surface underline decoration-tertiary-fixed-dim underline-offset-4 hover:decoration-tertiary hover:decoration-2 disabled:text-on-surface-variant disabled:no-underline",
        destructive:
          "bg-error text-white hover:bg-on-error-container disabled:bg-surface-container-high disabled:text-on-surface-variant",
      },
      size: {
        // 44px tall on phones for the touch target, a little tighter on larger screens.
        sm: "min-h-11 sm:min-h-9 px-3.5 text-[0.8125rem] rounded-md",
        md: "min-h-11 px-5 text-[0.9375rem] rounded-md",
        lg: "min-h-12 px-7 text-[1rem] rounded-md",
        icon: "h-11 w-11 rounded-md",
      },
    },
    compoundVariants: [{ variant: "tertiary", class: "px-1" }],
    defaultVariants: { variant: "primary", size: "md" },
  }
);
