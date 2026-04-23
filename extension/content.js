// content.js — Content script for contendo-six.vercel.app.
//
// Sole responsibility: respond to { action: "getSupabaseToken" } by reading
// the Supabase session from localStorage. Article content extraction is handled
// server-side by POST /scrape-and-ingest — not by this script.
//
// Injection guard: prevents duplicate listener registration if the declarative
// content_scripts load races with a programmatic executeScript call.

if (!window.__contendo_injected) {
  window.__contendo_injected = true;

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.action === "getSupabaseToken") {
      // Supabase stores the session under a key matching sb-*-auth-token.
      // This is the same token the frontend attaches as Authorization: Bearer
      // via useApi() → supabase.auth.getSession() → session.access_token.
      const key = Object.keys(localStorage).find(
        (k) => k.startsWith("sb-") && k.endsWith("-auth-token")
      );
      const raw = key ? localStorage.getItem(key) : null;
      let token = null;
      try {
        token = raw ? JSON.parse(raw)?.access_token : null;
      } catch (_) {
        token = null;
      }
      sendResponse({ token });
    }

    // Return true to keep the message channel open for sendResponse calls
    // (required by Chrome even when the response is synchronous).
    return true;
  });
}
