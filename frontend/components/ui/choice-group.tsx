"use client";

// A set of mutually exclusive choices drawn as tiles. Each tile is a real
// radio input, so arrow keys move between options and screen readers announce
// "radio, 2 of 3, checked". Unselected tiles have a 3:1 border (WCAG 1.4.11).

import { useId } from "react";
import { cn } from "@/lib/utils";

export interface Choice<T extends string> {
  value: T;
  label: string;
  /** A second, smaller line, e.g. "~200-300 words". */
  hint?: string;
}

export function ChoiceGroup<T extends string>({ legend, value, onChange, options, className, tileClassName }: {
  legend: string;
  value: T;
  onChange: (value: T) => void;
  options: readonly Choice<T>[];
  /** Layout of the tiles, e.g. "grid grid-cols-3 gap-2". */
  className?: string;
  tileClassName?: string;
}) {
  const name = useId();
  return (
    <fieldset>
      <legend className="label-caps mb-2.5 text-on-surface-variant">{legend}</legend>
      <div className={cn("flex flex-wrap gap-2", className)}>
        {options.map((option) => (
          <label key={option.value} className="relative block cursor-pointer">
            <input
              type="radio"
              name={name}
              value={option.value}
              checked={value === option.value}
              onChange={() => onChange(option.value)}
              className="peer sr-only"
            />
            <span
              className={cn(
                "flex h-full min-h-11 flex-col justify-center rounded-md border px-3.5 py-2 text-left text-[0.875rem] leading-tight",
                "border-outline bg-surface-container-lowest text-on-surface transition-colors duration-150 ease-out hover:bg-surface-container-low",
                "peer-checked:border-primary peer-checked:bg-primary peer-checked:text-white peer-checked:font-medium",
                "peer-focus-visible:ring-2 peer-focus-visible:ring-primary peer-focus-visible:ring-offset-2 peer-focus-visible:ring-offset-background",
                tileClassName
              )}
            >
              {option.label}
              {option.hint && <span className="mt-0.5 text-[0.75rem] font-normal opacity-80">{option.hint}</span>}
            </span>
          </label>
        ))}
      </div>
    </fieldset>
  );
}
