// Reading and writing the post editor's DOM (a contenteditable div that shows
// [DIAGRAM:]/[IMAGE:] placeholders as blocks).

export function getSelectionOffsetsWithin(node: HTMLElement) {
  const selection = window.getSelection();
  if (!selection || selection.rangeCount === 0 || selection.isCollapsed) return null;

  const range = selection.getRangeAt(0);
  if (!node.contains(range.commonAncestorContainer)) return null;

  const preRange = document.createRange();
  preRange.selectNodeContents(node);
  preRange.setEnd(range.startContainer, range.startOffset);

  const selectedText = range.toString();
  const start = preRange.toString().length;

  return {
    start,
    end: start + selectedText.length,
    text: selectedText,
  };
}

// ─── Placeholder block helpers ────────────────────────────────────────────────

export const PLACEHOLDER_RE = /\[(DIAGRAM|IMAGE):([^\]]+)\]/gi;

/** Imperatively populates the contentEditable editor with text + styled placeholder blocks. */
export function setEditorContent(editor: HTMLDivElement, text: string): void {
  editor.innerHTML = "";
  PLACEHOLDER_RE.lastIndex = 0;
  let lastIndex = 0;
  let match: RegExpExecArray | null;

  while ((match = PLACEHOLDER_RE.exec(text)) !== null) {
    if (match.index > lastIndex) {
      editor.appendChild(document.createTextNode(text.slice(lastIndex, match.index)));
    }
    const kind = match[1].toUpperCase();
    const placeholder = match[0];
    const labelText =
      kind === "DIAGRAM" ? "📊 Visual will appear here" : "🖼 Image reminder will appear here";

    const block = document.createElement("div");
    block.setAttribute("contentEditable", "false");
    block.setAttribute("data-placeholder", placeholder);
    block.style.cssText = [
      "background:#f3f4f3",
      "border:1.5px dashed rgba(174,179,178,0.4)",
      "border-radius:0.75rem",
      "height:120px",
      "display:flex",
      "align-items:center",
      "justify-content:center",
      "font-family:var(--font-body),sans-serif",
      "font-size:0.85rem",
      "color:#645e57",
      "user-select:none",
      "cursor:default",
      "margin:8px 0",
      "pointer-events:none",
    ].join(";");
    block.textContent = labelText;
    editor.appendChild(block);
    lastIndex = match.index + placeholder.length;
  }

  if (lastIndex < text.length) {
    editor.appendChild(document.createTextNode(text.slice(lastIndex)));
  }
}

/** Extracts raw post text from the editor, converting placeholder blocks back to their original text. */
export function extractTextFromEditor(el: HTMLElement): string {
  // Fast path: no placeholders in the DOM
  if (!el.querySelector("[data-placeholder]")) {
    return el.innerText.replace(/\u00a0/g, " ");
  }

  const parts: string[] = [];

  function traverse(node: Node) {
    if (node.nodeType === Node.TEXT_NODE) {
      parts.push(node.textContent ?? "");
    } else if (node instanceof HTMLElement) {
      const placeholder = node.getAttribute("data-placeholder");
      if (placeholder !== null) {
        parts.push(placeholder);
        return;
      }
      if (node.tagName === "BR") {
        parts.push("\n");
        return;
      }
      // Handle block-level containers inserted by browser (Enter key in contenteditable)
      const isBlock = node.tagName === "DIV" || node.tagName === "P";
      if (isBlock && parts.length > 0 && parts[parts.length - 1] !== "\n") {
        parts.push("\n");
      }
      node.childNodes.forEach(traverse);
      if (isBlock && parts.length > 0 && parts[parts.length - 1] !== "\n") {
        parts.push("\n");
      }
    }
  }

  el.childNodes.forEach(traverse);
  return parts.join("").replace(/\u00a0/g, " ");
}
