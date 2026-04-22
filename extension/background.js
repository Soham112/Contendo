// background.js — MV3 service worker.
// Owns the POST /ingest call so the popup stays lightweight and the fetch
// runs in the extension's privileged context (no CORS issues).
//
// Also owns token acquisition: polls the Contendo tab for the Supabase
// access_token and caches it in chrome.storage.local under "contendo_token".
// The popup reads from storage only — it never touches the Contendo tab.

const API_BASE = "https://contendo-production.up.railway.app";
const CONTENDO_ORIGIN = "https://contendo-six.vercel.app";

// ── Token polling ──────────────────────────────────────────────────────────

let _pollInterval = null;

// Inject content.js into the Contendo tab (if open) and read the Supabase
// token from localStorage. On success, persist to storage and stop polling.
async function tryReadToken() {
  try {
    const { contendo_token } = await chrome.storage.local.get("contendo_token");
    if (contendo_token) {
      // Already have a token — stop the polling loop.
      _stopPolling();
      return;
    }

    const tabs = await chrome.tabs.query({ url: `${CONTENDO_ORIGIN}/*` });
    if (!tabs.length) return; // Contendo tab not open yet — try again next tick.

    for (const tab of tabs) {
      try {
        // Programmatic injection handles tabs that were open before the
        // extension loaded (declarative content_scripts don't cover those).
        await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
        const response = await chrome.tabs.sendMessage(tab.id, { action: "getSupabaseToken" });
        if (response?.token) {
          await chrome.storage.local.set({ contendo_token: response.token });
          _stopPolling();
          return;
        }
      } catch (_) {
        // This tab wasn't ready — try the next one (or wait for next tick).
      }
    }
  } catch (_) {
    // Swallow unexpected errors so the polling loop stays alive.
  }
}

function _stopPolling() {
  if (_pollInterval !== null) {
    clearInterval(_pollInterval);
    _pollInterval = null;
  }
}

function _startPolling() {
  if (_pollInterval !== null) return; // Already running.
  tryReadToken(); // Immediate first attempt.
  _pollInterval = setInterval(tryReadToken, 3000);
}

// Start polling as soon as the service worker wakes.
_startPolling();

// ── Tab listener ───────────────────────────────────────────────────────────

// When any Contendo tab finishes loading, attempt token read immediately.
// Covers the case where the user navigates to Contendo after the popup opens.
chrome.tabs.onUpdated.addListener((tabId, changeInfo, tab) => {
  if (changeInfo.status === "complete" && tab.url?.startsWith(CONTENDO_ORIGIN)) {
    tryReadToken();
  }
});

// ── Message listener ───────────────────────────────────────────────────────

chrome.runtime.onMessage.addListener((message, _sender, sendResponse) => {
  if (message.action === "ingest") {
    handleIngest(message).then(sendResponse);
    // Return true to keep the message channel open for the async response.
    return true;
  }
  if (message.action === "startTokenPolling") {
    _startPolling();
    sendResponse({ ok: true });
    return false;
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
