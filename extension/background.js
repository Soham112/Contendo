// background.js — MV3 service worker.
// Owns the POST /ingest call so the popup stays lightweight and the fetch
// runs in the extension's privileged context (no CORS issues).
//
// Token acquisition uses a push model: the Contendo web app calls
// chrome.runtime.sendMessage(EXTENSION_ID, { action: 'setToken', token })
// via externally_connectable, and this worker saves it to storage.
// The popup reads from storage only.

console.log('Contendo background worker started');

const API_BASE = "https://contendo-production.up.railway.app";

// ── External message listener (push from Contendo web app) ────────────────

chrome.runtime.onMessageExternal.addListener((message, _sender, sendResponse) => {
  if (message.action === 'setToken' && message.token) {
    chrome.storage.local.set({ contendo_token: message.token });
    console.log('Token received from Contendo web app');
    sendResponse({ ok: true });
  }
  return false;
});

// ── Internal message listener ──────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "ingest") {
    handleIngest(message).then(sendResponse);
    // Return true to keep the message channel open for the async response.
    return true;
  }
});

// ── Ingest handler ─────────────────────────────────────────────────────────

async function handleIngest({ token, tabId, content, source_type, content_origin, title, url }) {
  try {
    // Mirror the auth pattern from frontend/lib/api.ts: Authorization: Bearer {token}
    const response = await fetch(`${API_BASE}/ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      // IngestRequest fields: content, source_type, content_origin.
      // title and url are not declared on IngestRequest — Pydantic ignores them
      // (extra fields are silently dropped). They are included here so a future
      // backend change can pick them up without touching the extension.
      body: JSON.stringify({ content, source_type, content_origin, title, url }),
    });

    if (!response.ok) {
      let detail = `Server error ${response.status}`;
      try {
        const err = await response.json();
        if (err.detail) detail = err.detail;
      } catch (_) {
        // Non-JSON error body — keep the status string
      }
      return { success: false, error: detail, status: response.status };
    }

    const data = await response.json();

    // Show a ✓ badge on the extension icon for the tab that triggered the save.
    if (tabId !== undefined) {
      try {
        chrome.action.setBadgeText({ text: "✓", tabId });
        chrome.action.setBadgeBackgroundColor({ color: "#58614f", tabId });
        // Clear the badge after 3 seconds.
        setTimeout(() => {
          chrome.action.setBadgeText({ text: "", tabId });
        }, 3000);
      } catch (_) {
        // Badge APIs are non-critical — ignore failures.
      }
    }

    return { success: true, data };
  } catch (err) {
    // Network failure, fetch abort, etc.
    return { success: false, error: err.message || "Network error — check your connection." };
  }
}
