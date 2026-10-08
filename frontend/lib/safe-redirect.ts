/**
 * Post-sign-in redirect targets come from the URL (`redirect_url`, `next`), so
 * they are attacker-controlled. Only a path on this site is ever followed.
 */

export const DEFAULT_REDIRECT = "/create";

// Placeholder origin used only to resolve the input the way a browser would.
const BASE_ORIGIN = "https://same-site.invalid";

/**
 * Returns `input` as a normalised same-site path (path + query + hash), or
 * `fallback` if it is anything else: an absolute or protocol-relative URL,
 * a backslash variant browsers treat as "//", or a path with control characters.
 */
export function safeRedirectPath(
  input: string | null | undefined,
  fallback: string = DEFAULT_REDIRECT
): string {
  if (!input || input[0] !== "/") return fallback;
  // Browsers read "\" as "/" and silently drop tabs and newlines, so
  // "/\evil.com" and "/\t/evil.com" would both leave the site.
  if (/[\\\u0000-\u001f\u007f]/.test(input)) return fallback;
  if (input[1] === "/") return fallback;

  let url: URL;
  try {
    url = new URL(input, BASE_ORIGIN);
  } catch {
    return fallback;
  }
  if (url.origin !== BASE_ORIGIN) return fallback;
  return url.pathname + url.search + url.hash;
}
