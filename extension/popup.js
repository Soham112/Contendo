// popup.js — Three-state popup controller
// States: auth → page | youtube

// ── Helpers ────────────────────────────────────────────────────────────────

function showOnly(stateId) {
  ["state-auth", "state-page", "state-youtube", "state-loading", "state-success"].forEach((id) => {
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

// ── Content extraction ─────────────────────────────────────────────────────

async function extractPageContent(tabId) {
  try {
    // Inject content.js into the active tab (guard inside prevents duplicate listeners)
    await chrome.scripting.executeScript({
      target: { tabId },
      files: ["content.js"],
    });
    return await chrome.tabs.sendMessage(tabId, { action: "getPageContent" });
  } catch (err) {
    // Scripting can fail on chrome:// or extension pages — return null gracefully
    return null;
  }
}

// ── Auth state ─────────────────────────────────────────────────────────────

function initAuthState() {
  showOnly("state-auth");
  const saveBtn = document.getElementById("save-token-btn");
  const tokenInput = document.getElementById("token-input");

  saveBtn.addEventListener("click", async () => {
    const token = tokenInput.value.trim();
    if (!token) {
      showFeedback("auth-feedback", "Paste a token first.", "error");
      return;
    }
    await chrome.storage.local.set({ token });
    // Re-initialise — will now pick up the stored token
    init();
  });

  tokenInput.addEventListener("keydown", (e) => {
    if (e.key === "Enter") saveBtn.click();
  });
}

// ── Page state ─────────────────────────────────────────────────────────────

async function initPageState(tab, token) {
  showOnly("state-page");

  // Get page content from content script
  const content = await extractPageContent(tab.id);

  const titleEl = document.getElementById("page-title-preview");
  titleEl.textContent = content?.title
    ? truncate(content.title, 90)
    : truncate(tab.title || "Untitled page", 90);

  // Source type pill selection
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

  // Ingest button
  const ingestBtn = document.getElementById("page-ingest-btn");
  ingestBtn.addEventListener("click", async () => {
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

  // Logout / change token
  document.getElementById("page-logout-btn").addEventListener("click", async () => {
    await chrome.storage.local.remove("token");
    initAuthState();
  });
}

// ── YouTube state ──────────────────────────────────────────────────────────

async function initYouTubeState(tab, token) {
  showOnly("state-youtube");

  // Extract title from the YouTube tab
  const content = await extractPageContent(tab.id);
  const titleEl = document.getElementById("yt-title-preview");
  titleEl.textContent = content?.title
    ? truncate(content.title, 90)
    : truncate(tab.title || "YouTube video", 90);

  const videoTitle = content?.title || tab.title || "YouTube video";

  // Ingest button
  const ingestBtn = document.getElementById("yt-ingest-btn");
  ingestBtn.addEventListener("click", async () => {
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

  // Logout / change token
  document.getElementById("yt-logout-btn").addEventListener("click", async () => {
    await chrome.storage.local.remove("token");
    initAuthState();
  });
}

// ── Success / error handling ───────────────────────────────────────────────

function handleIngestResponse(response, sourceTitle) {
  if (!response || !response.success) {
    const errMsg = response?.error || "Unknown error — check your token and try again.";
    // Go back to previous state and show the error
    // We don't know which state we came from, so reinitialise
    init(errMsg);
    return;
  }

  const chunks = response.data?.chunks_stored ?? 0;
  const duplicate = response.data?.duplicate ?? false;

  const msg = duplicate
    ? "Already in your knowledge base — no new chunks added."
    : `Saved. ${chunks} chunk${chunks !== 1 ? "s" : ""} added to your knowledge base.`;

  document.getElementById("success-msg").textContent = msg;
  showOnly("state-success");

  document.getElementById("success-back-btn").addEventListener("click", () => {
    init();
  });
}

// ── Boot ───────────────────────────────────────────────────────────────────

async function init(pendingError) {
  const { token } = await chrome.storage.local.get("token");

  if (!token) {
    initAuthState();
    return;
  }

  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });

  if (!tab) {
    initAuthState();
    return;
  }

  const isYouTube = tab.url && tab.url.includes("youtube.com/watch");

  if (isYouTube) {
    await initYouTubeState(tab, token);
  } else {
    await initPageState(tab, token);
  }

  // Surface a deferred error from a previous ingest attempt
  if (pendingError) {
    const feedbackId = isYouTube ? "yt-feedback" : "page-feedback";
    showFeedback(feedbackId, pendingError, "error");
  }
}

document.addEventListener("DOMContentLoaded", () => init());
