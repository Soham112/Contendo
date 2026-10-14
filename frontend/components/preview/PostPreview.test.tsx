import { renderToStaticMarkup } from "react-dom/server";
import { describe, expect, it } from "vitest";
import PostPreview from "./PostPreview";
import { PLACEHOLDER_AUTHOR, PLATFORMS, platformById } from "./platforms";

// Rendered on the server, as the public tool page will be: everything must be in the HTML.
const render = (text: string, author = PLACEHOLDER_AUTHOR) => renderToStaticMarkup(<PostPreview text={text} author={author} />);

describe("PostPreview", () => {
  it("renders the post as given, with its line breaks kept for pre-wrap", () => {
    const html = render("Line one\n\nLine two 🎉 𝐁𝐨𝐥𝐝");
    expect(html).toContain("Line one\n\nLine two 🎉 𝐁𝐨𝐥𝐝");
    expect(html).toContain("white-space:pre-wrap");
  });

  it("has accessible platform tabs and labelled toggles", () => {
    const html = render("Hi");
    expect(html).toContain('role="tablist"');
    expect(html).toContain('aria-selected="true"');
    expect(html).toContain('aria-label="Device"');
    expect(html).toContain('aria-label="Theme"');
    expect(html).toContain('aria-label="Preview of your post on LinkedIn"');
  });

  it("shows initials when there is no photo, and never an img without one", () => {
    const html = render("Hi", { name: "Ada Lovelace" });
    expect(html).toContain(">AL<");
    expect(html).not.toContain("<img");
  });

  it("marks the text past the limit and says by how much", () => {
    const html = render("x".repeat(3005));
    expect(html).toContain("<mark");
    expect(html).toContain("3,005 / 3,000 characters");
    expect(html).toContain("5 over LinkedIn");
  });
});

describe("platform config", () => {
  it("gives every platform what the preview needs", () => {
    for (const platform of PLATFORMS) {
      expect(platform.maxCharacters).toBeGreaterThan(0);
      expect(platform.actions.length).toBeGreaterThan(0);
      expect(platform.cardWidth.desktop).toBeGreaterThan(platform.cardWidth.mobile);
      expect(Object.keys(platform.colors).sort()).toEqual(["dark", "light"]);
    }
    expect(new Set(PLATFORMS.map((p) => p.id)).size).toBe(PLATFORMS.length);
    expect(platformById("x").counting).toBe("x-weighted");
  });
});
