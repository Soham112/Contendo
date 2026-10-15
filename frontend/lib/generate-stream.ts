/**
 * Reads POST /generate/stream (backend/routers/generate_stream.py): server-sent
 * events over fetch, since the Supabase token goes in a header.
 *
 *   delta  {text}                 preview text to append (markers already hidden)
 *   final  GenerateResponse       the checked result, any status; replaces the preview
 *   error  {status_code, detail}  the run failed after the stream started
 *
 * Exactly one final or error ends a stream. A stream that ends without one is
 * reported as an error, never as a post.
 */

export interface StreamEvent {
  event: string;
  data: string;
}

export type StreamEnd<T> =
  | { kind: "final"; data: T }
  | { kind: "error"; status: number; detail: string };

export const STREAM_CUT_MESSAGE =
  "The connection closed before your post was finished. Please try again.";

/** Split buffered SSE text into complete events and the unfinished rest. */
export function parseEvents(buffer: string): { events: StreamEvent[]; rest: string } {
  const blocks = buffer.replace(/\r\n/g, "\n").split("\n\n");
  const rest = blocks.pop() ?? "";
  const events = blocks.flatMap((block) => {
    let event = "message";
    const data: string[] = [];
    for (const line of block.split("\n")) {
      if (line.startsWith("event:")) event = line.slice(6).trim();
      else if (line.startsWith("data:")) data.push(line.slice(5).replace(/^ /, ""));
    }
    return data.length ? [{ event, data: data.join("\n") }] : [];
  });
  return { events, rest };
}

/** Read a /generate/stream body to its end, calling onDelta with preview text. */
export async function readGenerateStream<T>(
  body: ReadableStream<Uint8Array>,
  onDelta: (text: string) => void,
): Promise<StreamEnd<T>> {
  const reader = body.getReader();
  const decoder = new TextDecoder();
  let buffer = "";
  try {
    for (;;) {
      const { done, value } = await reader.read();
      buffer += done ? decoder.decode() : decoder.decode(value, { stream: true });
      const parsed = parseEvents(done ? `${buffer}\n\n` : buffer);
      buffer = parsed.rest;
      for (const { event, data } of parsed.events) {
        const payload = JSON.parse(data);
        if (event === "delta") onDelta(payload.text ?? "");
        else if (event === "final") return { kind: "final", data: payload as T };
        else if (event === "error") {
          return { kind: "error", status: Number(payload.status_code) || 500, detail: String(payload.detail ?? "") };
        }
      }
      if (done) return { kind: "error", status: 0, detail: STREAM_CUT_MESSAGE };
    }
  } finally {
    reader.cancel().catch(() => undefined);
  }
}
