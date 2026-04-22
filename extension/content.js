// content.js — Content script injected into the active tab on demand.
// Extracts page title and body text, responds to popup requests.
//
// Injection guard: chrome.scripting.executeScript is called every time the
// popup opens, which would register duplicate listeners without this flag.

if (!window.__contendo_injected) {
  window.__contendo_injected = true;

  chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
    if (message.action !== "getPageContent") return;

    const title = document.title || "";

    // Limit body text to 8000 chars — keeps the request payload reasonable
    // and stays well within the ingestion agent's chunking capacity.
    const text = (document.body?.innerText || "").trim().slice(0, 8000);

    const url = window.location.href;

    sendResponse({ title, text, url });
  });
}
