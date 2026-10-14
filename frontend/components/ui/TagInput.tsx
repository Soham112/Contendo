"use client";

import { useState } from "react";

export interface TagInputProps {
  /** For the field's label (htmlFor). */
  id?: string;
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  hint?: string;
}

export default function TagInput({ id, value, onChange, placeholder, hint }: TagInputProps) {
  const [input, setInput] = useState("");

  function addTag(raw: string) {
    const tag = raw.trim();
    if (tag && !value.includes(tag)) onChange([...value, tag]);
    setInput("");
  }

  function onKeyDown(e: React.KeyboardEvent<HTMLInputElement>) {
    if (e.key === "Enter" || e.key === ",") {
      e.preventDefault();
      addTag(input);
    } else if (e.key === "Backspace" && input === "" && value.length > 0) {
      onChange(value.slice(0, -1));
    }
  }

  return (
    <div className="flex flex-col gap-2">
      {/* Pills + input container — matches input-editorial style */}
      <div className="flex min-h-11 flex-wrap items-center gap-2 bg-surface-container-lowest rounded-t-md px-3 py-0.5 border-b-[1.5px] border-b-outline focus-within:border-b-primary focus-within:border-b-2 transition-colors">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 bg-primary-container text-on-primary-fixed text-[0.8125rem] font-medium pl-2.5 rounded-full"
          >
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((t) => t !== tag))}
              aria-label={`Remove ${tag}`}
              className="relative grid h-8 w-8 place-items-center rounded-full leading-none hover:bg-primary/15 after:absolute after:-inset-1.5 after:content-['']"
            >
              ×
            </button>
          </span>
        ))}
        <input
          id={id}
          aria-describedby={hint && id ? `${id}-hint` : undefined}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => input && addTag(input)}
          placeholder={value.length === 0 ? placeholder : ""}
          className="flex-1 min-w-[140px] min-h-11 bg-transparent outline-none text-[0.9375rem] text-on-surface placeholder:text-placeholder"
        />
      </div>
      {hint && <p id={id ? `${id}-hint` : undefined} className="text-[0.75rem] text-on-surface-variant">{hint}</p>}
    </div>
  );
}
