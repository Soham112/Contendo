"use client";

import * as React from "react";
import { Slot } from "@radix-ui/react-slot";
import type { VariantProps } from "class-variance-authority";
import { buttonVariants } from "./button-variants";
import { cn } from "@/lib/utils";

export interface ButtonProps
  extends React.ButtonHTMLAttributes<HTMLButtonElement>,
    VariantProps<typeof buttonVariants> {
  /** Render the child element (e.g. a Link) with the button's styles. */
  asChild?: boolean;
  /** Shows a spinner, keeps the label, and blocks clicks. */
  loading?: boolean;
  /** When disabled, the label says what is missing instead of fading out, e.g. "Add a topic to continue". */
  disabledReason?: string;
}

function Spinner() {
  return (
    <span
      aria-hidden="true"
      className="h-4 w-4 shrink-0 rounded-full border-2 border-current border-r-transparent animate-spin motion-reduce:animate-none"
    />
  );
}

export const Button = React.forwardRef<HTMLButtonElement, ButtonProps>(
  ({ className, variant, size, asChild = false, loading = false, disabled, disabledReason, children, ...props }, ref) => {
    const Comp = asChild ? Slot : "button";
    const blocked = disabled || loading;
    const label = disabled && !loading && disabledReason ? disabledReason : children;
    if (asChild) {
      return <Comp ref={ref} className={cn(buttonVariants({ variant, size }), className)} {...props}>{children}</Comp>;
    }
    return (
      <Comp
        ref={ref}
        // A disabled reason can be longer than the label: let it wrap rather than overflow on phones.
        className={cn(buttonVariants({ variant, size }), label !== children && "whitespace-normal py-2 text-center", className)}
        disabled={blocked}
        aria-busy={loading || undefined}
        type={props.type ?? "button"}
        {...props}
      >
        {loading && <Spinner />}
        {label}
      </Comp>
    );
  }
);
Button.displayName = "Button";

export { buttonVariants };
