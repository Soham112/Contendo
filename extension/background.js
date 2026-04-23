// background.js — MV3 service worker.
// Owns all backend fetch calls so they run in the extension's privileged
// context (no CORS issues) and the popup stays lightweight.
//
// Article saving → POST /scrape-and-ingest with { url }.
//   The backend handles scraping, title extraction, chunking, and embedding.
// YouTube saving → POST /ingest with { content: transcript, source_type }.
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
  if (message.action === "scrapeAndIngest") {
    handleScrapeAndIngest(message).then(sendResponse);
    return true;
  }
  if (message.action === "ingest") {
    // Used by the YouTube flow — transcript content posted directly.
    handleIngest(message).then(sendResponse);
    return true;
  }
  if (message.action === "fetchYouTubeTranscript") {
    handleFetchYouTubeTranscript(message).then(sendResponse);
    return true;
  }
});

// ── Scrape-and-ingest handler (articles) ──────────────────────────────────

async function handleScrapeAndIngest({ token, tabId, url }) {
  try {
    const response = await fetch(`${API_BASE}/scrape-and-ingest`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      let detail = `Server error ${response.status}`;
      try {
        const err = await response.json();
        if (err.detail) detail = err.detail;
      } catch (_) {}
      return { success: false, error: detail, status: response.status };
    }

    const data = await response.json();

    if (tabId !== undefined) {
      try {
        chrome.action.setBadgeText({ text: "✓", tabId });
        chrome.action.setBadgeBackgroundColor({ color: "#58614f", tabId });
        setTimeout(() => { chrome.action.setBadgeText({ text: "", tabId }); }, 3000);
      } catch (_) {}
    }

    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || "Network error — check your connection." };
  }
}

// ── Fetch-YouTube-transcript handler ──────────────────────────────────────

async function handleFetchYouTubeTranscript({ token, url }) {
  try {
    const response = await fetch(`${API_BASE}/fetch-youtube-transcript`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json",
        "Authorization": `Bearer ${token}`,
      },
      body: JSON.stringify({ url }),
    });

    if (!response.ok) {
      let detail = `Server error ${response.status}`;
      try {
        const err = await response.json();
        if (err.detail) detail = err.detail;
      } catch (_) {}
      return { success: false, error: detail, status: response.status };
    }

    const data = await response.json();
    return { success: true, data };
  } catch (err) {
    return { success: false, error: err.message || "Network error — check your connection." };
  }
}

// ── Ingest handler (YouTube transcripts) ──────────────────────────────────

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
