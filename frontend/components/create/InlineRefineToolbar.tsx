"use client";

import type { KeyboardEvent, RefObject } from "react";

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
              left:
                (rect?.left ?? 0) +
                (rect?.width ?? 0) / 2,
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
              minWidth: "320px",
              maxWidth: "420px",
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
              placeholder="Edit instruction..."
              disabled={loading}
              style={{
                flex: 1,
                background: "transparent",
                border: "none",
                outline: "none",
                color: "#2f3333",
                fontSize: "13px",
                fontFamily: "var(--font-body), sans-serif",
              }}
            />
            <button
              onClick={onSubmit}
              disabled={loading || !instruction.trim()}
              style={{
                background: "linear-gradient(135deg, #58614f 0%, #4c5543 100%)",
                border: "none",
                borderRadius: "999px",
                color: "#ffffff",
                fontSize: "13px",
                padding: "6px 12px",
                cursor: loading ? "wait" : "pointer",
                opacity: !instruction.trim() || loading ? 0.5 : 1,
                fontFamily: "var(--font-body), sans-serif",
              }}
            >
              {loading ? "..." : "→"}
            </button>
            <button
              onClick={onDismiss}
              style={{
                background: "transparent",
                border: "none",
                color: "#777c7b",
                fontSize: "13px",
                padding: "4px 6px",
                cursor: "pointer",
                fontFamily: "var(--font-body), sans-serif",
              }}
            >
              ✕
            </button>
          </div>
        </>
  );
}
