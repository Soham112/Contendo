"use client";

import { useEffect, useLayoutEffect, useMemo, useRef, useState } from "react";
import { useToast } from "@/components/ui/ToastProvider";
import { useApi } from "@/lib/api";
import type { ClosestSource, ScoreResponse } from "@/lib/api";
import { generateOutcome } from "@/lib/generate-outcome";
import { useTracking } from "@/lib/useTracking";
import { useBusinessPost } from "@/components/create/BusinessPostFields";
import { getPostStats, pastedText, stripPlaceholders } from "@/lib/post-text";
import UpgradeScreen from "@/components/billing/UpgradeScreen";
import { useEntitlements } from "@/hooks/useEntitlements";
import { readPaywall, type Paywall } from "@/lib/billing";
import { type Format, type GenerateResult, SS_CURRENT_POST_ID, SS_FEEDBACK, SS_POST, SS_SCORE, SS_SCORED, SS_SHOW_ANALYSIS, SS_TOPIC, type Tone } from "@/components/create/config";
import { extractTextFromEditor, getSelectionOffsetsWithin, setEditorContent } from "@/components/create/editor-dom";
import { VisualsPanel } from "@/components/create/VisualCards";
import SettingsDrawer from "@/components/create/SettingsDrawer";
import AnalysisPanel from "@/components/create/AnalysisPanel";
import ConfigureForm from "@/components/create/ConfigureForm";
import IdeasPanel from "@/components/create/IdeasPanel";
import InlineRefineToolbar from "@/components/create/InlineRefineToolbar";
import PostActionButtons from "@/components/create/PostActionButtons";
import { WorkspaceBar } from "@/components/create/PostChrome";
import ResumeDraftPrompt from "@/components/create/ResumeDraftPrompt";
import PostWorkspace from "@/components/create/PostWorkspace";
import { ProgressSteps } from "@/components/ui/states";

// What happens while a post is written, in the order the pipeline does it.
const GENERATION_STEPS = [
  "Finding what you know about this",
  "Drafting it in your voice",
  "Checking facts against your sources",
  "Polishing the wording",
];
import {
  GENERATION_KEYS, readDraft, readSavedIdeas, readShowAnalysis, removeKeys, saveDraft, START_FRESH_KEYS, storedPostId,
} from "@/components/create/draft-storage";
import { useSaveStatus, useSplitLayout } from "@/components/create/layout-hooks";
import { useIdeas } from "@/components/create/useIdeas";
import { useVisuals } from "@/components/create/useVisuals";
import { errorDetail } from "@/lib/request-errors";

// ─── Main Component ───────────────────────────────────────────────────────────

