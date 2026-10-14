import { describe, expect, it } from "vitest";
import { initials, pastedText } from "./post-text";

describe("pastedText", () => {
  it("drops Markdown and placeholders but keeps line breaks, emoji and Unicode styling", () => {
    const post = "**Big** news 🎉\n\n[DIAGRAM: flow]\n\n\n\n𝐁𝐨𝐥𝐝 stays.\n  Indented line";
    expect(pastedText(post)).toBe("Big news 🎉\n\n𝐁𝐨𝐥𝐝 stays.\n  Indented line");
  });
});

describe("initials", () => {
  it("takes the first letter of up to two words", () => {
    expect(initials("ada lovelace byron")).toBe("AL");
    expect(initials("  Plato ")).toBe("P");
    expect(initials("Émile Zola")).toBe("ÉZ");
    expect(initials("")).toBe("?");
  });
});
