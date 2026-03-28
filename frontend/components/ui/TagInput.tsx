"use client";

import { useState } from "react";

export interface TagInputProps {
  value: string[];
  onChange: (tags: string[]) => void;
  placeholder?: string;
  hint?: string;
}

export default function TagInput({ value, onChange, placeholder, hint }: TagInputProps) {
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
      <div className="flex flex-wrap gap-2 bg-[#f3f4f3] px-3 py-2.5 border-b border-b-[#aeb3b2] focus-within:border-b-[#58614f] focus-within:border-b-2 transition-all">
        {value.map((tag) => (
          <span
            key={tag}
            className="inline-flex items-center gap-1 bg-[#58614f]/15 text-[#58614f] text-[12px] font-medium px-2.5 py-0.5 rounded-full"
          >
            {tag}
            <button
              type="button"
              onClick={() => onChange(value.filter((t) => t !== tag))}
              className="opacity-60 hover:opacity-100 leading-none ml-0.5"
            >
              ×
            </button>
          </span>
        ))}
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={onKeyDown}
          onBlur={() => input && addTag(input)}
          placeholder={value.length === 0 ? placeholder : ""}
          className="flex-1 min-w-[140px] bg-transparent outline-none text-[14px] text-[#2f3333] placeholder-[#aeb3b2]"
        />
      </div>
      {hint && <p className="text-[11px] text-[#aeb3b2]">{hint}</p>}
    </div>
  );
}
