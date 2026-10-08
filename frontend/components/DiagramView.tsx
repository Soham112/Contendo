"use client";

import { useEffect, useState } from "react";
import { parseSvg, svgDataUri, type ParsedSvg } from "@/lib/svg";

/**
 * The one place model-generated SVG is put on screen.
 *
 * It is rendered as an <img>, never as markup: inside an image the browser runs
 * no scripts or event handlers and loads no external resources, so a malicious
 * or malformed diagram can't touch the page. Do not replace this with
 * dangerouslySetInnerHTML.
 */
export default function DiagramView({
  svg,
  description,
  className,
}: {
  svg: string;
  description: string;
  className?: string;
}) {
  // undefined: not parsed yet (parsing needs the browser). null: no <svg> found.
  const [parsed, setParsed] = useState<ParsedSvg | null | undefined>(undefined);

  useEffect(() => {
    setParsed(parseSvg(svg));
  }, [svg]);

  return (
    <div className={className}>
      {parsed === null && (
        <p className="text-xs text-secondary">This diagram could not be displayed.</p>
      )}
      {parsed && (
        // eslint-disable-next-line @next/next/no-img-element
        <img
          src={svgDataUri(parsed.xml)}
          alt={description}
          style={{ display: "block", width: "100%", maxWidth: parsed.maxWidth, height: "auto" }}
        />
      )}
    </div>
  );
}
