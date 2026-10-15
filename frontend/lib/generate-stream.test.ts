import { describe, expect, it } from "vitest";

import { parseEvents, readGenerateStream, STREAM_CUT_MESSAGE } from "./generate-stream";

function body(chunks: string[]): ReadableStream<Uint8Array> {
  const encoder = new TextEncoder();
  return new ReadableStream({
    start(controller) {
      for (const chunk of chunks) controller.enqueue(encoder.encode(chunk));
      controller.close();
    },
  });
}

const sse = (event: string, data: unknown) => `event: ${event}\ndata: ${JSON.stringify(data)}\n\n`;

describe("parseEvents", () => {
  it("keeps an unfinished event for the next read", () => {
    const { events, rest } = parseEvents(`${sse("delta", { text: "a" })}event: delta\ndata: {"te`);
    expect(events).toEqual([{ event: "delta", data: '{"text":"a"}' }]);
    expect(rest).toBe('event: delta\ndata: {"te');
  });

  it("reads CRLF line endings", () => {
    const { events } = parseEvents('event: final\r\ndata: {"post":"x"}\r\n\r\n');
    expect(events).toEqual([{ event: "final", data: '{"post":"x"}' }]);
  });
});

describe("readGenerateStream", () => {
  it("passes deltas on and returns the final result, however the bytes are split", async () => {
    const text = sse("delta", { text: "Hello" }) + sse("delta", { text: " world." }) + sse("final", { status: "ok", post: "Hello world." });
    for (const size of [1, 3, 7, text.length]) {
      const chunks = Array.from({ length: Math.ceil(text.length / size) }, (_, i) => text.slice(i * size, (i + 1) * size));
      const seen: string[] = [];
      const end = await readGenerateStream(body(chunks), (t) => seen.push(t));
      expect(seen.join("")).toBe("Hello world.");
      expect(end).toEqual({ kind: "final", data: { status: "ok", post: "Hello world." } });
    }
  });

  it("returns an error event as an error", async () => {
    const end = await readGenerateStream(body([sse("error", { status_code: 503, detail: "Overloaded." })]), () => {});
    expect(end).toEqual({ kind: "error", status: 503, detail: "Overloaded." });
  });

  it("treats a stream that ends early as an error, never a post", async () => {
    const seen: string[] = [];
    const end = await readGenerateStream(body([sse("delta", { text: "Half" })]), (t) => seen.push(t));
    expect(seen).toEqual(["Half"]);
    expect(end).toEqual({ kind: "error", status: 0, detail: STREAM_CUT_MESSAGE });
  });

  it("reads a final event that arrives without its blank line", async () => {
    const end = await readGenerateStream(body([`event: final\ndata: {"status":"draft_empty","post":""}`]), () => {});
    expect(end).toEqual({ kind: "final", data: { status: "draft_empty", post: "" } });
  });
});
