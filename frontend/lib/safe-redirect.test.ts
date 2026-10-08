import { describe, expect, it } from "vitest";
import { DEFAULT_REDIRECT, safeRedirectPath } from "./safe-redirect";

describe("safeRedirectPath", () => {
  it.each([
    "/create",
    "/history/123?x=1",
    "/first-post?topic=vector%20search",
    "/history/123#versions",
    "/",
  ])("keeps the same-site path %j", (path) => {
    expect(safeRedirectPath(path)).toBe(path);
  });

  it.each([
    ["protocol-relative", "//evil.com"],
    ["protocol-relative with path", "//evil.com/create"],
    ["backslash after slash", "/\\evil.com"],
    ["double backslash", "\\\\evil.com"],
    ["backslash later in the path", "/create\\..\\evil"],
    ["absolute https", "https://evil.com"],
    ["absolute http", "http://evil.com/create"],
    ["scheme without slashes", "https:evil.com"],
    ["javascript scheme", "javascript:alert(1)"],
    ["data scheme", "data:text/html,<script>alert(1)</script>"],
    ["userinfo, no leading slash", "@evil.com"],
    ["subdomain suffix, no leading slash", ".evil.com"],
    ["bare host", "evil.com"],
    ["relative path", "create"],
    ["leading space", " /create"],
    ["tab that browsers strip", "/\t/evil.com"],
    ["newline that browsers strip", "/\n/evil.com"],
    ["carriage return", "/create\r\nSet-Cookie: x=1"],
    ["null byte", "/create\u0000"],
    ["delete character", "/create\u007f"],
    ["empty", ""],
  ])("rejects %s", (_name, input) => {
    expect(safeRedirectPath(input)).toBe(DEFAULT_REDIRECT);
  });

  it("rejects null and undefined", () => {
    expect(safeRedirectPath(null)).toBe(DEFAULT_REDIRECT);
    expect(safeRedirectPath(undefined)).toBe(DEFAULT_REDIRECT);
  });

  it("returns the caller's fallback when given one", () => {
    expect(safeRedirectPath("//evil.com", "/welcome")).toBe("/welcome");
  });

  it("can never produce something that leaves the origin when appended to it", () => {
    const origin = "https://contendo-six.vercel.app";
    for (const input of ["@evil.com", ".evil.com", "//evil.com", "/\\evil.com", "/ok?next=//evil.com"]) {
      expect(new URL(origin + safeRedirectPath(input)).origin).toBe(origin);
    }
  });
});
