import { serializeJsonLd } from "@/lib/json-ld";

/**
 * A structured-data block. The data is our own (built in lib/json-ld.ts from
 * the page's content and the backend's plans), never user or model output,
 * and serializeJsonLd escapes "<" so it cannot close the script element.
 */
export default function JsonLd({ data }: { data: unknown }) {
  return <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: serializeJsonLd(data) }} />;
}
