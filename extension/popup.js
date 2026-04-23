// popup.js — Popup controller
//
// Auth flow (push model — no polling, no content-script messaging):
//   1. On open: check chrome.storage.local for "contendo_token".
//      The Contendo web app pushes this token via chrome.runtime.sendMessage
//      (externally_connectable) whenever the user loads the app signed in.
//   2. Token present → go straight to the article/YouTube UI.
//   3. Token absent → show two buttons:
//        "Open Contendo" — opens the app so the frontend can push the token.
//        "Already signed in — retry" — re-checks storage (for the case where
//        Contendo is already open in another tab and has already pushed the token).
//   4. On 401 from backend: clear the cached token and re-run init().
//
// Article saving: sends { action: "scrapeAndIngest", url } to background.js,
//   which POSTs to /scrape-and-ingest. The backend handles scraping entirely.
// YouTube saving: sends { action: "ingest", content: transcript } — unchanged.

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

// The background service worker polls the Contendo tab and writes the token
// to chrome.storage.local under "contendo_token". The popup reads from
// storage only — it never touches the Contendo tab directly.
async function resolveToken() {
  const { contendo_token } = await chrome.storage.local.get("contendo_token");
  return contendo_token || null;
}

// ── Connect state ──────────────────────────────────────────────────────────

function initConnectState(hint) {
  showOnly("state-connect");
  if (hint) showFeedback("connect-feedback", hint, "error");

  // "Open Contendo" — opens the app so the frontend can push the token.
  document.getElementById("open-contendo-btn").addEventListener("click", () => {
    chrome.tabs.create({ url: CONTENDO_ORIGIN });
    showFeedback(
      "connect-feedback",
      "Sign in to Contendo — the extension connects automatically when the page loads.",
      "info"
    );
  });

  // "Already signed in — retry" — re-checks storage in case the frontend
  // already pushed the token (e.g. Contendo was open in another tab).
  document.getElementById("retry-connect-btn").addEventListener("click", async () => {
    const { contendo_token } = await chrome.storage.local.get("contendo_token");
    if (contendo_token) {
      init(); // Token is there — go straight to the article UI.
    } else {
      showFeedback(
        "connect-feedback",
        "No token yet — open Contendo and sign in, then click retry again.",
        "info"
      );
    }
  });
}

// ── Page state ─────────────────────────────────────────────────────────────

async function initPageState(tab, token) {
  showOnly("state-page");

  // Title preview comes from the tab — the backend will extract the real title
  // server-side via /scrape-and-ingest, so this is display-only.
  document.getElementById("page-title-preview").textContent =
    truncate(tab.title || "Untitled page", 90);

  document.getElementById("page-ingest-btn").addEventListener("click", async () => {
    hideFeedback("page-feedback");
    showOnly("state-loading");

    // Send the URL only — backend scrapes, titles, chunks, and embeds.
    const response = await chrome.runtime.sendMessage({
      action: "scrapeAndIngest",
      token,
      tabId: tab.id,
      url: tab.url,
    });

    handleIngestResponse(response, tab.title || "page");
  });
}

// ── YouTube state ──────────────────────────────────────────────────────────

async function initYouTubeState(tab, token) {
  showOnly("state-youtube");

  // Strip " - YouTube" suffix that Chrome includes in the tab title.
  const videoTitle = (tab.title || "YouTube video").replace(/\s*-\s*YouTube\s*$/i, "").trim() || "YouTube video";

  document.getElementById("yt-title-preview").textContent = truncate(videoTitle, 90);

  // Auto-fetch the transcript using the tab URL — no manual paste needed.
  const fetchResult = await chrome.runtime.sendMessage({
    action: "fetchYouTubeTranscript",
    token,
    url: tab.url,
  });

  if (!fetchResult || !fetchResult.success) {
    // Expired token — re-auth and retry.
    if (fetchResult?.status === 401) {
      chrome.storage.local.remove("contendo_token");
      init();
      return;
    }
    document.getElementById("yt-fetching-status").hidden = true;
    showFeedback(
      "yt-feedback",
      fetchResult?.error || "Could not fetch transcript. The video may not have captions enabled.",
      "error"
    );
    return;
  }

  // Transcript ready — show preview and enable the ingest button.
  const transcript = fetchResult.data.transcript;

  document.getElementById("yt-fetching-status").hidden = true;
  document.getElementById("yt-transcript-snippet").textContent =
    transcript.slice(0, 200) + (transcript.length > 200 ? "…" : "");
  document.getElementById("yt-transcript-preview").hidden = false;

  const ingestBtn = document.getElementById("yt-ingest-btn");
  ingestBtn.disabled = false;

  ingestBtn.addEventListener("click", async () => {
    hideFeedback("yt-feedback");
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
      chrome.storage.local.remove("contendo_token");
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
