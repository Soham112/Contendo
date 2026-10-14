"use client";

import type { CSSProperties } from "react";

const actionBtnStyle = (disabled?: boolean): CSSProperties => ({
  display: "flex",
  flexDirection: "column",
  alignItems: "center",
  gap: 6,
  background: "rgba(255,255,255,0.78)",
  borderRadius: 14,
  padding: "12px 14px",
  border: "none",
  cursor: disabled ? "not-allowed" : "pointer",
  backdropFilter: "blur(20px)",
  opacity: disabled ? 0.5 : 1,
  transition: "background 0.15s",
  boxShadow: "0 1px 4px rgba(47,51,51,0.06)",
  minWidth: 52,
});

/** The column of post actions: regenerate, analyse, visuals and the copy buttons. */
export default function PostActionButtons({
  compact, row = false, loading, visualsLoading, visualsVisible, hasVisuals, copiedLinkedIn, copiedMedium,
  onRegenerate, onAnalyse, onShowVisuals, onHideVisuals, onGenerateVisuals, onCopyLinkedIn, onCopyMedium,
}: {
  /** Split view: smaller, borderless buttons. */
  compact: boolean;
  /** A horizontal row (phones and tablets) instead of a column. */
  row?: boolean;
  loading: boolean;
  visualsLoading: boolean;
  visualsVisible: boolean;
  hasVisuals: boolean;
  copiedLinkedIn: boolean;
  copiedMedium: boolean;
  onRegenerate: () => void;
  onAnalyse: () => void;
  onShowVisuals: () => void;
  onHideVisuals: () => void;
  onGenerateVisuals: () => void;
  onCopyLinkedIn: () => void;
  onCopyMedium: () => void;
}) {
  const iconSize = compact ? 16 : 22;
  const btnGap = compact ? 16 : 32;
  const btnLabelStyle: CSSProperties = {
    fontSize: compact ? 10 : 11,
    letterSpacing: "0.08em",
    textTransform: "uppercase",
    color: "#5b605f",
    fontWeight: 500,
  };

  return (
    <div
      role="toolbar"
      aria-label="Post actions"
      style={row
        ? { display: "flex", flexDirection: "row", gap: 8, overflowX: "auto", paddingBottom: 4 }
        : { display: "flex", flexDirection: "column", gap: btnGap, alignItems: "center" }}
    >
      <button
        onClick={onRegenerate}
        disabled={loading}
        title="Regenerate"
        style={compact ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: loading ? "not-allowed" : "pointer", opacity: loading ? 0.5 : 1, padding: "4px 6px", borderRadius: 8 } : actionBtnStyle(loading)}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M1 4v6h6" /><path d="M3.51 15a9 9 0 1 0 .49-4" />
        </svg>
        <span style={btnLabelStyle}>Regenerate</span>
      </button>

      <button
        onClick={onAnalyse}
        title="Analyse"
        style={compact ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: "pointer", padding: "4px 6px", borderRadius: 8 } : actionBtnStyle()}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <rect x="3" y="12" width="4" height="9" /><rect x="10" y="7" width="4" height="14" /><rect x="17" y="3" width="4" height="18" />
        </svg>
        <span style={btnLabelStyle}>Analyse</span>
      </button>

      <button
        onClick={
          visualsLoading
            ? undefined
            : visualsVisible
            ? onHideVisuals
            : hasVisuals
            ? onShowVisuals
            : onGenerateVisuals
        }
        disabled={visualsLoading}
        title={visualsLoading ? "Generating visuals…" : visualsVisible ? "Hide visuals" : "Generate visuals"}
        style={compact ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: visualsLoading ? "not-allowed" : "pointer", opacity: visualsLoading ? 0.5 : 1, padding: "4px 6px", borderRadius: 8 } : actionBtnStyle(visualsLoading)}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <rect x="3" y="3" width="18" height="18" rx="2" ry="2" />
          <circle cx="8.5" cy="8.5" r="1.5" />
          <polyline points="21 15 16 10 5 21" />
        </svg>
        <span style={btnLabelStyle}>{visualsLoading ? "Generating" : visualsVisible ? "Hide" : "Visuals"}</span>
      </button>

      <button
        onClick={onCopyLinkedIn}
        title="Copy for LinkedIn"
        style={compact ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: "pointer", padding: "4px 6px", borderRadius: 8 } : actionBtnStyle()}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M16 8a6 6 0 0 0-12 0v8a6 6 0 0 0 12 0" />
          <path d="M8 8v8" />
        </svg>
        <span style={btnLabelStyle}>{copiedLinkedIn ? "Copied!" : "LinkedIn"}</span>
      </button>

      <button
        onClick={onCopyMedium}
        title="Copy for Medium"
        style={compact ? { display: "flex", flexDirection: "column", alignItems: "center", gap: 5, background: "none", border: "none", cursor: "pointer", padding: "4px 6px", borderRadius: 8 } : actionBtnStyle()}
      >
        <svg width={iconSize} height={iconSize} viewBox="0 0 24 24" fill="none" stroke="#2f3333" strokeWidth="2">
          <path d="M4 4h16v16H4z" />
          <path d="M8 8l3.5 5L15 8" />
        </svg>
        <span style={btnLabelStyle}>{copiedMedium ? "Copied!" : "Medium"}</span>
      </button>
    </div>
  );
}
