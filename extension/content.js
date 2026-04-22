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

function extractMainContent() {
  // Step 1: Remove noise elements from a clone
  const clone = document.body.cloneNode(true);
  const noise = clone.querySelectorAll(
    'nav, header, footer, aside, script, style, noscript, ' +
    '[role="navigation"], [role="banner"], [role="complementary"], ' +
    '.nav, .navigation, .sidebar, .menu, .header, .footer, ' +
    '.cookie, .popup, .modal, .ad, .advertisement'
  );
  noise.forEach(el => el.remove());

  // Step 2: Score all block elements by text density
  const candidates = clone.querySelectorAll(
    'div, article, section, main, p'
  );

  let bestEl = null;
  let bestScore = 0;

  candidates.forEach(el => {
    const text = el.innerText || el.textContent || '';
    const textLength = text.trim().length;
    const linkText = Array.from(el.querySelectorAll('a'))
      .reduce((sum, a) => sum + (a.textContent || '').length, 0);
    const pCount = el.querySelectorAll('p').length;

    // Score = text length, penalise link-heavy elements (nav), reward paragraphs
    const score = textLength - (linkText * 2) + (pCount * 50);

    if (score > bestScore && textLength > 200) {
      bestScore = score;
      bestEl = el;
    }
  });

  const raw = bestEl
    ? (bestEl.innerText || bestEl.textContent || '')
    : clone.innerText || clone.textContent || '';

  return raw.trim().slice(0, 8000);
}

function extractTitle() {
  // Try og:title first (most reliable)
  const og = document.querySelector('meta[property="og:title"]');
  if (og && og.content) return og.content.trim();

  // Try h1
  const h1 = document.querySelector('h1');
  if (h1 && h1.textContent.trim().length > 5) return h1.textContent.trim();

  // Fall back to document.title, strip site name
  return document.title.split(/\s[\|\-–]\s/)[0].trim();
}

if (!window.__contendo_injected) {
  window.__contendo_injected = true;

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {

    if (message.action === "getPageContent") {
      const title = extractTitle();
      const text = extractMainContent();
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
