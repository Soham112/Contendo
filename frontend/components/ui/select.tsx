"use client";

// A dropdown (Radix Select: keyboard and screen-reader support), styled like
// the other form controls.

import * as React from "react";
import * as SelectPrimitive from "@radix-ui/react-select";
import { Check, ChevronDown } from "lucide-react";
import { cn } from "@/lib/utils";

export interface SelectOption {
  value: string;
  label: string;
}

export function Select({
  id, value, onValueChange, options, placeholder, disabled, className, "aria-label": ariaLabel, "aria-describedby": describedBy,
}: {
  id?: string;
  value: string;
  onValueChange: (value: string) => void;
  options: SelectOption[];
  placeholder?: string;
  disabled?: boolean;
  className?: string;
  "aria-label"?: string;
  "aria-describedby"?: string;
}) {
  return (
    <SelectPrimitive.Root value={value || undefined} onValueChange={onValueChange} disabled={disabled}>
      <SelectPrimitive.Trigger
        id={id}
        aria-label={ariaLabel}
        aria-describedby={describedBy}
        className={cn(
          "flex min-h-11 w-full items-center justify-between gap-2 rounded-t-md rounded-b-none bg-surface-container-low px-3.5 py-2.5 text-left text-[1rem] text-on-surface",
          "border-0 border-b-[1.5px] border-outline transition-[border-color] duration-150 ease-out",
          "focus:outline-none focus-visible:ring-2 focus-visible:ring-primary/30 data-[state=open]:border-b-2 data-[state=open]:border-primary",
          "disabled:cursor-not-allowed disabled:text-on-surface-variant data-[placeholder]:text-placeholder",
          className
        )}
      >
        <SelectPrimitive.Value placeholder={placeholder} />
        <SelectPrimitive.Icon asChild>
          <ChevronDown size={16} aria-hidden="true" className="shrink-0 text-on-surface-variant" />
        </SelectPrimitive.Icon>
      </SelectPrimitive.Trigger>
      <SelectPrimitive.Portal>
        <SelectPrimitive.Content
          position="popper"
          sideOffset={4}
          className="z-[300] max-h-72 min-w-[var(--radix-select-trigger-width)] overflow-hidden rounded-xl bg-surface-container-lowest shadow-ambient"
        >
          <SelectPrimitive.Viewport className="p-1">
            {options.map((option) => (
              <SelectPrimitive.Item
                key={option.value}
                value={option.value}
                className="relative flex min-h-11 cursor-pointer select-none items-center rounded-lg py-2 pl-9 pr-3 text-[0.9375rem] text-on-surface outline-none data-[highlighted]:bg-surface-container-low data-[state=checked]:font-medium"
              >
                <SelectPrimitive.ItemIndicator className="absolute left-3">
                  <Check size={16} aria-hidden="true" className="text-primary" />
                </SelectPrimitive.ItemIndicator>
                <SelectPrimitive.ItemText>{option.label}</SelectPrimitive.ItemText>
              </SelectPrimitive.Item>
            ))}
          </SelectPrimitive.Viewport>
        </SelectPrimitive.Content>
      </SelectPrimitive.Portal>
    </SelectPrimitive.Root>
  );
}
