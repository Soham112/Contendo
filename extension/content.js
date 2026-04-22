// content.js — Content script with two responsibilities:
//
// 1. On any webpage (injected on demand via chrome.scripting.executeScript):
//    Responds to { action: "getPageContent" } with the page title, body text,
//    and URL so the popup can send them to POST /ingest.
//
// 2. On contendo-six.vercel.app (declaratively loaded via manifest content_scripts):
//    Responds to { action: "getSupabaseToken" } by reading the Supabase session
//    from localStorage — the same token the frontend already has post-login.
//    No user action required.
//
// Injection guard: chrome.scripting.executeScript is called every time the popup
// opens on an article page, which would register duplicate listeners without this
// flag. The declarative load on Contendo pages also only fires once per page, but
// the guard is harmless there too.

if (!window.__contendo_injected) {
  window.__contendo_injected = true;

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {

    if (message.action === "getPageContent") {
      const title = document.title || "";
      // Limit body text to 8000 chars — keeps the request payload reasonable
      // and stays well within the ingestion agent's chunking capacity.
      const text = (document.body?.innerText || "").trim().slice(0, 8000);
      const url = window.location.href;
      sendResponse({ title, text, url });

    } else if (message.action === "getSupabaseToken") {
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
