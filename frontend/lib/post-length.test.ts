import { describe, expect, it } from "vitest";
import { measure } from "./post-length";

const x = (text: string, limit = 280) => measure(text, "x-weighted", limit);

describe("X counting", () => {
  it("counts plain Latin text one per character", () => {
    expect(x("Hello, world").count).toBe(12);
  });

  it("counts an emoji as 2, however many code points it has", () => {
    expect(x("😀").count).toBe(2);
    expect(x("👩‍💻").count).toBe(2); // ZWJ sequence
    expect(x("🇺🇸").count).toBe(2); // flag
    expect(x("1️⃣").count).toBe(2); // keycap
    expect(x("©").count).toBe(1); // a bare symbol in the light range
  });

  it("counts Unicode bold and CJK characters as 2", () => {
    expect(x("𝐁𝐨𝐥𝐝").count).toBe(8);
    expect(x("日本").count).toBe(4);
  });

  it("counts a link as 23 whatever its length, leaving trailing punctuation out", () => {
    expect(x("https://example.com/a/very/long/path?with=query").count).toBe(23);
    expect(x("See www.example.com.").count).toBe(4 + 23 + 1);
  });

  it("counts a decomposed accent as one character", () => {
    expect(x("é").count).toBe(1);
  });

  it("marks where the limit is first exceeded, in UTF-16 indices", () => {
    expect(x("abc", 3).overflowAt).toBeNull();
    expect(x("abcd", 3).overflowAt).toBe(3);
    const text = "ab😀c";
    expect(x(text, 3).overflowAt).toBe(2); // the emoji takes the count from 2 to 4
    expect(text.slice(x(text, 3).overflowAt!)).toBe("😀c");
  });
});

describe("code point counting", () => {
  it("counts each code point once, so an emoji is 1 and a ZWJ sequence is its parts", () => {
    expect(measure("😀", "codepoints", 10).count).toBe(1);
    expect(measure("👩‍💻", "codepoints", 10).count).toBe(3);
    expect(measure("abcdef", "codepoints", 4).overflowAt).toBe(4);
  });
});
