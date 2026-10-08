/**
 * Helpers for model-generated SVG. The markup is untrusted (it can carry
 * <script>, event handlers, external references), so it is never inserted into
 * the page's DOM. It is shown as an image instead: see components/DiagramView.
 */

export interface ParsedSvg {
  /** Well-formed, namespaced XML for the <svg> element. */
  xml: string;
  /** Pixel size used when rasterising. */
  width: number;
  height: number;
  /** CSS max-width for display: the SVG's own width, or "100%" if it has none. */
  maxWidth: string;
}

const FALLBACK_WIDTH = 680;
const FALLBACK_HEIGHT = 400;

function pixels(value: string | null): number | null {
  const match = /^\s*(\d+(?:\.\d+)?)(?:px)?\s*$/.exec(value ?? "");
  const n = match ? parseFloat(match[1]) : NaN;
  return n > 0 ? n : null;
}

/**
 * Parse SVG markup into well-formed XML plus its size. Returns null if there
 * is no <svg> element. Browser only.
 *
 * The HTML parser is used because it is what inline rendering used, so markup
 * that displayed before (an unescaped "&", a missing xmlns) still parses. The
 * parsed document is inert: scripts don't run and nothing is fetched.
 */
export function parseSvg(svgCode: string): ParsedSvg | null {
  const doc = new DOMParser().parseFromString(svgCode, "text/html");
  const svg = doc.querySelector("svg");
  if (!svg) return null;

  const viewBox = (svg.getAttribute("viewBox") ?? "").trim().split(/[\s,]+/).map(Number);
  const [vbWidth, vbHeight] = viewBox.length === 4 ? [viewBox[2], viewBox[3]] : [NaN, NaN];
  const ownWidth = pixels(svg.getAttribute("width"));
  const ownHeight = pixels(svg.getAttribute("height"));

  return {
    xml: new XMLSerializer().serializeToString(svg),
    width: ownWidth ?? (vbWidth > 0 ? vbWidth : FALLBACK_WIDTH),
    height: ownHeight ?? (vbHeight > 0 ? vbHeight : FALLBACK_HEIGHT),
    maxWidth: ownWidth ? `${ownWidth}px` : "100%",
  };
}

/** A data: URI for use as an <img> src. In an image, SVG cannot run scripts or load anything. */
export function svgDataUri(xml: string): string {
  return `data:image/svg+xml;charset=utf-8,${encodeURIComponent(xml)}`;
}

/** Rasterise SVG markup to a PNG data URL at 2x. */
export function svgToPngDataURL(svgCode: string): Promise<string> {
  return new Promise((resolve, reject) => {
    const parsed = parseSvg(svgCode);
    if (!parsed) {
      reject(new Error("No <svg> element"));
      return;
    }

    const canvas = document.createElement("canvas");
    canvas.width = parsed.width * 2;
    canvas.height = parsed.height * 2;
    const ctx = canvas.getContext("2d");
    if (!ctx) {
      reject(new Error("No canvas context"));
      return;
    }

    const img = new Image();
    img.onload = () => {
      ctx.drawImage(img, 0, 0, canvas.width, canvas.height);
      resolve(canvas.toDataURL("image/png"));
    };
    img.onerror = () => reject(new Error("Image load failed"));
    img.src = svgDataUri(parsed.xml);
  });
}