export default function CreatePost() {
  const api = useApi();
  const businessPost = useBusinessPost();
  const { entitlements, refresh: refreshEntitlements } = useEntitlements();
  const [paywall, setPaywall] = useState<Paywall | null>(null);
  const { logEvent } = useTracking();
  const [topic, setTopic] = useState("");
  // Every post is a LinkedIn post.
  const format: Format = "linkedin post";
  const [tone, setTone] = useState<Tone>("casual");
  const [context, setContext] = useState("");
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<GenerateResult | null>(null);
  const [editedPost, setEditedPost] = useState("");
  const [error, setError] = useState("");
  // Set when /generate returns low_coverage: the closest sources it found.
  const [lowCoverage, setLowCoverage] = useState<ClosestSource[] | null>(null);
  const [noSpecificsEnabled, setNoSpecificsEnabled] = useState(false);
  // True when the current post was generated in no-specifics mode.
  const [opinionMode, setOpinionMode] = useState(false);
  const [copiedLinkedIn, setCopiedLinkedIn] = useState(false);


  const { showToast } = useToast();
  const [lastSaved, setLastSaved] = useState<number | null>(null);

  const [scoreLoading, setScoreLoading] = useState(false);
  const [toneDescOpacity, setToneDescOpacity] = useState(0);

  const [analysisOpen, setAnalysisOpen] = useState(false);
  const [currentPostId, setCurrentPostId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(false);
  const [showInterstitial, setShowInterstitial] = useState(false);
  const [interstitialTopic, setInterstitialTopic] = useState("");
  const [interstitialScore, setInterstitialScore] = useState(0);

  const [inlineSelection, setInlineSelection] = useState<{
    start: number;
    end: number;
    text: string;
    rect: DOMRect | null;
  } | null>(null);
  const [inlineInstruction, setInlineInstruction] = useState("");
  const [inlineLoading, setInlineLoading] = useState(false);
  const [editorHinted, setEditorHinted] = useState(false);

  const topicRef = useRef<HTMLTextAreaElement>(null);
  const analysisRef = useRef<HTMLDivElement>(null);
  const inlineInputRef = useRef<HTMLInputElement>(null);
  const postEditorRef = useRef<HTMLDivElement>(null);

  // Tracks whether the last editedPost change came from user typing (to skip DOM re-sync)
  const isUserInput = useRef(false);
  // Tracks what was last programmatically rendered so we don't re-render on unrelated deps changes
  const lastRenderedPost = useRef<string>("");
  // Stores the original generated post text with [DIAGRAM:/IMAGE:] placeholders intact
  // (editedPost stores the clean version; rawPostRef is used for /generate-visuals)
  const rawPostRef = useRef<string>("");
  // trace_id from the latest /generate, sent with the first successful /log-post
  // for that generation, then cleared so a later save never re-links it.
  const pendingTraceIdRef = useRef<string | null>(null);
  // trace_id of the post generated in this session, kept so selection refines
  // can be checked against its sources. In memory only: a stored copy could
  // outlive the post and point a different post at the wrong sources.
  const currentTraceIdRef = useRef<string | null>(null);


  const { splitRatio, setSplitRatio, isWide, splitContainerRef, handleDragStart } = useSplitLayout();
  const saveStatusText = useSaveStatus(lastSaved);
  const ideas = useIdeas((s) => {
    setTopic(s.title);
    topicRef.current?.scrollIntoView({ behavior: "smooth", block: "center" });
    topicRef.current?.focus();
  });
  const {
    suggestions, visible: suggestionsVisible, loading: suggestionsLoading, selectedIndex: selectedIdeaIndex,
    focus: ideaTopic, refresh: handleGetIdeas, use: handleUseSuggestion, dismiss: handleDismissIdeas,
  } = ideas;
  const visualsState = useVisuals({
    logEvent,
    beforeGenerate: async () => {
      setAnalysisOpen(false);
      // Ensure a history entry exists before generating visuals
      if (!storedPostId(currentPostId) && result) {
        await autoSavePost(result, editedPost);
      }
    },
    sourceText: () => rawPostRef.current || editedPost,
    saveDiagrams: (diagrams) => patchHistory({ svg_diagrams: diagrams }),
  });
  const {
    visuals, loading: visualsLoading, visible: visualsVisible, setVisible: setVisualsVisible, entered: visualsPanelEntered,
    generate: handleGenerateVisuals, changeVersion: handleDiagramVersionChange,
  } = visualsState;

  // On mount: show interstitial if a saved post exists, else go to idle with prefill
  useEffect(() => {
    try {
      // Non-post preferences come back either way (ideas panel, analysis open state)
      ideas.restore(readSavedIdeas());
      const showAnalysis = readShowAnalysis();
      if (showAnalysis !== null) setAnalysisOpen(showAnalysis);

      if (sessionStorage.getItem(SS_POST)) {
        // A saved post exists: show the interstitial and defer all restoration
        setInterstitialTopic(sessionStorage.getItem(SS_TOPIC) || "");
        setInterstitialScore(Number(sessionStorage.getItem(SS_SCORE)) || 0);
        setShowInterstitial(true);
      } else {
        // No saved post: idle state; apply any prefill from Ideas screen
        const prefillTopic = sessionStorage.getItem("contentOS_last_topic");
        if (prefillTopic) setTopic(prefillTopic);
        sessionStorage.removeItem("contentOS_last_topic");
        sessionStorage.removeItem("contentOS_prefill_format");
      }
    } catch {
      // corrupt sessionStorage — ignore
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  // Persist session whenever result or visuals change
  useEffect(() => {
    if (!result) return;
    saveDraft({ result, traceId: currentTraceIdRef.current, post: editedPost, rawPost: rawPostRef.current, visuals, topic, format, tone });
  }, [result, editedPost, visuals, topic, format, tone]);

  // Persist analysisOpen preference
  useEffect(() => {
    try {
      sessionStorage.setItem(SS_SHOW_ANALYSIS, String(analysisOpen));
    } catch {
      // ignore
    }
  }, [analysisOpen]);

  // Fade tone description in when tone changes
  useEffect(() => {
    setToneDescOpacity(0);
    const t = setTimeout(() => setToneDescOpacity(1), 50);
    return () => clearTimeout(t);
  }, [tone]);

  // useLayoutEffect (not useEffect) so the editor is populated synchronously
  // after every DOM commit — before the browser paints. This eliminates the
  // blank-canvas flash that occurred when analysisOpen or other deps caused a
  // branch switch (split ↔ single-column), because the new editor div is always
  // empty on mount and a deferred requestAnimationFrame could fire too late or
  // be cancelled by the effect cleanup when the layout changed quickly.
  useLayoutEffect(() => {
    if (!editedPost) return;
    const editor = postEditorRef.current;
    if (!editor) return;
    // Skip DOM re-sync when the change came from user typing in the editor.
    // The browser already updated the DOM; overwriting it would disrupt the cursor.
    // EXCEPTION: if the editor is empty (just remounted after a layout branch switch),
    // always repopulate regardless — otherwise the canvas stays blank.
    if (isUserInput.current && editor.innerHTML !== "") {
      isUserInput.current = false;
      return;
    }
    isUserInput.current = false;
    // Re-render when content changed OR when editor was remounted (empty after branch switch).
    if (editedPost !== lastRenderedPost.current || editor.innerHTML === "") {
      setEditorContent(editor, editedPost);
      lastRenderedPost.current = editedPost;
    }
  // analysisOpen + isWide + visualsVisible determine which branch (split vs single-column)
  // is rendered. loading gates post-gen mount after generate.
  }, [editedPost, analysisOpen, isWide, visualsVisible, loading]);

  const clearSession = () => {
    removeKeys(GENERATION_KEYS);
    setCurrentPostId(null);
    ideas.reset();
  };
  // Restore full session from storage — called when user clicks "Continue editing"
  const handleContinueEditing = () => {
    try {
      const draft = readDraft();
      if (draft) {
        currentTraceIdRef.current = draft.traceId;
        setResult(draft.result);
        setEditedPost(draft.post);
        // Restore raw post (with placeholders) for /generate-visuals calls
        rawPostRef.current = draft.rawPost;
        if (draft.visuals) visualsState.restore(draft.visuals);
        if (draft.topic) setTopic(draft.topic);
        if (draft.tone) setTone(draft.tone);
        if (draft.postId !== null) setCurrentPostId(draft.postId);
      }
    } catch {
      // corrupt storage — fall through to idle
    }
    setShowInterstitial(false);
  };

  // Discard saved session and start blank — called when user clicks "Start fresh"
  const handleStartFresh = () => {
    removeKeys(START_FRESH_KEYS);
    rawPostRef.current = "";
    currentTraceIdRef.current = null;
    sessionStorage.removeItem("contentOS_last_topic");
    sessionStorage.removeItem("contentOS_prefill_format");

    setResult(null);
    setEditedPost("");
    visualsState.reset();
    setAnalysisOpen(false);
    setCurrentPostId(null);
    ideas.reset();
    setShowInterstitial(false);
  };

  const autoSavePost = async (data: GenerateResult, postContent: string) => {
    try {
      const res = await api.logPost({
        topic,
        format,
        tone,
        content: postContent,
        authenticity_score: data.score,
        svg_diagrams: null,
        trace_id: pendingTraceIdRef.current,
      });
      if (!res.ok) return;
      pendingTraceIdRef.current = null;
      const saved = await res.json();
      const postId: number = saved.post_id;
      setCurrentPostId(postId);
      setLastSaved(Date.now());
      try {
        sessionStorage.setItem(SS_CURRENT_POST_ID, String(postId));
      } catch {
        // ignore
      }
    } catch {
      // auto-save failure is non-critical
    }
  };

  const patchHistory = async (fields: {
    content?: string;
    authenticity_score?: number;
    svg_diagrams?: object[] | null;
  }) => {
    const postId = storedPostId(currentPostId);
    if (!postId) return;
    try {
      await api.patchPost(postId, fields);
      setLastSaved(Date.now());
    } catch {
      // patch failure is non-critical
    }
  };

  const handleScore = async () => {
    if (!result || scoreLoading) return;
    setScoreLoading(true);
    try {
      const res = await api.scorePost(editedPost);
      if (!res.ok) throw new Error("Scoring failed");
      const data: ScoreResponse = await res.json();
      if (data.score === null) {
        // No score came back: leave the post unscored so the user can try again.
        showToast(data.message || "Couldn't score this post. Try again.", "error");
        return;
      }
      const score = data.score;
      setResult((prev) =>
        prev ? { ...prev, score, score_feedback: data.score_feedback, scored: true } : prev
      );
      try {
        sessionStorage.setItem(SS_SCORE, String(score));
        sessionStorage.setItem(SS_FEEDBACK, JSON.stringify(data.score_feedback));
        sessionStorage.setItem(SS_SCORED, "true");
      } catch {
        // ignore
      }
      await patchHistory({ authenticity_score: score });
    } catch {
      showToast("Couldn't score this post. Try again.", "error");
    } finally {
      setScoreLoading(false);
    }
  };

  const generate = async (overrides?: {
    topic?: string;
    tone?: Tone;
    context?: string;
  }, opts?: { noSpecifics?: boolean }) => {
    const t = overrides?.topic ?? topic;
    const f = format;
    const tn = overrides?.tone ?? tone;
    const ctx = overrides?.context ?? context;

    if (!t.trim()) {
      setError("Topic is required.");
      return;
    }
    logEvent({ event_type: "button_click", page_url: "/create", button_name: "generate_btn", metadata: { format: f, tone: tn } });
    setError("");
    setLoading(true);
    setResult(null);
    setLowCoverage(null);
    setOpinionMode(false);
    visualsState.reset();
    setAnalysisOpen(false);
    clearSession();

    // Apply overrides to main state
    if (overrides?.topic !== undefined) setTopic(overrides.topic);
    if (overrides?.tone !== undefined) setTone(overrides.tone);
    if (overrides?.context !== undefined) setContext(overrides.context);

    try {
      // No length: the backend sets the length of a LinkedIn post.
      const res = await api.generatePost({
        topic: t, format: f, tone: tn, context: ctx,
        no_specifics: opts?.noSpecifics ?? false,
        ...businessPost.requestFields(),
      });

      if (!res.ok) {
        const err = await res.clone().json().catch(() => null);
        // Out of posts for the month: explain the plan instead of showing an error.
        const refused = err ? readPaywall(res.status, err) : null;
        if (refused) {
          setPaywall(refused);
          refreshEntitlements();
          return;
        }
        throw new Error(await errorDetail(res, "We couldn't write that post. Please try again."));
      }

      const data: GenerateResult = await res.json();
      refreshEntitlements();
      const outcome = generateOutcome(data);
      if (outcome.kind === "low_coverage") {
        setLowCoverage(outcome.closestSources);
        setNoSpecificsEnabled(outcome.noSpecificsEnabled);
        logEvent({ event_type: "feature_start", page_url: "/create", button_name: "low_coverage_notice" });
        return; // nothing was drafted, so nothing to autosave
      }
      if (outcome.kind === "no_post") {
        // The draft was cut off or declined: say so. Nothing is shown as a post or saved.
        setError(outcome.message);
        logEvent({ event_type: "feature_start", page_url: "/create", button_name: `generate_${outcome.status}` });
        return;
      }
      setOpinionMode(opts?.noSpecifics ?? false);
      businessPost.clearDetails();
      pendingTraceIdRef.current = data.trace_id ?? null;
      currentTraceIdRef.current = data.trace_id ?? null;
      // Store raw post (with placeholders) for /generate-visuals, strip for display/editing
      rawPostRef.current = data.post;
      const cleanPost = stripPlaceholders(data.post);
      setResult(data);
      setEditedPost(cleanPost);
      setEditorHinted(false);
      await autoSavePost(data, cleanPost);
    } catch (e: unknown) {
      // A network failure (TypeError "Failed to fetch") is not something to show as-is.
      setError(e instanceof TypeError ? "We couldn't reach Contendo. Check your connection and try again." : e instanceof Error ? e.message : "Something went wrong. Please try again.");
    } finally {
      setLoading(false);
    }
  };

  const handlePostEditorSelection = () => {
    const el = postEditorRef.current;
    if (!el) return;

    const domSelection = window.getSelection();
    const selection = getSelectionOffsetsWithin(el);
    if (!selection) {
      setInlineSelection(null);
      return;
    }

    const rect = domSelection && domSelection.rangeCount > 0 ? domSelection.getRangeAt(0).getBoundingClientRect() : null;
    setInlineSelection({
      start: selection.start,
      end: selection.end,
      text: selection.text,
      rect,
    });
  };

  const handlePostEditorInput = (e: React.FormEvent<HTMLDivElement>) => {
    isUserInput.current = true;
    const nextValue = extractTextFromEditor(e.currentTarget);
    setEditedPost(nextValue);
  };

  const handleInlineEdit = async () => {
    if (!inlineSelection || !inlineInstruction.trim() || inlineLoading) return;
    setInlineLoading(true);
    try {
      const postId = storedPostId(currentPostId);
      const result = await api.refineSelection({
        selected_text: inlineSelection.text,
        instruction: inlineInstruction,
        full_post: editedPost,
        trace_id: currentTraceIdRef.current,
        post_id: postId,
      });
      if (result.status === "reverted") {
        // Nothing changed. Keep the selection and instruction so they can be amended.
        showToast([result.message, result.sources_message].filter(Boolean).join(" "), "error");
        return;
      }
      const rewrittenText = result.rewritten_text;
      const newPost =
        editedPost.slice(0, inlineSelection.start) +
        rewrittenText +
        editedPost.slice(inlineSelection.end);

      setEditedPost(newPost);
      try {
        sessionStorage.setItem(SS_POST, newPost);
        sessionStorage.setItem("contentOS_last_post", newPost);
      } catch {
        // ignore
      }

      await patchHistory({ content: newPost });
      if (result.note) showToast(result.note, "info");
      setInlineSelection(null);
      setInlineInstruction("");
    } catch (err) {
      console.error("Inline edit failed:", err);
      showToast(
        err instanceof Error && err.message ? err.message : "Couldn't refine that selection. Please try again.",
        "error"
      );
    } finally {
      setInlineLoading(false);
    }
  };

  const dismissInlineToolbar = () => {
    setInlineSelection(null);
    setInlineInstruction("");
  };

  const handleInlineKeyDown = (e: React.KeyboardEvent<HTMLInputElement>) => {
    if (e.key === "Enter") {
      e.preventDefault();
      handleInlineEdit();
    }
    if (e.key === "Escape") {
      e.preventDefault();
      dismissInlineToolbar();
    }
  };

  useEffect(() => {
    if (inlineSelection) {
      const timer = setTimeout(() => inlineInputRef.current?.focus(), 50);
      return () => clearTimeout(timer);
    }
  }, [inlineSelection]);

  const handleCopyLinkedIn = async () => {
    await navigator.clipboard.writeText(pastedText(editedPost));
    setCopiedLinkedIn(true);
    showToast("Copied for LinkedIn", "success");
    logEvent({ event_type: "button_click", page_url: "/create", button_name: "publish_btn", metadata: { platform: "linkedin" } });
    setTimeout(() => setCopiedLinkedIn(false), 1500);
  };

  const handleDrawerRegenerate = (overrides: { topic: string; tone: Tone; context: string }) => {
    setDrawerOpen(false);
    generate(overrides);
  };

  const handleStartOver = () => { logEvent({ event_type: "button_click", page_url: "/create", button_name: "start_over_btn" }); setResult(null); setEditedPost(""); setAnalysisOpen(false); };

  // ─── Derived state ────────────────────────────────────────────────────────

  const postGenerated = !!result;
  const splitActive = postGenerated && analysisOpen && isWide && !visualsVisible;


  const closeAnalysis = () => {
    // Snapshot current DOM content into state before the layout branch
    // switches. Without this, the remounting single-column div could render
    // empty if the user edited the post while the analysis panel was open.
    if (postEditorRef.current) {
      const current = extractTextFromEditor(postEditorRef.current);
      if (current && current !== editedPost) setEditedPost(current);
    }
    setAnalysisOpen(false);
    setSplitRatio(0.75);
  };

  const analysisPanelContent = (
    <AnalysisPanel result={result} scoreLoading={scoreLoading} onClose={closeAnalysis} onRunAnalysis={handleScore} />
  );

  // ─── Shared action buttons for post view ─────────────────────────────────

  const openDrawer = () => { logEvent({ event_type: "button_click", page_url: "/create", button_name: "regenerate_btn" }); setDrawerOpen(true); };
  const openAnalysis = () => {
    logEvent({ event_type: "button_click", page_url: "/create", button_name: "analyse_btn" });
    // Snapshot current DOM content before the layout branch switches.
    // Without this, content typed-but-not-yet-persisted would be lost
    // when the split layout remounts the editor div.
    if (postEditorRef.current) {
      const current = extractTextFromEditor(postEditorRef.current);
      if (current && current !== editedPost) setEditedPost(current);
    }
    setAnalysisOpen(true);
    if (!result?.scored && !scoreLoading) handleScore();
    else if (!isWide) setTimeout(() => analysisRef.current?.scrollIntoView({ behavior: "smooth" }), 50);
  };

  const postActionButtons = (
    <PostActionButtons
      compact={splitActive}
      loading={loading}
      visualsLoading={visualsLoading}
      visualsVisible={visualsVisible}
      hasVisuals={visuals.length > 0}
      copiedLinkedIn={copiedLinkedIn}
      onRegenerate={openDrawer}
      onAnalyse={openAnalysis}
      onShowVisuals={() => setVisualsVisible(true)}
      onHideVisuals={() => setVisualsVisible(false)}
      onGenerateVisuals={handleGenerateVisuals}
      onCopyLinkedIn={handleCopyLinkedIn}
    />
  );

  const mobileActionButtons = (
    <PostActionButtons
      compact={false}
      row
      loading={loading}
      visualsLoading={visualsLoading}
      visualsVisible={visualsVisible}
      hasVisuals={visuals.length > 0}
      copiedLinkedIn={copiedLinkedIn}
      onRegenerate={openDrawer}
      onAnalyse={openAnalysis}
      onShowVisuals={() => setVisualsVisible(true)}
      onHideVisuals={() => setVisualsVisible(false)}
      onGenerateVisuals={handleGenerateVisuals}
      onCopyLinkedIn={handleCopyLinkedIn}
    />
  );

  // ─── Post metadata bar ────────────────────────────────────────────────────

  const postStats = useMemo(() => getPostStats(editedPost), [editedPost]);

  // ─── Render ───────────────────────────────────────────────────────────────

  return (
    <div
      className={splitActive ? "" : "-mx-4 -mt-6 -mb-6 sm:-mx-6 md:-mx-10 md:-mt-10 md:-mb-10 bg-background flex flex-col"}
      style={
        splitActive
          ? {
              position: "fixed",
              top: 0,
              left: "14rem",
              right: 0,
              bottom: 0,
              display: "flex",
              flexDirection: "column",
              background: "#faf9f8",
              zIndex: 10,
            }
          : { minHeight: "100vh" }
      }
    >

      <WorkspaceBar />

      {/* Post layout: unified split / single-column (see PostWorkspace) */}
      {postGenerated && !loading ? (
        <PostWorkspace
          splitActive={splitActive}
          splitRatio={splitRatio}
          isWide={isWide}
          containerRef={splitContainerRef}
          onDragStart={handleDragStart}
          topic={topic}
          tone={tone}
          onStartOver={handleStartOver}
          actions={postActionButtons}
          mobileActions={mobileActionButtons}
          editorRef={postEditorRef}
          opinionMode={opinionMode}
          hinted={editorHinted}
          onEditorFocus={() => setEditorHinted(true)}
          onEditorInput={handlePostEditorInput}
          onEditorSelect={handlePostEditorSelection}
          text={editedPost}
          grounding={result?.grounding}
          postId={currentPostId}
          traceId={currentTraceIdRef.current}
          postStats={postStats}
          saveStatus={lastSaved ? saveStatusText : "Auto-saved to history"}
          analysisOpen={analysisOpen}
          analysisRef={analysisRef}
          analysisPanel={analysisPanelContent}
          visualsPanel={visualsVisible && (
            <VisualsPanel
              entered={visualsPanelEntered}
              visuals={visuals}
              loading={visualsLoading}
              api={api}
              onRegenerate={handleGenerateVisuals}
              onClose={() => setVisualsVisible(false)}
              onVersionChange={handleDiagramVersionChange}
            />
          )}
        />

      ) : (
        // ── Scrollable column (configure / spinner / visuals) ────────────────
        <div className="flex-1 overflow-y-auto">
          <div className="px-4 md:px-10" style={{ maxWidth: 900, margin: "0 auto", paddingTop: "32px", paddingBottom: "32px" }}>

            {/* Ideas panel */}
            {suggestionsVisible && (
              <IdeasPanel
                loading={suggestionsLoading}
                suggestions={suggestions}
                focus={ideaTopic}
                selectedIndex={selectedIdeaIndex}
                onRefresh={handleGetIdeas}
                onDismiss={handleDismissIdeas}
                onUse={handleUseSuggestion}
              />
            )}

            {/* ── Interstitial: continue vs start fresh ───────────────────── */}
            {showInterstitial && (
              <ResumeDraftPrompt
                topic={interstitialTopic}
                score={interstitialScore}
                onContinue={handleContinueEditing}
                onStartFresh={handleStartFresh}
              />
            )}

            {/* ── Configure form ──────────────────────────────────────────── */}
            {!postGenerated && !loading && !showInterstitial && (
              <ConfigureForm
                business={businessPost}
                topicRef={topicRef}
                topic={topic}
                onTopicChange={setTopic}
                tone={tone}
                onToneChange={setTone}
                toneDescOpacity={toneDescOpacity}
                error={error}
                lowCoverage={lowCoverage}
                loading={loading}
                opinionEnabled={noSpecificsEnabled}
                entitlements={entitlements}
                onGenerate={generate}
                logEvent={logEvent}
              />
            )}

            {/* ── Generating spinner ──────────────────────────────────────── */}
            {loading && <ProgressSteps title="Writing your post" steps={GENERATION_STEPS} stepMs={6000} />}

          </div>
        </div>
      )}

      {/* Settings drawer */}
      {postGenerated && (
        <SettingsDrawer
          open={drawerOpen}
          initialTopic={topic}
          initialTone={tone}
          initialContext={context}
          onCancel={() => setDrawerOpen(false)}
          onRegenerate={handleDrawerRegenerate}
        />
      )}

      {inlineSelection && postGenerated && (
        <InlineRefineToolbar
          rect={inlineSelection.rect}
          inputRef={inlineInputRef}
          instruction={inlineInstruction}
          onInstructionChange={setInlineInstruction}
          onKeyDown={handleInlineKeyDown}
          loading={inlineLoading}
          onSubmit={handleInlineEdit}
          onDismiss={dismissInlineToolbar}
        />
      )}

      {paywall && <UpgradeScreen code={paywall.code} message={paywall.message} onClose={() => setPaywall(null)} />}
    </div>
  );
}
