"use client";

// Form controls (DESIGN.md §5 "Input Fields"): a soft fill with a bottom
// border in `outline` (3:1 against its surroundings, WCAG 1.4.11) that turns
// sage and thicker on focus. Every control is 44px tall or more.

import * as React from "react";
import * as LabelPrimitive from "@radix-ui/react-label";
import { cn } from "@/lib/utils";

const control = [
  "w-full bg-surface-container-low text-on-surface text-[1rem] placeholder:text-placeholder",
  "border-0 border-b-[1.5px] border-outline rounded-t-md rounded-b-none",
  "transition-[border-color,box-shadow] duration-150 ease-out",
  "focus:outline-none focus-visible:outline-none focus:border-b-2 focus:border-primary focus-visible:ring-2 focus-visible:ring-primary/30",
  "disabled:cursor-not-allowed disabled:text-on-surface-variant",
  "aria-[invalid=true]:border-error",
];

export const Input = React.forwardRef<HTMLInputElement, React.InputHTMLAttributes<HTMLInputElement>>(
  ({ className, type = "text", ...props }, ref) => (
    <input ref={ref} type={type} className={cn(control, "min-h-11 px-3.5 py-2.5", className)} {...props} />
  )
);
Input.displayName = "Input";

export const Textarea = React.forwardRef<HTMLTextAreaElement, React.TextareaHTMLAttributes<HTMLTextAreaElement>>(
  ({ className, ...props }, ref) => (
    <textarea ref={ref} className={cn(control, "min-h-24 px-3.5 py-3 leading-relaxed", className)} {...props} />
  )
);
Textarea.displayName = "Textarea";

/** The label above a control (DESIGN.md "Labels & Metadata": small caps). */
export const Label = React.forwardRef<
  React.ElementRef<typeof LabelPrimitive.Root>,
  React.ComponentPropsWithoutRef<typeof LabelPrimitive.Root>
>(({ className, ...props }, ref) => (
  <LabelPrimitive.Root ref={ref} className={cn("label-caps block text-on-surface-variant mb-2", className)} {...props} />
));
Label.displayName = "Label";

/** A hint or error line under a control. Pass its id to the control's aria-describedby. */
export function FieldMessage({ id, error, children }: { id?: string; error?: boolean; children: React.ReactNode }) {
  return (
    <p id={id} role={error ? "alert" : undefined} className={cn("mt-1.5 text-[0.8125rem]", error ? "text-error" : "text-on-surface-variant")}>
      {children}
    </p>
  );
}
