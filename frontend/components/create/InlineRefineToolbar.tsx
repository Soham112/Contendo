"use client";

import type { KeyboardEvent, RefObject } from "react";
import { Button } from "@/components/ui/button";

/** The floating instruction box shown over a selected passage of the post. */
export default function InlineRefineToolbar({ rect, inputRef, instruction, onInstructionChange, onKeyDown, loading, onSubmit, onDismiss }: {
  rect: DOMRect | null;
  inputRef: RefObject<HTMLInputElement>;
  instruction: string;
  onInstructionChange: (value: string) => void;
  onKeyDown: (e: KeyboardEvent<HTMLInputElement>) => void;
  loading: boolean;
  onSubmit: () => void;
  onDismiss: () => void;
}) {
  return (
        <>
          <div
            onClick={onDismiss}
            style={{
              position: "fixed",
              inset: 0,
              zIndex: 999,
              background: "transparent",
            }}
          />

          <div
            style={{
              position: "fixed",
              top: (rect?.top ?? 200) - 56,
              // Centred on the selection, but kept 16px inside the screen edges.
              left: `clamp(calc(min(420px, 100vw - 32px) / 2 + 16px), ${(rect?.left ?? 0) + (rect?.width ?? 0) / 2}px, calc(100vw - min(420px, 100vw - 32px) / 2 - 16px))`,
              transform: "translateX(-50%)",
              zIndex: 1000,
              background: "rgba(243, 244, 243, 0.82)",
              borderRadius: "999px",
              padding: "8px 10px 8px 12px",
              display: "flex",
              alignItems: "center",
              gap: "8px",
              boxShadow:
                "0px 4px 20px rgba(47,51,51,0.08), 0px 12px 40px rgba(47,51,51,0.08)",
              width: "min(420px, calc(100vw - 32px))",
              backdropFilter: "blur(20px)",
              border: "1px solid rgba(174, 179, 178, 0.18)",
            }}
            onClick={(e) => e.stopPropagation()}
          >
            <input
              ref={inputRef}
              value={instruction}
              onChange={(e) => onInstructionChange(e.target.value)}
              onKeyDown={onKeyDown}
              aria-label="How should this passage change?"
              placeholder="How should this change?"
              disabled={loading}
              className="min-h-11 flex-1 bg-transparent text-[0.875rem] text-on-surface placeholder:text-placeholder focus:outline-none"
            />
            <Button size="sm" onClick={onSubmit} loading={loading} disabled={!instruction.trim()} className="rounded-full">
              Refine
            </Button>
            <Button variant="ghost" size="icon" onClick={onDismiss} aria-label="Cancel" className="h-9 w-9">
              ✕
            </Button>
          </div>
        </>
  );
}
