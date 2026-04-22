// popup.js — Popup controller
//
// Auth flow (no manual token input):
//   1. On open: check chrome.storage.local for a cached token.
//   2. If none: query for an open contendo-six.vercel.app tab, send
//      { action: "getSupabaseToken" } to its content script, cache the result.
//   3. If Contendo is not open or user is not signed in: show the connect
//      state with a single "Open Contendo" button.
//   4. On 401 from backend: clear cached token and re-run the flow so a
//      fresh token is read from the Contendo tab automatically.

const CONTENDO_ORIGIN = "https://contendo-six.vercel.app";

// ── Helpers ────────────────────────────────────────────────────────────────

function showOnly(stateId) {
  ["state-connecting", "state-connect", "state-page", "state-youtube",
   "state-loading", "state-success"].forEach((id) => {
    const el = document.getElementById(id);
    if (el) el.hidden = id !== stateId;
  });
}

function showFeedback(containerId, message, type) {
  const el = document.getElementById(containerId);
  if (!el) return;
  el.className = `feedback ${type} mt8`;
  el.textContent = message;
  el.hidden = false;
}

function hideFeedback(containerId) {
  const el = document.getElementById(containerId);
  if (el) el.hidden = true;
}

function truncate(str, maxLen) {
  if (!str) return "";
  return str.length > maxLen ? str.slice(0, maxLen - 1) + "…" : str;
}

// ── Token resolution ───────────────────────────────────────────────────────

// Read the Supabase access_token directly from the Contendo tab's localStorage.
// We inject content.js programmatically before messaging to handle the case
// where the tab was already open when the extension was installed or reloaded
// (declarative content_scripts only inject into tabs opened after the extension
// loads, so existing tabs may not have the listener active).
async function getTokenFromContendo() {
  try {
    const tabs = await chrome.tabs.query({ url: `${CONTENDO_ORIGIN}/*` });
    if (!tabs.length) return null;
    const tab = tabs[0];
    // Inject content.js first — the injection guard (window.__contendo_injected)
    // inside content.js prevents duplicate listener registration if it was
    // already declaratively loaded.
    await chrome.scripting.executeScript({ target: { tabId: tab.id }, files: ["content.js"] });
    const response = await chrome.tabs.sendMessage(tab.id, { action: "getSupabaseToken" });
    return response?.token || null;
  } catch (_) {
    // Tab not yet ready or content script not loaded — return null gracefully.
    return null;
  }
}

// Resolve a valid token: use the cached one if present, otherwise fetch fresh
// from the Contendo tab and cache it.
async function resolveToken() {
  const { token } = await chrome.storage.local.get("token");
  if (token) return token;

  const fresh = await getTokenFromContendo();
  if (fresh) await chrome.storage.local.set({ token: fresh });
  return fresh || null;
}

// ── Content extraction ─────────────────────────────────────────────────────

async function extractPageContent(tabId) {
  try {
    // Inject content.js into the article tab on demand.
    // The injection guard inside content.js prevents duplicate listeners.
    await chrome.scripting.executeScript({ target: { tabId }, files: ["content.js"] });
    return await chrome.tabs.sendMessage(tabId, { action: "getPageContent" });
  } catch (_) {
    return null;
  }
}

// ── Connect state ──────────────────────────────────────────────────────────

function initConnectState(hint) {
  showOnly("state-connect");
  if (hint) showFeedback("connect-feedback", hint, "error");

  document.getElementById("open-contendo-btn").addEventListener("click", () => {
    chrome.tabs.create({ url: CONTENDO_ORIGIN });
    showFeedback(
      "connect-feedback",
      "Sign in to Contendo, then come back and click the extension icon.",
      "info"
    );
  });
}

// ── Page state ─────────────────────────────────────────────────────────────

async function initPageState(tab, token) {
  showOnly("state-page");

  const content = await extractPageContent(tab.id);

  document.getElementById("page-title-preview").textContent = content?.title
    ? truncate(content.title, 90)
    : truncate(tab.title || "Untitled page", 90);

  let selectedSource = "article";
  let selectedOrigin = "saved";

  document.querySelectorAll("#state-page .source-pill").forEach((pill) => {
    pill.addEventListener("click", () => {
      document.querySelectorAll("#state-page .source-pill").forEach((p) => p.classList.remove("active"));
      pill.classList.add("active");
      selectedSource = pill.dataset.source;
      selectedOrigin = pill.dataset.origin;
      document.getElementById("page-badge").textContent =
        selectedSource === "note" ? "Personal" : "Article";
    });
  });

  document.getElementById("page-ingest-btn").addEventListener("click", async () => {
    hideFeedback("page-feedback");

    if (!content?.text) {
      showFeedback("page-feedback", "Could not extract page content. Try on a regular webpage.", "error");
      return;
    }

    showOnly("state-loading");

    const response = await chrome.runtime.sendMessage({
      action: "ingest",
      token,
      tabId: tab.id,
      content: content.text,
      source_type: selectedSource,
      content_origin: selectedOrigin,
      title: content.title || tab.title || "",
      url: tab.url || "",
    });

    handleIngestResponse(response, content.title || tab.title || "page");
  });
}

// ── YouTube state ──────────────────────────────────────────────────────────

async function initYouTubeState(tab, token) {
  showOnly("state-youtube");

  const content = await extractPageContent(tab.id);
  const videoTitle = content?.title || tab.title || "YouTube video";

  document.getElementById("yt-title-preview").textContent = truncate(videoTitle, 90);

  document.getElementById("yt-ingest-btn").addEventListener("click", async () => {
    hideFeedback("yt-feedback");

    const transcript = document.getElementById("yt-transcript").value.trim();
    if (!transcript) {
      showFeedback("yt-feedback", "Paste the video transcript before saving.", "error");
      return;
    }

    showOnly("state-loading");

    const response = await chrome.runtime.sendMessage({
      action: "ingest",
      token,
      tabId: tab.id,
      content: transcript,
      source_type: "youtube",
      content_origin: "saved",
      title: videoTitle,
      url: tab.url || "",
    });

    handleIngestResponse(response, videoTitle);
  });
}

// ── Success / error handling ───────────────────────────────────────────────

function handleIngestResponse(response, sourceTitle) {
  if (!response || !response.success) {
    // 401 means the cached token expired — clear it and re-run so a fresh
    // token is read from the Contendo tab automatically.
    if (response?.status === 401) {
      chrome.storage.local.remove("token");
      init();
      return;
    }

    const errMsg = response?.error || "Something went wrong — try again.";
    init(errMsg);
    return;
  }

  const chunks = response.data?.chunks_stored ?? 0;
  const duplicate = response.data?.duplicate ?? false;

  document.getElementById("success-msg").textContent = duplicate
    ? "Already in your knowledge base — no new chunks added."
    : `Saved. ${chunks} chunk${chunks !== 1 ? "s" : ""} added to your knowledge base.`;

  showOnly("state-success");

  document.getElementById("success-back-btn").addEventListener("click", () => init());
}

// ── Boot ───────────────────────────────────────────────────────────────────

async function init(pendingError) {
  showOnly("state-connecting");

  const token = await resolveToken();

  if (!token) {
    initConnectState(pendingError || null);
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab) {
    initConnectState("No active tab found.");
    return;
  }

  const isYouTube = tab.url && tab.url.includes("youtube.com/watch");

  if (isYouTube) {
    await initYouTubeState(tab, token);
  } else {
    await initPageState(tab, token);
  }

  if (pendingError) {
    showFeedback(isYouTube ? "yt-feedback" : "page-feedback", pendingError, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => init());
