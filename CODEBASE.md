# CODEBASE.md

> Read this file at the start of every new session before touching any code.
> It is the complete technical reference for the Contendo system.

---

## 1. FILE REGISTRY

| File | Description |
|------|-------------|
| `README.md` | Project overview, architecture diagram, setup instructions |
| `CODEBASE.md` | This file — full technical reference |
| `PROMPTS.md` | All agent system prompts verbatim — source of truth for agent behaviour |
| `DESIGN.md` | Editorial Atelier design system — palette tokens, typography (Noto Serif + Inter), No-Line Rule, surface hierarchy, component specs; mandatory reading before any UI change |
| `.gitignore` | Excludes venv, node_modules, .env, chroma_db data |
| **Backend** | |
| `backend/main.py` | FastAPI app entry point — CORS config, lifespan hook (calls `init_db` + `init_hierarchy_db` + `init_retrieval_stats_db`), router registration, and `logging.basicConfig` (level from `LOG_LEVEL` env var, defaults to INFO) |
| `backend/routers/__init__.py` | Empty — marks routers/ as a Python package |
| `backend/routers/ingest.py` | `/ingest`, `/ingest-file`, `/scrape-and-ingest`, `/obsidian/preview`, `/obsidian/ingest` (both with `ENVIRONMENT=production` guard), `/obsidian/preview-zip`, `/obsidian/ingest-zip` (no environment guard — works in production) |
| `backend/routers/generate.py` | `/generate`, `/refine`, `/refine-selection`, `/score`, `/generate-visuals` |
| `backend/routers/history.py` | `GET /history`, `POST /log-post`, `PATCH /history/{id}`, `DELETE /history/{id}`, `POST /history/{id}/restore/{vid}`, `PATCH /history/{id}/publish` |
| `backend/routers/library.py` | `GET /library`, `GET /library/clusters`, `DELETE /library/source` |
| `backend/routers/ideas.py` | `GET /suggestions` |
| `backend/routers/stats.py` | `GET /stats` |
| `backend/routers/profile.py` | `GET /profile`, `POST /profile`, `POST /extract-resume` — per-user profile read/write plus resume extraction; `POST /profile` does a read-back verification after save and returns HTTP 500 if the write didn't land; `POST /extract-resume` accepts `multipart/form-data` with a single `file` (PDF only), extracts text via PyMuPDF (`extract_from_pdf`), sends to Claude Sonnet 4.6 to produce structured `{ name, role, bio, location, topics_of_expertise, voice_descriptors, opinions, writing_samples }` JSON, and returns the parsed dict — does NOT auto-save to profile (frontend merges and saves via `POST /profile`); returns 422 if file is not a PDF, extracted text < 100 chars, or JSON parse fails |
| `backend/routers/debug.py` | **TEMPORARY** — `GET /debug/profile-paths` (no auth); returns `data_dir`, `profiles_dir`, `profiles_dir_exists`, `profile_files`, `environment`; used to verify Railway volume mount; remove once persistence is confirmed |
| `backend/routers/feedback.py` | `POST /feedback` — accepts `{ message: str, page: str }` body; `user_id` from `Depends(get_user_id_dep)`; appends a JSON line to `DATA_DIR/feedback.jsonl` with fields `user_id`, `message`, `page`, `submitted_at` (UTC ISO); returns `{"received": true}`; after writing, fires `_notify_telegram()` via `asyncio.create_task()` (fire-and-forget, never blocks response); `_notify_telegram()` reads `TELEGRAM_BOT_TOKEN` and `TELEGRAM_CHAT_ID` from env — if either is absent, logs a warning and returns silently; on Telegram API failure, catches all exceptions and logs a warning (non-fatal); uses `httpx.AsyncClient(timeout=10)` for the Telegram `sendMessage` call with HTML parse mode |
| `backend/routers/admin.py` | **TEMPORARY** — `POST /admin/migrate-profile` and `POST /admin/migrate-user-data` (both protected by `x-migration-secret` header matching `MIGRATION_SECRET` env var, no Clerk auth); `migrate-profile` accepts `target_user_id` + optional `profile` dict (falls back to legacy `profile.json`); `migrate-user-data` copies ChromaDB chunks, SQLite posts, and hierarchy nodes from `user_id="default"` to a real Clerk user ID — `contendo_default` collection preserved as backup; remove both after all users migrated |
| `backend/requirements.txt` | All Python dependencies pinned — includes rank-bm25>=0.2.2 for hybrid BM25 retrieval |
| `backend/.env.example` | Required env var template — `ANTHROPIC_API_KEY`, `DATA_DIR`, `FRONTEND_ORIGIN`, `ENVIRONMENT`, `CLERK_SECRET_KEY` |
| `backend/Dockerfile` | Production Docker image for Railway — Python 3.11-slim; pre-installs CPU-only `torch==2.2.2` from PyTorch CPU wheel registry (avoids 4 GB image limit); sentence-transformers model downloads at first request (not baked in); uses `$PORT` and `$DATA_DIR` |
| `backend/.dockerignore` | Excludes venv, pycache, local data files, .env from Docker build context |
| `backend/config/__init__.py` | Empty — marks config/ as a Python package |
| `backend/config/paths.py` | Single source of truth for all data paths; reads `DATA_DIR` env var, falls back to `backend/data/` for local dev; exposes `CHROMA_DIR`, `POSTS_DB_PATH`, `HIERARCHY_DB_PATH`, `PROFILE_PATH`, `PROFILES_DIR`, `FEEDBACK_PATH` |
| `backend/agents/ideation_agent.py` | Generates N content ideas from ChromaDB sample, profile, and posted topic history; accepts `user_id` param for per-user data isolation |
| `backend/auth/__init__.py` | Empty — marks auth/ as a Python package |
| `backend/auth/clerk.py` | Clerk JWT verification — `get_user_id(authorization)` verifies Bearer token via JWKS (1hr cache); falls back to `user_id="default"` in non-production when no token; `get_user_id_dep` is the FastAPI `Depends()` dependency used by all protected endpoints |
| `backend/agents/visual_agent.py` | Parses [DIAGRAM:] and [IMAGE:] placeholders from post; calls Claude to generate SVG for diagrams; returns reminder text for images |
| `backend/agents/ingestion_agent.py` | Chunks content, extracts tags via Claude Sonnet, upserts to ChromaDB; after successful upsert: generates a 2-3 sentence source summary via Claude Haiku and writes a source_node + topic_node to hierarchy_store (wrapped in try/except — never blocks ingestion); SHA-256 dedup via `query_by_hash()` before any Claude call |
| `backend/agents/vision_agent.py` | Sends base64 images to Claude vision, returns extracted text |
| `backend/agents/retrieval_agent.py` | Semantic search node in the LangGraph pipeline; builds a `retrieval_bundle` (chunks + source_contexts + topic_contexts) from hierarchy_store; sets `retrieved_context` (pre-formatted enriched text block) and always sets `retrieved_chunks` for backward compat; computes internal coverage signal via `_compute_retrieval_confidence()` and stores `retrieval_confidence` + `retrieved_chunk_count` in pipeline state; falls back to flat retrieval if hierarchy_store is empty; calls `increment_retrieval()` for each unique source title in a try/except block |
| `backend/agents/draft_agent.py` | Calls Claude Haiku via `infer_archetype()` to classify the topic into one of 7 post archetypes, then generates the initial draft via Claude Sonnet; uses `_format_retrieval_context()` which prefers the enriched `retrieved_context` from state and falls back to flat `retrieved_chunks`; injects `_get_grounding_instruction(retrieval_confidence, retrieved_chunk_count)` into the prompt for medium/low confidence calibration (empty string for high confidence); passes `state.get("length", "standard")` into `get_format_instructions()` |
| `backend/agents/critic_agent.py` | Diagnoses the initial draft across hook, substance, structure, and voice; produces a structured JSON brief; runs between `draft_node` and `humanizer_node`; uses Claude Haiku; skipped for draft quality mode |
| `backend/agents/humanizer_agent.py` | Rewrites draft to remove AI patterns, inject human voice; reads `critic_brief` from state and fixes flagged issues before humanizing if any area was rated "needs_work"; exposes `refine_selection()` for targeted single-selection rewrites |
| `backend/agents/scorer_agent.py` | Scores draft 0–100 across 5 dimensions, returns flagged sentences |
| `backend/pipeline/state.py` | TypedDict schema for shared LangGraph pipeline state; includes `length` (`"concise" | "standard" | "long-form"`), `archetype`, `user_id`, `critic_brief`, retrieval calibration fields (`retrieval_confidence`, `retrieved_chunk_count`), `retrieved_chunks` (backward compat flat list), `retrieval_bundle` (full hierarchical bundle), and `retrieved_context` (pre-formatted enriched text for draft prompt) |
| `backend/pipeline/graph.py` | LangGraph graph definition — nodes, edges, conditional retry loop |
| `backend/memory/vector_store.py` | ChromaDB init, upsert, semantic query, stats, delete_source, query_by_hash; `query_similar()` returns `source_id` and `chunk_index` per result; `query_similar_batch()` embeds all queries in a single batched forward pass then queries ChromaDB for each (significantly faster than N sequential `query_similar()` calls); `query_similar_hybrid()` and `query_similar_hybrid_batch()` combine BM25 keyword ranking (rank-bm25) with cosine vector search via Reciprocal Rank Fusion (k=60) — both fall back to pure vector search on any exception; `upsert_chunks()` stores `node_type:"chunk"`; `get_chunks_for_source()` and `get_adjacent_chunks()` for hierarchical sibling retrieval; collections namespaced as `contendo_{user_id}` |
| `backend/memory/profile_store.py` | Per-user profile read/write — `load_profile(user_id)`, `save_profile(profile, user_id)`, `profile_exists(user_id)`; legacy fallback to `data/profile.json` when `user_id="default"`; `DEFAULT_PROFILE` includes bio, location, target_audience, opinions, writing_samples; `profile_to_context_string()` formats all fields for prompt injection; `save_profile()` uses atomic write (`os.replace` from `.tmp`) to prevent corrupt half-writes; all three functions emit INFO-level logs of the exact file path for Railway debugging; `save_writing_sample(user_id, sample, max_samples=10)` appends a new sample to the user's `writing_samples` list (case-insensitive dedup, oldest dropped when over limit) |
| `backend/memory/hierarchy_store.py` | SQLite store (path from `config.paths.HIERARCHY_DB_PATH`) for source_nodes and topic_nodes — `upsert_source_node`, `get_source_node`, `source_node_exists`, `upsert_topic_node`, `get_topic_node`, `find_matching_topic` (tag-overlap heuristic), `add_source_to_topic`; initialized in FastAPI lifespan |
| `backend/memory/retrieval_stats_store.py` | SQLite store for source retrieval counts — `init_retrieval_stats_db`, `increment_retrieval`, `get_retrieval_counts`; uses same `HIERARCHY_DB_PATH` as hierarchy store |
| `backend/memory/feedback_store.py` | SQLite posts and post_versions tables — all functions accept `user_id` param for per-user isolation; `init_db()` runs idempotent `ALTER TABLE` migrations to add `user_id`, `published_at`, `published_platform`, `published_content` columns; `_post_owned_by()` helper validates post ownership before version operations; `mark_published(post_id, platform, published_content, user_id)` sets `published_at=CURRENT_TIMESTAMP`, `published_platform`, and optionally `published_content` |
| `backend/tools/scraper_tool.py` | URL scraper using Jina Reader — `is_valid_url()`, `clean_scraped_text()`, `scrape_url()` |
| `backend/tools/obsidian_tool.py` | Obsidian vault reader — `read_vault()` yields cleaned note dicts from a vault directory; `get_vault_stats()` accepts a path and returns stats (total_files, total_words, estimated_chunks, skipped_files, vault_name); `get_vault_stats_from_dir()` is the refactored core that both local and zip endpoints use; `extract_vault_from_zip(zip_bytes)` extracts a zip file to a temp directory, validates for path traversal attacks (rejects paths starting with `/` or containing `..`), and verifies .md files exist; `clean_obsidian_markdown()` strips wikilinks/frontmatter/Dataview/embeds |
| `backend/tools/__init__.py` | Empty — tools directory retained for future use |
| `backend/utils/chunker.py` | 500-word chunks with 50-word overlap |
| `backend/utils/formatters.py` | Format + tone instruction strings per output type; `get_format_instructions(format_type, length, tone)` appends length-target guidance by format (`concise`/`standard`/`long-form`); `get_archetype_instructions()` returns structural prompt block for each of 7 post archetypes |
| `backend/utils/file_extractor.py` | Extracts plain text from PDF (PyMuPDF), DOCX (python-docx), and TXT files; raises ValueError on unsupported types, scanned PDFs, password-protected PDFs, and empty files |
| `backend/data/profile.json` | User voice and style profile — **gitignored**, never committed. Copy from `profile.template.json` to create. |
| `backend/data/profile.template.json` | Committed template with placeholder values — starting point for new users |
| `backend/data/chroma_db/` | ChromaDB persistent storage (gitignored) |
| `backend/data/posts.db` | SQLite post history (gitignored) |
| `backend/data/hierarchy.db` | SQLite hierarchy store — source_nodes + topic_nodes (gitignored) |
| `backend/data/feedback.jsonl` | Append-only feedback log (gitignored) — one JSON object per line: `{ user_id, message, page, submitted_at }`; created on first submission; readable on Railway via the persistent `/data` volume |
| `scripts/migrate_hierarchy.py` | One-time migration script: backfills hierarchy_store from existing ChromaDB data; idempotent; run with `python scripts/migrate_hierarchy.py [--dry_run] [--force] [--user_id default]` |
| `backend/venv/` | Python virtual environment (gitignored) |
| **Frontend** | |
| `frontend/app/layout.tsx` | Root layout — wraps body in `ClerkProvider`; mounts AppShell which renders Sidebar for app routes; `/welcome`, `/onboarding`, `/sign-in`, `/sign-up` bypass sidebar |
| `frontend/app/page.tsx` | Screen 1: Feed Memory (default route `/`) |
| `frontend/app/library/page.tsx` | Screen 2: Library (`/library`) — two views toggled by a "Sources / Topic Map" segmented control. **Sources view:** source cards with chunk count and retrieval count UX (sage dot marker for 5+ uses), stats bar, text search, filter/sort ("Date Added", "Oldest First", "Most Used"), grid/list toggle; card placeholders use `getTitleGradient()` + `getSourceIcon()`. **Topic Map view:** calls `GET /library/clusters`; renders two tinted summary stat pills (sage and terracotta tints), a color-tiered tag cloud with 3-tier sizing (large ≥7: 15px/600/sage tint, medium 4–6: 13px/500/warm-grey tint, small 2–3: 11px/400/light grey) + collapsible cluster sections with colored left accent bars (5-color cycle: sage, terracotta, slate-blue, warm-brown, dark-sage; deterministic per index % 5). Cluster headers render tag name in Noto Serif italic, 1.1rem. Source rows in clusters (both clustered and unclustered) have 8px color-coded dots before the title (NOTE: sage, ARTICLE: terracotta, IMAGE: slate, default: outline). Unclustered section collapsed by default; clicking a source row switches back to Sources view and sets the search filter to that source title. |
| `frontend/app/create/page.tsx` | Screen 3: Create Post (`/create`) |
| `frontend/app/ideas/page.tsx` | Screen 4: Get Ideas (`/ideas`) — standalone ideas screen with topic filter, count picker, save-for-later; ideas persisted in localStorage |
| `frontend/app/history/page.tsx` | Screen 5: Post History (`/history`) — searchable list, expandable post cards, version pills, restore, delete, diagram rendering; **"Open in editor"** button writes post+topic+format+tone to sessionStorage and navigates to `/create`; **"Mark as published"** button opens a modal (platform pill picker + optional final-version textarea) that calls `PATCH /history/{id}/publish`; published posts show a sage `Published · {Platform}` badge; **All / Published filter toggle** in header bar filters cards client-side |
| `frontend/app/history/[id]/page.tsx` | Post detail page (`/history/[id]`) — full-page view of a single post with version picker, restore, delete, diagram rendering; **"Open in editor"** button; **"Mark as published"** inline modal; published badge when `published_at` is set |
| `frontend/app/welcome/page.tsx` | Landing page (`/welcome`) — standalone editorial marketing surface (top nav + hero + how-it-works + philosophy + toolkit + mood grid + final CTA + footer), accessible to both signed-in and signed-out users. Sections alternate bg-background / bg-surface-container-low for tonal rhythm. Functional hero prompt bar: submit writes `sessionStorage.contendo_topic`; signed-in users go to `/create` (also writes `contentOS_last_topic`); signed-out users go to `/first-post?topic=...`. Nav has single "How it works" → `#how-it-works` scroll link; auth-aware CTA ("Get started" → `/first-post` signed-out, "Open workspace" → `/` signed-in). How-it-works section: three prose steps, no icons, step numbers in Noto Serif italic sage. Mood grid: 8 `MOOD_GRADIENTS` tiles with Noto Serif italic labels, `rounded-2xl`, `minHeight: 160`. No fake social proof, no trial/pricing language anywhere. |
| `frontend/app/globals.css` | Global styles — Tailwind directives, CSS custom properties for design tokens, `.btn-primary` gradient, `.glass` glassmorphism, `.font-headline`/`.serif-text`, grain texture overlay, custom scrollbar, `.input-editorial`, `.label-caps`, `.ghost-border`, `.no-scrollbar` (hides scrollbar on overflow-x-auto nav elements) |
| `frontend/components/ui/ToastProvider.tsx` | Global custom lightweight React Context for floating success/error notifications |
| `frontend/components/ui/FeedbackButton.tsx` | Floating pill button fixed bottom-right (bottom: 24px, right: 24px) on all app routes; opens a centered modal overlay (rgba(0,0,0,0.3) backdrop, 420px card, ambient shadow); modal has Noto Serif "Send feedback" title, subtitle, `input-editorial` textarea, Cancel ghost button + Submit `btn-primary`; on submit calls `api.submitFeedback(message, pathname)`; shows inline "Thanks — feedback received." success state then auto-closes after 2 s; only mounted in the app shell so it never appears on `/welcome`, `/onboarding`, `/sign-in`, `/sign-up` |
| `frontend/components/LoadingWordmark.tsx` | Full-screen loading state (`min-h-screen`, `#faf9f8` background) — centered "Contendo" wordmark in Noto Serif italic, fades in from opacity 0 via RAF + 300ms CSS transition on mount; used by AppShell (profile check in flight) and sso-callback (OAuth handshake) for visual consistency. |
| `frontend/components/AppShell.tsx` | Layout wrapper — renders Sidebar + FeedbackButton for app routes; returns children unwrapped for `/welcome`, `/onboarding`, `/first-post`, `/sign-in`, `/sign-up`; runs `useProfileCheck()` and shows `<LoadingWordmark />` (Noto Serif italic wordmark on `#faf9f8`, 300ms fade-in) while profile check is in flight; **intercept safety net:** after profile check confirms `has_profile === true`, checks `localStorage.contendo_intercept_done` — if absent, renders `OnboardingIntercept` as a fixed overlay on top of the workspace (sidebar + content visible behind blur); `onComplete` callback sets local `interceptDone` state to true so the overlay is dismissed and the workspace takes full focus |
| `frontend/components/OnboardingIntercept.tsx` | One-time 5-question intercept shown after the first-post flow (and as a safety net for returning users who missed it). **Renders as a fixed modal overlay** (`position: fixed, inset: 0, z-index: 50`) on top of the workspace — sidebar and content remain mounted and visible behind `rgba(47,51,51,0.45)` backdrop with `backdrop-filter: blur(4px)`. Modal card: white `#ffffff`, `border-radius: 1.25rem`, `padding: 2.5rem`, `max-width: 480px / width: 90vw`, ambient shadow (`0px 4px 20px rgba(47,51,51,0.06), 0px 12px 40px rgba(47,51,51,0.10)`), no borders. **Entrance animation:** opacity 0→1 + translateY(12px)→0, 250ms ease-out (triggered via RAF on mount). **Exit animation:** opacity 1→0, 150ms ease-in; `onComplete` is called after the 150ms delay so the parent unmounts cleanly after fade. **Progress dots:** active (seen) = 8px sage `#58614f`; inactive = 6px `#aeb3b2` at 40% opacity; gap 8px. **Question text:** Noto Serif italic, 1.4rem, `#2f3333`, centered, max-width 340px, line-height 1.5. **Chips:** unselected `#f3f4f3` bg / transparent border / `#2f3333` text; selected `#eef0eb` bg / `1px solid #58614f` / `#58614f` text; hover `#edeeed`; padding 10px 18px; border-radius 9999px; 0.9rem. **Skip button:** plain text, `#645e57`, 0.85rem, no background. **Next/Done button:** `btn-primary` (sage gradient, white text, rounded-xl). Five questions shown one at a time; Q1–Q4 chip-select, Q5 free-text. **Question → profile field mapping:** Q1 (`voice_descriptors`): communication style; Q2 (`voice_descriptors`): writing mode; Q3 (`target_audience`): audience scalar (only set if empty); Q4 (`writing_rules`): goal chip prefixed `"My goal: "`; Q5 (`opinions`): free text. **Save logic:** loads existing profile, merges answers (list fields appended with case-insensitive dedup, scalar only set if empty), saves via `api.saveProfile()`. **Completion:** sets `localStorage.contendo_intercept_done = "1"`, triggers exit animation, navigates to `destination` prop. |
| `frontend/components/Sidebar.tsx` | Left sidebar navigation — logo, six nav items ordered as Create Post, Feed Memory, Get Ideas, Library, History, Settings; bottom CTA is "Create Post" linking to `/create`; user row at bottom with real user avatar/name/email from `useUser()` and sign-out via `useClerk().signOut()` |
| `frontend/components/ui/TagInput.tsx` | Shared tag pill input component — used by onboarding and settings; accepts Enter/comma to add tags, Backspace to remove last, deduplicates; exports `TagInputProps` interface |
| `frontend/components/FeedMemory.tsx` | Feed Memory form — tabs (Article/Text, URL, File, YouTube, Image, Note, Obsidian), URL scraping, textarea, file upload with drag-and-drop, image upload. **Obsidian tab:** Local Path is conditionally rendered only when `isLocalBackend` is true (`NEXT_PUBLIC_API_URL` contains localhost/127.0.0.1). In that local case, dual-mode toggle pills are shown (Local path / Upload zip), defaulting to Local path. In production (non-local backend), the toggle is hidden entirely and the tab renders the Upload zip flow directly with no Local Path option or notice. Local path mode (local only) shows a text input for vault folder path, optional preview card, and "Preview vault" / "Ingest all notes" buttons. Upload zip mode shows drop zone (dashed ghost-border, surface-container-low bg, accepts .zip files) with drag-over active state; on successful file select calls `previewObsidianZip()`, shows preview stats card, then enables "Ingest vault" / "Choose different file" buttons. Ingesting shows muted progress message "Ingesting vault — this may take a minute…" (no spinner). Both flows show success card with checkmark, file count, chunk count, and sampled tags. **Tooltip tour:** shown when `localStorage.getItem('contendo_feed_tour_done')` is null (single condition — chunk count is not checked, as it caused silent failures for new users). Tour starts 800 ms after mount. Renders a `position: fixed` dark-sage tooltip (`#3a4a35`, `z-index: 9999`, `width: 280px`) anchored below the active tab button — `top` = `tabBarRef bottom + 8px`, `left` = horizontal center of the active button, measured via `getBoundingClientRect()` in a `requestAnimationFrame` callback. An upward CSS-triangle caret (`borderBottom: 8px solid #3a4a35`) points at the active tab. No backdrop/overlay. Card shows: tab name (14px/600/white) + step indicator (11px/55% white), a translucent divider, description text (13px/85% white/1.6 line-height), and Skip/Next→/Done buttons. "Next →" button is white text on `#3a4a35` pill; on step 7 becomes "Done". Tour walks 7 steps (Article → URL → File → YouTube → Image → Note → Obsidian); each step auto-switches the active tab. Completing or skipping sets `contendo_feed_tour_done = "1"` in localStorage. |
| `frontend/components/CreatePost.tsx` | Create Post — 4-state UI; dynamic autosave tracker; settings drawer; split-screen analysis panel. Pre-gen form keeps a calm two-column editorial layout: left column is unchanged (`FORMAT` vertical pills), right column is restructured into `VOICE & RESONANCE` horizontal pills, a muted tone description line below with 8px spacing, and a `LENGTH` row below that with 16px separation. Tone pills display Casual / Technical / Storytelling and send `casual` / `technical` / `storytelling` to the backend. Length pills are two-line, format-aware controls (`concise`/`standard`/`long-form`) with inline metadata (LinkedIn: `~100-150/~200-300/~400-600 words`, Medium: `~350-500/~700-900/~1200-1600 words`, Thread: `4-5/7-9/11-14 tweets`) that update when the selected format changes. A left-column quote block sits below the format pills with a sage accent border. The headline remains `Drafting a new thought` in Noto Serif at 3rem, and the primary action button reads `CREATE POST →`. Selected length persists in sessionStorage under `contentOS_last_length` and is restored on mount/session resume. Generate calls include `length` in `POST /generate`. Post-gen: manuscript-style contentEditable canvas with a requestAnimationFrame DOM sync effect keyed to both layout branch switches and loading-driven post-gen mount transitions so generated text renders immediately on first show. Non-split view uses the shared manuscript column (`maxWidth: 768`) for title/status/canvas/footer, with the desktop action stack offset from the canvas edge (`right: 100%`, `marginRight: 32`). Split view remains available on wide screens with a draggable divider controlled by `splitRatio` (default 0.75, clamped to 0.35–0.82). The editor uses a scoped `.manuscript-editor` class to remove the black focus outline and apply the muted sage text-selection tint. Copy actions stay split between stripped LinkedIn and raw Markdown Medium output; `stripMarkdown(text)` remains the pure formatter utility. The inline toolbar is glassmorphic / pill-shaped, anchored above the current selection, and dismisses on outside click or Escape. Analysis panel remains on the right in split view and stacked below on narrow viewports. |
| `frontend/middleware.ts` | Clerk v5 middleware — three routing rules: (1) authenticated users hitting `/` are redirected to `/create` (workspace entry point); (2) unauthenticated visitors hitting `/` are redirected to `/welcome` (landing page); (3) all other unauthenticated requests to protected routes are redirected to `/sign-in?redirect_url=<original-url>` (preserves post-login destination). `/welcome` is accessible to both signed-in and signed-out users — no forced redirect away. Public routes that bypass auth check: `/welcome`, `/sign-in(.*)`, `/sign-up(.*)`, `/onboarding`, `/first-post`, `/sso-callback`. |
| `frontend/app/first-post/page.tsx` | Standalone conversion-focused route — no sidebar; auth invite for signed-out users (Google OAuth + email), plus a **6-step** guided flow for signed-in users: step 0 topic+format → step 1 role → step 2 experience type → step 3 opinion → step 4 audience+voice → **step 5 resume upload**. Step 5 headline is "One last thing" (Noto Serif italic); shows a drag-and-drop PDF-only upload zone (`ResumeDropZone` subcomponent, `rounded-2xl`, dashed ghost-border, surface-container-low bg); primary action "Upload resume →" becomes "Reading your resume..." while uploading; plain-text "Skip for now" link below advances to generate without uploading and sets `resumeSkipped=true`. On resume upload the page calls `POST /extract-resume`, and on success passes extracted fields directly to `handleGenerate()` to avoid stale React closure (extraction result is passed as `resumeFieldsOverride` arg — not read from state). `handleGenerate(resumeFieldsOverride?)` builds merged profile via `buildMergedProfile(finalAnswers, effectiveResumeFields, fallbackExtractedFields)` then saves via `POST /profile` before calling `POST /generate`. **Profile merge priority** (highest to lowest): onboarding 5-question answers > resume extraction fields > fallback Q&A fields. For list fields (`topics_of_expertise`, `voice_descriptors`, `opinions`, `writing_samples`): `mergeStringArrays()` concatenates and deduplicates (case-insensitive) without overwriting. **Profile Gate:** after generation completes and draft is shown, if `resumeSkipped=true`, clicking either CTA button ("Add sources and improve →" or "Go to workspace →") sets `pendingDestination` and transitions to `flowState='gate'`. **Onboarding Intercept:** if `resumeSkipped=false` (resume uploaded or skipped normally), `handleCTA()` checks `localStorage.contendo_intercept_done` — if absent, sets `flowState='intercept'` and renders `OnboardingIntercept` with the destination URL. If already set, navigates directly as before. flowState type includes `'intercept'` as a value. |
| `frontend/app/sso-callback/page.tsx` | Handles Clerk OAuth redirects from Google SSO — renders `<AuthenticateWithRedirectCallback afterSignInUrl="/create" afterSignUpUrl="/create" />` which completes the OAuth handshake and redirects to `/create`; new users are then caught by `useProfileCheck` and forwarded to `/first-post`. Shows `<LoadingWordmark />` while the handshake is in flight. Public route. |
| `frontend/lib/first-post-constants.ts` | All hardcoded data for the `/first-post` flow: `ROLE_OPTIONS` (9 roles with keys + labels), `ROLE_TO_BUCKET` mapping (role → data/product/engineering/founder bucket), `OPINION_STATEMENTS` per bucket (5 statements each), `EXPERIENCE_OPTIONS` (5 types with sublabels), `EXPERIENCE_PLACEHOLDER` per role (role-specific example sentences), `CORE_AUDIENCE_PILLS` (6 universal pills), `ROLE_AUDIENCE_PILLS` (role-specific pills shown first in Screen 5). |
| `frontend/lib/api.ts` | `useApi()` hook — returns all typed API functions with Bearer token pre-attached via `useAuth().getToken()`; single source of truth for all backend calls; replaces raw `fetch()` in all components; `saveProfile()` throws on non-2xx (instead of returning the response) and console.logs status for debugging; `submitFeedback(message, page)` posts to `POST /feedback`; `refineSelection()` calls `POST /refine-selection`; `extractResume(file: File)` sends `multipart/form-data` to `POST /extract-resume` |
| `frontend/hooks/useProfileCheck.ts` | `useProfileCheck()` hook — runs after Clerk confirms auth, calls `GET /profile`, redirects to `/first-post` only if `has_profile === false` (file does not exist); `has_profile: true` with empty name (`profile_complete: false`) does NOT redirect — user is allowed into workspace; no-op on public routes (`/welcome`, `/sign-in`, `/sign-up`, `/onboarding`, `/first-post`); exposes `{ loading, hasProfile, profileComplete, profile }` |
| `frontend/app/sign-in/[[...sign-in]]/page.tsx` | Clerk prebuilt `<SignIn />` page with Editorial Atelier wordmark (Noto Serif italic) and sage `#58614f` primary color; reads `redirect_url` from `searchParams`, passes it through to Clerk (`forceRedirectUrl` + `fallbackRedirectUrl`) and preserves it when switching to sign-up via `signUpUrl` |
| `frontend/app/sign-up/[[...sign-up]]/page.tsx` | Clerk prebuilt `<SignUp />` page, identical structure to sign-in page; reads `redirect_url` from `searchParams`, passes it through to Clerk (`forceRedirectUrl` + `fallbackRedirectUrl`) and preserves it when switching to sign-in via `signInUrl` |
| `frontend/app/onboarding/page.tsx` | Legacy 5-step onboarding flow (no longer the new-user entry point) — immediately redirects to `/first-post` via `router.replace()` on mount; route kept for backward compat so old links don't 404 |
| `frontend/app/settings/page.tsx` | Settings hub at `/settings` — 2-column card grid (1-col mobile); loads profile + stats in parallel; 6 cards: **Profile** (avatar, name, role, bio excerpt → `/settings/profile`), **Voice & Fingerprint** (4 stat rows for phrases/avoid/rules/topics → `/settings/profile`), **Writing Samples** (count + nudge → `/settings/profile`), **Memory** (chunk count, tag count → `/library`; "clear/export coming soon"), **Account** (Clerk avatar/email, working sign-out, "delete coming soon"), **Integrations** ("Soon" badge, 6 future sources listed); all cards animate-pulse skeleton while loading |
| `frontend/app/settings/profile/page.tsx` | Full profile editor at `/settings/profile` — moved from old `/settings`; all fields and behavior preserved; additions: back link "← Settings", live-updating profile summary header card (avatar initials, name, role, location), sticky section nav (Identity · Audience · Voice · Opinions · Samples · Advanced) with anchor links and `scrollMarginTop: 72px`, each section wrapped in `bg-surface-container-low rounded-2xl` card; sticky save button with amber dirty dot and spinner; `beforeunload` guard; Advanced section collapsed by default |
| `frontend/.env.local` | Sets `NEXT_PUBLIC_API_URL=http://localhost:8000` and `NEXT_PUBLIC_CLERK_PUBLISHABLE_KEY` |
| `frontend/tailwind.config.ts` | Tailwind config scoped to app/ and components/; extends colors with full Material Design token set (primary, secondary, tertiary, surface-container-*, on-surface, outline-variant, error); custom box shadows (card, card-hover, float, ambient, focus); border radius overrides; font families (headline: Noto Serif, body/sans: Inter) |
| `frontend/package.json` | Next.js 14 app with TypeScript + Tailwind |

---

## 2. AGENT CONTRACTS

### ingestion_agent.py
| | |
|---|---|
| **Reads** | `content: str`, `source_type: str` (passed directly, not from pipeline state) |
| **Writes** | Returns `{ chunks_stored: int, tags: list[str] }` on new content; `{ chunks_stored: int, tags: list[str], duplicate: True }` if content already exists — not a pipeline node |
| **Side effects** | Computes SHA-256 hash of normalised content and calls `query_by_hash()` before any Claude call. If duplicate: returns immediately. If new: calls Claude for tag extraction, upserts chunks to ChromaDB with `source_title`, `ingested_at`, and `content_hash` in metadata. |

### vector_store.py — get_all_sources()
| | |
|---|---|
| **Reads** | All ChromaDB chunk metadatas via `collection.get()` |
| **Returns** | `list[dict]` — one entry per unique `source_id` with `source_title`, `source_type`, `ingested_at`, `chunk_count`, `tags` (deduplicated) |
| **Sort** | Newest `ingested_at` first; sources without timestamp sort last |

### vector_store.py — query_by_hash()
| | |
|---|---|
| **Reads** | `content_hash: str`, `user_id: str = "default"` |
| **Returns** | `{ chunk_count: int, tags: list[str] }` if hash found; `None` if not found |
| **Side effects** | Two `collection.get()` calls with a metadata filter — no vector search |

### vision_agent.py
| | |
|---|---|
| **Reads** | `image_base64: str`, `media_type: str` (passed directly) |
| **Writes** | Returns `str` — extracted knowledge text |
| **Side effects** | None (output fed into ingestion_agent) |

### retrieval_node (retrieval_agent.py)
| | |
|---|---|
| **Reads from state** | `topic`, `context`, `user_id` (defaults to `"default"` if absent) |
| **Writes to state** | `retrieved_chunks: list[str]` |
| **Side effects** | Queries the `contendo_{user_id}` ChromaDB collection; filters below 0.3 cosine similarity |

### draft_node (draft_agent.py)
| | |
|---|---|
| **Reads from state** | `profile`, `retrieved_chunks`, `topic`, `format`, `tone`, `length`, `context` |
| **Writes to state** | `current_draft: str`, `archetype: str` (inferred archetype key, e.g. `"incident_report"`) |
| **Side effects** | 2 Claude API calls: Haiku (`claude-haiku-4-5-20251001`) for `infer_archetype()`, then Sonnet (`claude-sonnet-4-6`) for the draft |

### critic_node (critic_agent.py)
| | |
|---|---|
| **Reads from state** | `current_draft`, `profile`, `archetype`, `retrieved_chunks`, `quality` |
| **Writes to state** | `critic_brief: dict` — structured JSON with verdict + fix per area and an overall verdict |
| **Side effects** | 1 Claude Haiku call (`claude-haiku-4-5-20251001`, `max_tokens=600`). Skipped entirely for `draft` quality mode (sets `critic_brief: {}` with no API call). All exceptions caught — sets `critic_brief: {}` on failure so the pipeline never breaks. |

**critic_brief schema:**
```json
{
  "structure": { "verdict": "strong" | "needs_work", "fix": "instruction or null" },
 Vercel and Railway/Render deployment config files
  "voice":     { "verdict": "strong" | "needs_work", "fix": "instruction or null" },
  "overall":   "postable" | "needs_work"
}
```
On JSON parse failure: returns `_NEUTRAL_BRIEF` (all "strong", overall "postable") so the humanizer always receives a valid dict.

### humanizer_node (humanizer_agent.py)
| | |
|---|---|
| **Reads from state** | `profile`, `current_draft`, `critic_brief` |
| **Writes to state** | `current_draft: str` (overwrites), `iterations: int` (increments by 1) |
| **Side effects** | 1 Claude Sonnet call per invocation. `_format_critic_brief()` converts `critic_brief` into `(critic_section, rewrite_instruction)` injected into `SYSTEM_PROMPT`. When any area has `"needs_work"`, the humanizer fixes hook/substance/structure/voice first then humanizes. When all areas are "strong" or brief is `{}`, behavior is identical to the old prompt (preserve structure, language-only pass). |

### scorer_node (scorer_agent.py)
| | |
|---|---|
| **Reads from state** | `current_draft` |
| **Writes to state** | `score: int`, `score_feedback: list[str]` |
| **Side effects** | 1 Claude API call — only invoked for polished mode. Skipped entirely for standard and draft modes (graph routes humanizer → finalize directly). |

### load_profile_node (graph.py inline)
| | |
|---|---|
| **Reads** | `profile.json` from disk; calls `get_all_topics_posted()` from feedback_store |
| **Writes to state** | `profile: dict`, `iterations: 0`, `posted_topics: list[str]` |

### finalize_node (graph.py inline)
| | |
|---|---|
| **Reads from state** | `current_draft` |
| **Writes to state** | `final_post: str` |

---

## 3. API CONTRACT

### GET /profile
**Response:**
```json
{
  "profile": { "name": "Alex Chen", "role": "Staff Engineer", ... },
  "has_profile": true,
  "profile_complete": true
}
```
**Notes:** Returns the profile for the authenticated user. The profile is always returned (falling back to `DEFAULT_PROFILE`) regardless of `has_profile`.

| Field | Meaning | Redirect behaviour |
|---|---|---|
| `has_profile: false` | Profile file does not exist on disk | Redirect to `/first-post` (new user) |
| `has_profile: true, profile_complete: false` | File exists but `name` is empty | Allow into workspace — thin profile, do not redirect |
| `has_profile: true, profile_complete: true` | File exists and `name` is non-empty | Fully set up — normal workspace access |

`has_profile` uses raw file existence (`_profile_path(user_id).exists()`). `profile_complete` is `bool(profile["name"].strip())`. Only `has_profile === false` triggers the `/first-post` redirect in `useProfileCheck`.

---

### POST /profile
**Request body:** Full profile object (see profile.json schema below)
**Response:**
```json
{ "saved": true }
```
**Notes:** Saves the profile to `DATA_DIR/profiles/profile_{user_id}.json`. Creates the `profiles/` directory if it does not exist.

---

### POST /extract-resume
**Request:** `multipart/form-data` with a single `file` field (PDF only)
**Response:**
```json
{
  "name": "Alex Chen",
  "role": "Staff Machine Learning Engineer",
  "bio": "I build ML systems that ship...",
  "location": "San Francisco, CA",
  "topics_of_expertise": ["MLOps", "distributed training", "model evaluation"],
  "voice_descriptors": ["direct and technical", "systems-first thinker"],
  "opinions": ["Automation beats manual processes in every data pipeline"],
  "writing_samples": []
}
```
**Error cases:**
- `422` — file is not a PDF
- `422` — extracted text is under 100 characters ("Could not extract text from this PDF. Please try a different file.")
- `422` — Claude JSON parse failure ("Resume extraction failed. Please try again or skip.")

**Notes:** Text is extracted via PyMuPDF (`extract_from_pdf` from `utils/file_extractor.py`). Extracted text is passed to `claude-sonnet-4-6` with a structured extraction prompt. Returns the parsed dict directly — does NOT auto-save to profile. The frontend merges returned fields into the existing profile state and saves via `POST /profile`. Protected with `Depends(get_user_id_dep)`.

---

### POST /obsidian/preview
**Request body:**
```json
{ "vault_path": "/Users/yourname/Documents/ObsidianVault" }
```
**Response:**
```json
{
  "vault_name": "ObsidianVault",
  "total_files": 87,
  "total_words": 42300,
  "estimated_chunks": 105,
  "skipped_files": 12
}
```
**Notes:** Reads all `.md` files from the vault path and returns stats without ingesting anything. Raises 400 if the path does not exist, is not a directory, or is otherwise invalid. `skipped_files` counts notes shorter than 100 characters after cleaning and files that fail to read. `estimated_chunks` is `max(1, round(total_words / 400))` — always at least 1 when content exists.

---

### POST /obsidian/ingest
**Request body:**
```json
{ "vault_path": "/Users/yourname/Documents/ObsidianVault" }
```
**Response:**
```json
{
  "total_files_processed": 85,
  "total_chunks_stored": 203,
  "total_words_processed": 41500,
  "skipped_files": 2,
  "all_tags": ["ai", "machine learning", "product strategy"]
}
```
**Notes:** Ingests all vault notes via `read_vault()` → `ingest_content()` with `source_type="note"` and `source_title` set to the note filename stem. Per-note errors are caught and skipped; `skipped_files` counts notes that errored during ingestion (not the same as `get_vault_stats` skipped count which refers to short notes). Re-ingesting the same vault is safe — ChromaDB upsert prevents duplicate chunks. Can take 30–120 seconds for large vaults. **Environment guard:** This endpoint returns 400 with a message on production (`ENVIRONMENT=production`). Local path ingestion only works on localhost.

---

### POST /obsidian/preview-zip
**Request:** `multipart/form-data` with a single `file` field (`.zip` archive)
**Response:**
```json
{
  "vault_name": "ObsidianVault",
  "total_files": 87,
  "total_words": 42300,
  "estimated_chunks": 105,
  "skipped_files": 12
}
```
**Notes:** Uploads and temporarily extracts a zipped Obsidian vault, then returns preview stats without ingesting. Raises 400 for invalid/corrupted zip files, zip files with no `.md` files, or path traversal attempts (entries starting with `/` or containing `..'). Raises 413 if file exceeds 50 MB. Temp directory is cleaned up after response. **No environment guard** — works on both localhost and production.

---

### POST /obsidian/ingest-zip
**Request:** `multipart/form-data` with a single `file` field (`.zip` archive)
**Response:**
```json
{
  "total_files_processed": 85,
  "total_chunks_stored": 203,
  "total_words_processed": 41500,
  "skipped_files": 2,
  "all_tags": ["ai", "machine learning", "product strategy"]
}
```
**Notes:** Uploads and temporarily extracts a zipped Obsidian vault, then ingests all notes via `read_vault()` → `ingest_content()` with `source_type="note"`. Response schema matches local path ingestion. Raises 400 for invalid/corrupted zip files, zip files with no `.md` files, or path traversal attempts. Raises 413 if file exceeds 50 MB. Temp directory is cleaned up in a `finally` block even if ingestion errors occur. Can take 30–120 seconds for large vaults. **No environment guard** — works on both localhost and production. This endpoint removes the production blocker for Obsidian vault ingestion.

---

### POST /scrape-and-ingest
**Request body:**
```json
{ "url": "https://example.com/article" }
```
**Response:**
```json
{
  "chunks_stored": 6,
  "tags": ["ai", "machine learning"],
  "title": "Why RAG fails in production",
  "word_count": 1204
}
```
**Notes:** Calls `scrape_url()` from `tools/scraper_tool.py`, which fetches via Jina Reader (`https://r.jina.ai/{url}`) and returns clean markdown. Raises 400 for invalid URLs, timeouts, non-200 responses, or pages with < 200 chars of content. Title is extracted from the first `# ` heading in the scraped markdown; falls back to the URL itself. Content is passed to `ingest_content()` with `source_type="article"` and the extracted title as `source_title`.

---

### POST /ingest
**Request body:**
```json
{
  "content": "string (required unless source_type is image)",
  "source_type": "article | youtube | image | note",
  "raw_image": "base64 string (required if source_type is image, optional otherwise)"
}
```
**Response:**
```json
{
  "chunks_stored": 3,
  "tags": ["machine learning", "transformers", "inference"]
}
```
**Notes:** For `image` source_type, backend calls `vision_agent` first, then passes extracted text to `ingestion_agent`. For all others, `content` is chunked and embedded directly.

---

### POST /ingest-file
**Request:** `multipart/form-data` with a single `file` field (PDF, DOCX, or TXT)
**Response:**
```json
{
  "chunks_stored": 4,
  "tags": ["machine learning", "transformers"]
}
```
**Notes:** 10 MB max size limit (returns 413 if exceeded). Text is extracted via `utils/file_extractor.py`, then passed to `ingest_content()` with `source_type="article"`. Raises 422 for unsupported file types, scanned/image-only PDFs (<100 chars extracted), password-protected PDFs, corrupted files, or empty files.

---

### POST /generate
**Request body:**
```json
{
  "topic": "string (required)",
  "format": "linkedin post | medium article | thread",
  "tone": "casual | technical | storytelling",
  "length": "concise | standard | long-form (optional, default standard)",
  "context": "string (optional, default empty)"
}
```
**Response:**
```json
{
  "post": "final post text",
  "score": 82,
  "score_feedback": ["Sentence in paragraph 2 is too generic.", "Avoid 'it's worth noting'"],
  "iterations": 2,
  "archetype": "incident_report",
  "scored": true,
  "retrieval_confidence": "medium"
}
```
**Notes:** Runs the full LangGraph pipeline. `length` defaults to `"standard"` and is injected into draft prompt formatting via `get_format_instructions(format_type, length, tone)`. `quality` defaults to `"standard"` (1 humanizer pass, scorer skipped — lazy). Pass `"polished"` for up to 3 humanizer iterations with scorer running each pass. Pass `"draft"` to skip humanizer and scorer entirely. `scored` in the response indicates whether the scorer ran: `false` for `standard` and `draft` modes (use `POST /score` to score on demand), `true` for `polished` mode. `retrieval_confidence` is an informational internal retrieval-coverage signal (`"low" | "medium" | "high"`) returned for observability only; generation behavior never blocks on this value. Posts are NOT auto-saved by this endpoint — the frontend calls `/log-post` automatically after generation completes.

---

### POST /log-post
**Request body:**
```json
{
  "topic": "string",
  "format": "linkedin post | medium article | thread",
  "tone": "casual | technical | storytelling",
  "content": "string — the post text (may differ from generated if user edited it)",
  "authenticity_score": 82,
  "svg_diagrams": [
    { "position": 0, "description": "...", "svg_code": "<svg>...</svg>" }
  ],
  "archetype": "incident_report"
}
```
**Response:**
```json
{ "post_id": 7, "saved": true }
```
**Notes:** Called automatically by the frontend immediately after generation completes. Returns `post_id` which the frontend stores in `contentOS_current_post_id` sessionStorage for subsequent PATCH calls. `svg_diagrams` is null on initial auto-save; updated later via PATCH when visuals are generated.

---

### GET /history
**Response:**
```json
{
  "posts": [
    {
      "id": 7,
      "created_at": "2026-03-15 14:22:01",
      "topic": "Why RAG fails in production",
      "format": "linkedin post",
      "tone": "technical",
      "content": "Full post text...",
      "authenticity_score": 82,
      "svg_diagrams": [
        { "position": 0, "description": "...", "svg_code": "<svg>...</svg>" }
      ]
    }
  ]
}
```
**Notes:** Returns up to 20 most recent saved posts, newest first. `svg_diagrams` is `null` for posts saved before the visuals feature or saved without diagrams. The JSON string stored in SQLite is parsed back to a list before returning. Each post includes a `versions` array (see `post_versions` schema) with all versions ordered by `version_number` ascending; `svg_diagrams` within each version is also parsed from JSON. Each post also includes `published_at` (ISO timestamp or `null`), `published_platform` (string or `null`), and `published_content` (string or `null`).

---

### POST /history/{post_id}/restore/{version_id}
**Response:**
```json
{
  "restored": true,
  "version_number": 2,
  "content": "restored post text",
  "authenticity_score": 82
}
```
**Notes:** Sets the parent `posts` row `content` and `authenticity_score` to match the specified version. Does not create a new version row. The frontend writes the restored content to `contentOS_last_post` (and related sessionStorage keys) so it appears immediately in Create Post.

---

### PATCH /history/{post_id}/publish
**Request body:**
```json
{ "platform": "linkedin", "published_content": "optional final version text" }
```
**Response:**
```json
{ "published": true }
```
**Notes:** Sets `published_at = CURRENT_TIMESTAMP`, `published_platform`, and optionally `published_content` on the post row. If `published_content` is non-empty, also calls `save_writing_sample(user_id, published_content)` which appends the text to the user's `writing_samples` list (case-insensitive dedup, max 10 kept). Auth: `Depends(get_user_id_dep)`. Returns 404 if post not found or does not belong to user.

---

### GET /suggestions
**Query params:**
- `count` (int, default 8, range 1–15)
- `topic` (str, optional) — if provided, focuses sampling on the given topic

**Response:**
```json
{
  "suggestions": [
    {
      "title": "What 3 production outages taught me about RAG chunking",
      "angle": "Specific failure modes nobody talks about in tutorials",
      "format": "linkedin post",
      "reasoning": "Resonates with ML engineers who've hit the same walls"
    }
  ]
}
```
**Notes:** Calls ideation_agent. If `topic` is provided: uses 3 focused queries (topic, topic + "lessons learned", topic + "failure or mistake") plus 1 random tag for diversity; injects a topic focus instruction into the prompt. If `topic` is omitted: existing multi-query diversity sampling (8 queries: 5 broad topics + 2 random tags + 1 oldest-source query) across up to 30 ChromaDB chunks. All previously posted topics are always excluded.

---

### POST /generate-visuals
**Request body:**
```json
{ "post_content": "string — full post text including [DIAGRAM:] and [IMAGE:] placeholders" }
```
**Response:**
```json
{
  "visuals": [
    {
      "type": "diagram",
      "placeholder": "[DIAGRAM: RAG pipeline showing query → retrieval → generation]",
      "description": "RAG pipeline showing query → retrieval → generation",
      "position": 0,
      "svg_code": "<svg viewBox='0 0 680 400' ...>...</svg>",
      "reminder_text": null
    },
    {
      "type": "image_reminder",
      "placeholder": "[IMAGE: Screenshot of latency dashboard]",
      "description": "Screenshot of latency dashboard",
      "position": 1,
      "svg_code": null,
      "reminder_text": "Add a visual here: Screenshot of latency dashboard. Use a real photo, screenshot, or data chart that shows this directly."
    }
  ]
}
```
**Notes:** One Claude call per `[DIAGRAM:]` placeholder; zero Claude calls for `[IMAGE:]`. Visuals returned in the order placeholders appear in the post. If SVG generation fails, `svg_code` is `null` and the frontend shows an error card.

---

### DELETE /history/{post_id}
**Response:**
```json
{ "deleted": true }
```
**Notes:** Deletes the post with the given id from SQLite. Returns `deleted: false` if the id does not exist.

---

### PATCH /history/{post_id}
**Request body (all fields optional — only provided fields are updated):**
```json
{
  "content": "updated post text",
  "authenticity_score": 85,
  "svg_diagrams": [{ "position": 0, "description": "...", "svg_code": "<svg>...</svg>" }]
}
```
**Response:**
```json
{ "updated": true }
```
**Notes:** Partial update — uses Pydantic `model_fields_set` to identify which fields were explicitly provided; only those fields are written to SQLite. Called by the frontend after refinement (content + score) and after visuals generation (svg_diagrams only). A request with no fields returns `updated: false` without touching the DB.

---

### POST /refine
**Request body:**
```json
{
  "current_draft": "string — the post text to refine",
  "refinement_instruction": "string — specific instruction describing what to fix"
}
```
**Response:**
```json
{
  "refined_draft": "string — the refined post text",
  "score": 82,
  "score_feedback": ["note 1", "note 2", "flagged sentence"]
}
```
**Notes:** Calls `refine_draft()` from `humanizer_agent.py` once, then `score_text()` from `scorer_agent.py` once. Does NOT run the full LangGraph pipeline — no retrieval, no draft agent, no retry loop. Designed for targeted fixes after the initial generation. Both functions are standalone callables extracted from their respective pipeline nodes.

---

### POST /refine-selection
**Auth:** `Depends(get_user_id_dep)`
**Request body:**
```json
{
  "selected_text": "string — the highlighted text to rewrite",
  "instruction": "string — what to do with it",
  "full_post": "string — entire post for voice/context reference"
}
```
**Response:**
```json
{ "rewritten_text": "string — rewritten selection only" }
```
**Notes:** Rewrites only the `selected_text`. `full_post` is context only — never rewritten. One Claude Sonnet call (`max_tokens=500`). Profile loaded server-side by `user_id` from auth token. Returns the rewritten fragment; frontend splices it back into the post at the original selection offsets.

---

### POST /score
**Request body:**
```json
{ "post_content": "string — the post text to score" }
```
**Response:**
```json
{
  "score": 78,
  "score_feedback": ["note 1", "note 2", "flagged sentence"]
}
```
**Notes:** Standalone scoring endpoint. Calls `score_text()` directly — no pipeline. Used by the frontend when the user requests analysis on a standard-mode post (where the scorer was skipped during generation). Does not save to history — frontend calls `PATCH /history/{id}` separately if it wants to persist the score.

---

### DELETE /library/source
**Request body:**
```json
{ "source_title": "Why RAG fails in production — 3 lessons" }
```
**Response:**
```json
{
  "deleted": true,
  "chunks_removed": 5,
  "message": "Removed 5 chunks"
}
```
**Notes:** Deletes all ChromaDB chunks with matching `source_title` metadata via `delete_source()` in `vector_store.py`. Returns 404 if no chunks found with that title. The frontend removes the card from the UI immediately and subtracts `chunks_removed` from the displayed total.

---

### GET /library/clusters
**Auth:** `Depends(get_user_id_dep)`
**Response:**
```json
{
  "clusters": [
    {
      "tag": "machine learning",
      "source_count": 14,
      "total_chunks": 87,
      "sources": [
        { "source_title": "Why RAG fails in production", "source_type": "article", "ingested_at": "2026-03-18T10:22:01+00:00" }
      ]
    }
  ],
  "unclustered_sources": [
    { "source_title": "My quick note", "source_type": "note", "ingested_at": "2026-03-20T08:00:00+00:00" }
  ],
  "total_sources": 22,
  "total_tags": 8
}
```
**Notes:** Tags are normalised to lowercase. Only tags appearing in 2+ sources form clusters. `unclustered_sources` contains sources where every tag they have appears in fewer than 2 sources total. Clusters sorted by `source_count` descending. Near-duplicate tag merging is exact lowercase match only — no fuzzy matching.

---

### GET /library
**Response:**
```json
{
  "sources": [
    {
      "source_title": "Why RAG fails in production — 3 lessons",
      "source_type": "article",
      "ingested_at": "2026-03-18T10:22:01+00:00",
      "chunk_count": 5,
      "tags": ["rag", "machine learning", "production systems"],
      "retrieval_count": 12
    }
  ],
  "total_chunks": 47,
  "total_sources": 9
}
```
**Notes:** Groups all ChromaDB chunks by `source_id`. Sources without `ingested_at` (ingested before this feature) sort last. Source titles derived from first 80 chars of ingested content.

---

### GET /stats
**Response:**
```json
{
  "total_chunks": 47,
  "tags": ["ai", "machine learning", "product strategy", "startups"]
}
```

---

### POST /admin/migrate-profile *(TEMPORARY)*
**Auth:** `x-migration-secret` header must match `MIGRATION_SECRET` env var. No Clerk auth.
**Request body:**
```json
{
  "target_user_id": "user_3BYsin1Q4qNbSpkYOKnhPCTTarN",
  "profile": { ... }  // optional — if omitted, reads legacy DATA_DIR/profile.json
}
```
**Response:**
```json
{
  "migrated": true,
  "source": "/data/profile.json",
  "to": "/data/profiles/profile_user_3BYsin1Q4qNbSpkYOKnhPCTTarN.json",
  "name": "Soham Patil"
}
```
**Notes:** Writes a profile for any user ID without requiring Clerk auth. If `profile` is provided in the body, that data is used directly. Otherwise falls back to reading `DATA_DIR/profile.json`. Returns 403 if secret is wrong, 404 if no legacy profile exists and no inline `profile` was provided, 500 if `MIGRATION_SECRET` is unset.

---

### POST /admin/migrate-user-data *(TEMPORARY)*
**Auth:** `x-migration-secret` header must match `MIGRATION_SECRET` env var. No Clerk auth.
**Request body:**
```json
{ "target_user_id": "user_3BYsin1Q4qNbSpkYOKnhPCTTarN" }
```
**Response:**
```json
{
  "migrated": true,
  "target_user_id": "user_3BYsin1Q4qNbSpkYOKnhPCTTarN",
  "chunks_migrated": 312,
  "posts_migrated": 47,
  "hierarchy": "18 nodes migrated",
  "note": "contendo_default collection preserved as backup. Profile migration is separate — run /admin/migrate-profile too."
}
```
**Notes:** One-time migration that copies all data from `user_id="default"` to a real Clerk user ID. Three steps: (1) gets `contendo_default` ChromaDB collection and upserts all chunks + embeddings + metadata into `contendo_{target_user_id}` — `contendo_default` is NOT deleted (backup); (2) updates `posts` table in `posts.db` WHERE `user_id='default'`; (3) updates `source_nodes` and `topic_nodes` in `hierarchy.db` if a `user_id` column exists (skipped with message if not). Returns 403 if secret is wrong, 404 if `contendo_default` not found, 500 with `{"step": "chromadb"|"posts"|"hierarchy", "error": "..."}` on any step failure. Profile must be migrated separately via `/admin/migrate-profile`.

---

## 4. DATA SCHEMAS

### profile.json (full structure)

**Location:** `DATA_DIR/profiles/profile_{user_id}.json` (per-user); legacy `DATA_DIR/profile.json` for `user_id="default"` if it exists
**Gitignored:** Yes — personal details never committed.
**Auto-created:** `load_profile()` returns `DEFAULT_PROFILE` copy if the file does not exist.
**Forward-compatible:** Missing keys are filled in from `DEFAULT_PROFILE` on load — adding new fields never breaks existing profiles.
**New users:** Redirected to `/first-post` after Clerk sign-up (`/onboarding` is a legacy redirect route); `POST /profile` creates their profile file.

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | User's name — `profile_complete` in `GET /profile` response is true only when non-empty; resolved from resume → Clerk firstName+lastName → email prefix before saving |
| `role` | str | Role/title — injected into every draft prompt |
| `bio` | str | 2–3 sentence summary of who they are and what they believe |
| `location` | str | City, country (optional) |
| `target_audience` | str | Who they write for — shapes tone and framing |
| `topics_of_expertise` | list[str] | Domains the user knows deeply |
| `voice_descriptors` | list[str] | Phrases the user naturally uses |
| `opinions` | list[str] | Strong takes the user actually holds — not facts |
| `words_to_avoid` | list[str] | Injected into humanizer prompt as banned language |
| `writing_rules` | list[str] | Style rules injected into draft and humanizer prompts |
| `writing_samples` | list[str] | Real past posts — the single most powerful signal for voice matching |
| `linkedin_style_notes` | str | Format-specific style notes for LinkedIn posts (default set in DEFAULT_PROFILE) |
| `medium_style_notes` | str | Format-specific style notes for Medium articles (default set in DEFAULT_PROFILE) |
| `thread_style_notes` | str | Format-specific style notes for threads (default set in DEFAULT_PROFILE) |

---

### ChromaDB collection
| Property | Value |
|----------|-------|
| Collection name | `contendo_{user_id}` (e.g. `contendo_default` for the default single user) |
| Distance metric | cosine |
| Embedding model | `all-MiniLM-L6-v2` (local, sentence-transformers) |
| Storage path | `backend/data/chroma_db/` |

**Metadata fields per chunk:**
| Field | Type | Description |
|-------|------|-------------|
| `source_type` | str | `article`, `youtube`, `image`, or `note` |
| `tags` | str | Comma-separated tag list |
| `source_id` | str | UUID grouping all chunks from one ingest call |
| `chunk_index` | int | Position of this chunk within its source |
| `total_chunks` | int | Total number of chunks from this source |
| `source_title` | str | First 80 chars of first line of content — used as display title in Library |
| `ingested_at` | str | UTC ISO timestamp of when the source was ingested |

---

### SQLite post history
**File:** `backend/data/posts.db`
**Owned by:** `backend/memory/feedback_store.py`
**Table:** `posts`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `created_at` | TIMESTAMP | Auto-set on insert |
| `topic` | TEXT | Topic used for generation |
| `format` | TEXT | Format type |
| `tone` | TEXT | Tone type |
| `content` | TEXT | Current best post text — updated by refinement and restore |
| `authenticity_score` | INTEGER | Score of current content (0–100) |
| `svg_diagrams` | TEXT | JSON array of `{position, description, svg_code}` objects; NULL if no diagrams |
| `archetype` | TEXT | Post archetype key inferred at generation time (e.g. `"incident_report"`); default empty string |
| `user_id` | TEXT | Clerk user ID (`sub` claim); defaults to `'default'` for rows inserted before auth was added; added via idempotent `ALTER TABLE` in `init_db()` |

**Table:** `post_versions`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `post_id` | INTEGER FK | References `posts.id`; cascade deletes |
| `version_number` | INTEGER | Monotonically increasing per post — starts at 1 for the initial generation |
| `content` | TEXT | Post text at this version |
| `authenticity_score` | INTEGER | Nullable — `null` for draft-mode generations where scorer is skipped |
| `version_type` | TEXT | `"generated"` (initial) or `"refined"` (after `/refine`) |
| `created_at` | TIMESTAMP | Auto-set on insert |
| `svg_diagrams` | TEXT | JSON array; updated in-place by `update_latest_version_svg()` when diagrams are added without a new version |

**Table:** `source_retrieval_stats`

| Column | Type | Description |
|--------|------|-------------|
| `id` | INTEGER PK | Auto-increment |
| `user_id` | TEXT | Clerk user ID |
| `source_title` | TEXT | Unique per user_id |
| `retrieval_count` | INTEGER | Times retrieved in generation |
| `last_retrieved_at` | TIMESTAMP | Last updated time |

---

## 5. KNOWN DECISIONS

| Decision | Why |
|----------|-----|
| ChromaDB uses `upsert`, never `add` | Prevents duplicate chunks if the same content is re-ingested |
| Score threshold is 75 | Defined in `pipeline/graph.py` as `SCORE_THRESHOLD = 75` |
| Humanizer retries capped at 3 (`MAX_ITERATIONS`) | Guarantees the pipeline always terminates; surfaces best attempt regardless |
| Embeddings are local (sentence-transformers) | No API key required, no per-call cost, adequate quality for retrieval |
| YouTube auto-fetch removed | `youtube-transcript-api` was blocked by YouTube bot detection in testing. Replaced with manual paste — the YouTube tab now shows a textarea with instructions to copy from YouTube's built-in transcript feature |
| Claude model selection | Draft generation and all main pipeline calls use `claude-sonnet-4-6`. Archetype inference (`infer_archetype()` in `draft_agent.py`) uses `claude-haiku-4-5-20251001` (`max_tokens=20`) for low-latency classification before the Sonnet draft call. |
| ChromaDB similarity threshold is 0.3 | Cosine similarity — chunks below this are too semantically distant to help |
| profile.json has auto-merge on load | Ensures new profile fields added in code appear without manual migration |
| CORS: production origin set via `FRONTEND_ORIGIN` env var | Starlette does NOT support glob patterns in `allow_origins` — `https://*.vercel.app` is treated as a literal string and won't match real requests. The Railway env var `FRONTEND_ORIGIN` is appended to the allow-list at startup. The list also always includes `http://localhost:3000` and `https://localhost:3000` for local dev. Never add trailing slashes to `FRONTEND_ORIGIN` or `NEXT_PUBLIC_API_URL` — trailing slash causes origin mismatches. |
| All data paths derived from `DATA_DIR` env var | `backend/config/paths.py` is the single source of truth. `DATA_DIR` defaults to `backend/data/` for local dev (identical to the previous hardcoded relative paths). On Railway, set `DATA_DIR=/data` and mount the persistent volume at `/data`. All four memory modules import from `config.paths` — no path logic elsewhere. |
| Obsidian routes guarded by `ENVIRONMENT=production` | `/obsidian/preview` and `/obsidian/ingest` return HTTP 400 when `ENVIRONMENT=production`. The frontend hides the Obsidian tab when `NEXT_PUBLIC_API_URL` does not contain `localhost` or `127.0.0.1`. This prevents meaningless/dangerous filesystem reads on a remote server. |
| `GET /health` endpoint returns `{"status": "ok"}` | Lightweight health check at the app level in `main.py`. Used by Railway's health check probe and smoke tests after deployment. |
| Backend Docker image does not pre-bake the sentence-transformers model | Model pre-loading was removed from the Dockerfile because it caused Railway build timeouts. The `all-MiniLM-L6-v2` model (~90 MB) is downloaded by `sentence-transformers` on first use and cached inside the container. Build times stay fast; only the very first embedding call (ingest or generate) on a fresh container is slow. |
| `numpy<2` pinned in requirements.txt | NumPy 2.x is incompatible with the torch version used. After multiple embedding calls, torch raises a fatal ABI mismatch error which crashes the worker process. Pinning to `numpy<2` prevents silent upgrade breakage. |
| CPU-only `torch==2.2.2` pre-installed in Dockerfile from PyTorch CPU wheel registry | The default PyTorch wheel includes CUDA libraries (~2 GB) and exceeds Railway's 4 GB image limit. Pre-installing from `https://download.pytorch.org/whl/cpu` before `requirements.txt` keeps the image under the limit. This must happen before the pip install step so the CPU wheel is not overwritten. |
| `query_similar_batch()` used in ideation agent instead of N `query_similar()` calls | The ideation agent generates 8 diversity-sampling queries. Calling `query_similar()` once per query runs 8 separate transformer forward passes (slow on CPU). `query_similar_batch()` embeds all queries in one batched forward pass then queries ChromaDB for each, cutting embedding time by ~7×. |
| Hybrid BM25 + vector retrieval via RRF | Pure vector search misses exact-term matches when a topic has low chunk density in the collection. BM25 (rank-bm25 library) provides keyword/term-frequency ranking; cosine vector search provides semantic similarity. Reciprocal Rank Fusion (k=60) merges both ranked lists into a single ranking. BM25 index is built in-memory per query from `collection.get()` — acceptable at current collection sizes. Both `query_similar_hybrid()` and `query_similar_hybrid_batch()` fall back to pure vector search on any exception so the pipeline never breaks. |
| Retrieval confidence calibration — always generate, never block | After retrieval, `_compute_retrieval_confidence()` classifies coverage as high/medium/low from raw retrieval results. Decision thresholds are equivalent to: high (3+ chunks with distance < 0.55), medium (1+ chunk < 0.55 or 3+ chunks < 0.70), low (everything else). Implementation uses the returned `similarity` key with mapped cutoffs (`> 0.45` and `> 0.30`) because vector_store returns similarity values. High confidence injects nothing into the draft prompt — identical to baseline. Medium injects an observational framing reminder. Low injects a full calibration block telling the model to write one idea well and stop — 60 to 100 words is a complete post, do not pad. The signal is internal only; the user never sees it. Generation always proceeds regardless of confidence level. |
| Inline selection editor uses a dedicated `/refine-selection` endpoint | Inline edits go through `POST /refine-selection` rather than a direct browser-to-Anthropic call because CLAUDE.md mandates all API calls go through `useApi()` from `lib/api.ts`. The endpoint loads the user's profile server-side (voice matching), calls `claude-sonnet-4-6` with `max_tokens=500`, and returns only the rewritten fragment. The frontend splices it back using `selectionStart`/`selectionEnd` offsets captured at mouseup. |
| Cluster endpoint uses tag co-occurrence as the clustering signal | Tags appearing in 2+ sources form clusters; tags unique to a single source are filtered out as noise. No ML, no embeddings — simple and fast. Near-duplicate tag merging is exact lowercase match only (no fuzzy matching) to avoid merging semantically distinct tags. |
| Profile editing via `/settings` — single-page editor, not multi-step | A stepped form makes sense for first-run onboarding; a flat scrollable page is better for incremental edits. The settings page loads all sections at once, shows a sticky save button with an amber dirty indicator, and guards against accidental navigation with `beforeunload`. The `projects` field is not shown in the UI but is loaded and preserved in every save payload so existing project data is never dropped. `voice_descriptors` is the stored field name for "Phrases you use" — the onboarding page maps `phrases_i_use` → `voice_descriptors` on save; the settings page reads and writes `voice_descriptors` directly. `technical_voice_notes` (a `list[str]` in the backend) is shown as a single textarea where each line becomes one list item. |
| SQLite used for post history | Zero-config, single-file, sufficient for one user — no PostgreSQL needed at MVP |
| Posts are auto-saved after generation | Frontend calls `POST /log-post` immediately after `POST /generate` completes. The returned `post_id` is stored in `contentOS_current_post_id` sessionStorage. Manual "Save to history" button removed. |
| feedback_store.py owns the SQLite table | `main.py` no longer contains `init_db` or `save_post` — all DB logic is in `feedback_store.py`; `init_db()` is called from the FastAPI lifespan |
| draft_node injects posted topics | `load_profile_node` fetches `get_all_topics_posted()` and stores in pipeline state; `draft_node` formats them into the prompt to prevent repeated angles |
| `source_type: "youtube"` treated identically to `"article"` in ingestion | Same chunking + embedding pipeline; only difference is the UI label |
| Diagrams generated as SVG, converted to PNG in browser | Claude returns self-contained SVG; Canvas API converts at 2x viewBox resolution for retina quality — no server-side image processing needed |
| Image placeholders are not auto-generated | `[IMAGE:]` placeholders return reminder cards so the user adds real photos or screenshots — Claude is not called for these |
| PNG exported at 2x resolution | Canvas dimensions are set to 2× the SVG viewBox width/height, parsed dynamically from the returned SVG element |
| Placeholders never auto-stripped from post textarea | `[DIAGRAM:]` and `[IMAGE:]` remain in the editable textarea — user removes them manually before copying |
| SVG diagrams saved to SQLite alongside post text | `svg_diagrams` column stores a JSON array of `{position, description, svg_code}` objects; nullable — posts without diagrams store NULL |
| Create Post session state persists in sessionStorage | Post text, score, feedback, iterations, and visuals are written to `contentOS_last_*` keys; restored on page mount; cleared on Regenerate or banner dismiss |
| Library screen groups chunks by source | `get_all_sources()` groups ChromaDB chunks by `source_id` so the user sees one card per ingested item, not raw chunk counts |
| Ideation agent uses multi-query diversity sampling | 8 queries (5 broad + 2 random tags + 1 oldest source) prevent recency bias; chunk cap raised to 30; diversity rules added to system prompt |
| Default idea count is 8 | Raised from 5 — more ideas needed to span different knowledge base topics after diversity sampling |
| Refinements update the existing history entry in place | After `/refine`, frontend calls `PATCH /history/{post_id}` with new content + score. After visuals generation, calls `PATCH` with `svg_diagrams`. No new history rows are created — one entry per generation session. |
| Scorer runs lazily for standard mode | Scorer is skipped entirely during generation for `standard` and `draft` modes — the graph routes `humanizer → finalize` directly. The analysis toggle button reads "Score this post" and calls `POST /score` on first click, then shows results. `polished` mode still runs the scorer automatically because the retry loop depends on the score. Saves one Sonnet call per standard generation for users who never open the analysis panel. Score ring, feedback, and refine section are collapsed behind the toggle; post textarea and action buttons are always visible. |
| Ideas persist in sessionStorage until dismissed | `contentOS_last_ideas` stores the ideas array on Create Post; panel is restored on mount if key exists. Panel stays open after "Use this" (idea gets a checkmark). Cleared only by explicit X dismiss, Regenerate, or restored-session dismiss. |
| Top navigation replaced with left sidebar | `AppShell` renders `Sidebar` (a 224px fixed-width left sidebar) for all app routes. The `/welcome` route bypasses AppShell entirely and renders its own top nav. The root layout no longer contains any nav elements directly. |
| Get Ideas moved to dedicated screen `/ideas` | The Get Ideas feature has its own page at `/ideas` (not just a panel on Create Post). The sidebar links to it. Ideas state (generated ideas, topic, count) is persisted in localStorage under `contendo_ideas`, `contendo_ideas_topic`, and `contendo_ideas_count` keys. |
| Saved ideas persisted in localStorage under `contendo_saved_ideas` | Users can save individual ideas for later using a "Save for later" button. Saved ideas persist across sessions in localStorage and appear in a "SAVED" subsection below the generated ideas list. |
| `contentOS_prefill_format` sessionStorage key pre-fills Create Post from Ideas screen | When the user clicks "Use this" on an idea in `/ideas`, the idea title is written to `contentOS_last_topic` and the format is written to `contentOS_prefill_format` in sessionStorage. Create Post reads both on mount and then removes `contentOS_prefill_format` to prevent stale pre-fills. |
| Post content box uses flex:1 / min-height:0 in split layout | In split-screen mode, the post textarea container is `flex: 1; min-height: 0` inside a flex column. This allows the box to fill remaining vertical space while the topic header and action row remain fixed-height rows. Without `min-height: 0`, the textarea would overflow its flex container. |
| Split-screen analysis layout breaks out of max-width container with draggable ratio | When analysis is open on wide viewports (`>= 900px`), CreatePost applies `position: fixed; left: 14rem; right: 0; top: 0; bottom: 0` to escape the parent `max-w-3xl` constraint and use the full available viewport width beside the sidebar. The left/right panes are separated by a draggable handle that updates `splitRatio` (default `0.75`, clamped to `0.35`–`0.82`); closing analysis resets ratio to `0.75`. The standard stacked layout is used on narrow viewports or when analysis is closed. |
| Landing page at `/welcome` has its own layout | `frontend/app/welcome/page.tsx` renders a complete standalone page (top nav, hero, feature cards, how-it-works section, footer) using its own inline nav — not the shared Sidebar. `AppShell` detects `pathname === "/welcome"` and renders `{children}` directly without the sidebar wrapper. |
| Welcome hero prompt bar routes into product with prefill | Submitting topic text on `/welcome` writes `contendo_topic` for continuity. Signed-in users are sent to `/create` with `contentOS_last_topic` set (consumed by `CreatePost.tsx` on mount). Signed-out users are sent to `/first-post?topic=...`; `first-post/page.tsx` hydrates the topic from query/session before showing form or auth invite. |
| Landing page is the default entry point — middleware handles auth redirects | Two active rules in `frontend/middleware.ts`: (1) unauthenticated `/` → `/welcome`; (2) all other protected routes without auth → `/sign-in` with `redirect_url`. `/welcome` remains accessible to signed-in users (no forced redirect away). The root route (`/`) itself is unchanged — it still renders Feed Memory for authenticated users. The redirect logic lives entirely in middleware so `app/page.tsx` has no auth guards. |
| Settings drawer for regeneration replaces inline form | After a post is generated, the topic/format/tone/context inputs are hidden. Clicking "Regenerate" opens a right-side drawer (`SettingsDrawer`) where the user edits settings and confirms. This keeps the post content area clean and uncluttered after generation. |
| Topic displayed above post content box after generation | In both split and stacked layouts, after generation the current topic is shown as a small `TOPIC` label + value line above the post textarea. This is display-only; topic changes go through the settings drawer. |
| Post detail page at `/history/[id]` | Individual posts have a dedicated full-page view accessible via the dynamic route `/history/[id]`. The page fetches from `GET /history`, finds the matching post by id, and renders the full content with version picker, restore, delete, and diagrams — same features as the expanded card in `/history` but with more space. |
| User can delete posts from History | `DELETE /history/{post_id}` removes the SQLite row; frontend filters the card from state without a page reload. |
| `/refine` does not run the full pipeline | Refinement is a targeted one-pass fix: `refine_draft()` + `score_text()` only. No retrieval, no draft agent, no retry loop — running the full pipeline would discard the user's manual edits |
| `score_text()` extracted from `scorer_node` | Scoring logic lives in exactly one place (`scorer_agent.py`); both the LangGraph pipeline (`scorer_node`) and the standalone `/refine` endpoint call `score_text()` internally — no duplication |
| Default generation quality is standard | Standard runs 1 critic pass + 1 humanizer pass, skips scorer during generation, and performs no retry loop. The previous polished-by-default behavior was removed to reduce latency/cost. Users can score on demand (`POST /score`) and refine manually. |
| Quality modes: draft, standard, polished | `draft` — skip critic, humanizer, and scorer entirely, return raw draft agent output. `standard` — 1 critic pass + 1 humanizer pass, scorer skipped during generation (default). `polished` — 1 critic pass, then up to 3 humanizer passes with scorer-driven retry (`score < 75`). Quality is passed in the POST /generate request body and defaults to `standard` if not provided. |
| The retry loop is preserved for polished mode only | Routing after `scorer_node` checks the `quality` field in state via `should_retry()`. For `draft` and `standard`, it returns `"finalize"` immediately. For `polished`, it falls back to the original score+iterations check. |
| File uploads use a separate `/ingest-file` endpoint | Keeps multipart form-data handling separate from the JSON `/ingest` route; avoids mixed content-type complexity in a single endpoint |
| Uploaded files are ingested as `source_type="article"` | PDF/DOCX/TXT content is plain text after extraction — same chunking and embedding pipeline applies; no need for a new source type |
| Scanned/image-only PDFs are rejected with 422 | PyMuPDF returns < 100 characters for image-only PDFs; a clear error message is returned rather than silently ingesting empty chunks |
| File drag-and-drop uses native HTML5 events only | No external DnD library added; `onDragOver`, `onDragLeave`, `onDrop` on the drop zone div are sufficient and keep the bundle small |
| Library delete removes all ChromaDB chunks with matching `source_title` | `delete_source()` does `collection.get(where={"source_title": ...})` then bulk-deletes by ID. If two sources share the same title, both are deleted — acceptable trade-off given source titles are derived from content and rarely collide. |
| Captcha/bot-protection detection uses a 2-signal threshold | `detect_captcha()` in `scraper_tool.py` checks for 2+ matches from `CAPTCHA_SIGNALS` before raising an error. A single match (e.g., an article that mentions "Cloudflare") is not flagged; 2+ matches means the page is almost certainly a bot-challenge page. |
| URL scraping uses Jina Reader, not Tavily | Jina Reader (`r.jina.ai`) is free, requires no API key, and returns clean markdown. The `scrape_url()` docstring documents the upgrade path to Tavily for higher quality if an API key is available. |
| Obsidian integration reads local `.md` files directly — no plugin or API needed | FastAPI runs locally and has filesystem access. The vault path is entered as a plain text string because browser security prevents JS from accessing local file paths. This only works on localhost — not after cloud deployment. |
| Obsidian-specific syntax is stripped before ingestion | `clean_obsidian_markdown()` removes YAML frontmatter, `[[wikilinks]]`, `^block-references`, `==highlights==` markers, `![[embedded files]]`, and Dataview query blocks. Plain text content is preserved. |
| Re-ingesting the same Obsidian vault is safe | ChromaDB uses upsert so running `/obsidian/ingest` a second time updates existing chunks rather than creating duplicates. Users can safely re-run after adding new notes. |
| Vault notes shorter than 100 characters are skipped | Set as `MIN_CONTENT_LENGTH` in `obsidian_tool.py`. Skips daily journal stubs, empty notes, and template files that contain no usable knowledge. `.obsidian`, `.trash`, `templates`, `Templates`, and `.git` folders are always excluded. |
| URL success card shows `word_count → chunks_stored` | Gives the user a concrete sense of how much was extracted before chunking — more meaningful than just a chunk count |
| Post versioning uses a parent + child table design | The `posts` table is the parent record (one row per generation session); `post_versions` stores every historical version. Every generation creates v1; every refinement creates the next version. SVG diagram updates do not create new versions — `update_latest_version_svg()` stamps diagrams onto the current version row in place. |
| Best version tracked by highest authenticity_score | `get_best_version()` orders by `authenticity_score DESC, version_number DESC` so ties go to the latest version. The History UI highlights the best version with a green "Best" badge. |
| Restore writes to sessionStorage, not a new PATCH | Restoring a version calls `POST /history/{post_id}/restore/{version_id}`, which updates the `posts` row. The frontend then writes the restored content to `contentOS_last_post` and related keys so Create Post picks it up immediately without an extra fetch. |
| Post archetypes system — 7 structural patterns inferred from topic/tone | `infer_archetype()` in `draft_agent.py` uses Claude Haiku to semantically classify the topic + context into one of 7 archetype keys (`incident_report`, `contrarian_take`, `personal_story`, `teach_me_something`, `list_that_isnt`, `prediction_bet`, `before_after`). The archetype key is stored in pipeline state, returned in the `/generate` response, and saved to the `posts` SQLite table. Structural instructions are injected into the draft prompt via `get_archetype_instructions()` in `formatters.py`. |
| `infer_archetype()` uses Claude Haiku, not regex | Haiku (`claude-haiku-4-5-20251001`, `max_tokens=20`) classifies the topic semantically — understands intent beyond keyword matching (e.g. "after 2 years" doesn't incorrectly trigger `before_after`). Fallback chain: valid key → use it; invalid/empty key → `incident_report`; any exception → `incident_report`. |
| `main.py` split into focused `APIRouter` files under `backend/routers/` | Each router owns its endpoints and imports only what it needs. `main.py` now registers 10 routers (ingest, generate, history, library, ideas, stats, profile, feedback, debug, admin) and remains focused on CORS, lifespan, and router registration. Pydantic models used by only one router live in that router file; no shared `models.py` is required. |
| ChromaDB collections namespaced per user as `contendo_{user_id}` | Data isolation is active. `vector_store.py` functions accept `user_id: str = "default"` for compatibility, while router endpoints pass authenticated IDs via `Depends(get_user_id_dep)`. `contendo_default` remains valid for local-dev fallback (`ENVIRONMENT != production` with no token). Existing data in the old `"contendo"` collection is not auto-migrated; re-ingestion or migration is required. |
| Chunks prefixed with `[source_type: X]` before reaching draft agent | `retrieval_node` prepends `[source_type: article]`, `[source_type: note]`, `[source_type: youtube]`, or `[source_type: image]` to each chunk string. Preserves attribution metadata without changing the `list[str]` schema of `retrieved_chunks` in `PipelineState`. The draft agent's SOURCE ATTRIBUTION RULES use this label to distinguish content the user personally wrote (notes — attributable to direct experience) from content they read or watched (articles, youtube, images — must be framed as external references, never as first-person claims). Prevents the fabrication of personal experiences by combining the user's employer/role from their profile with technical details from external chunks. Missing or `"unknown"` source_type defaults to `"article"` as the safe assumption. |
| Critic agent runs once per generation, not per retry iteration | The retry loop in polished mode routes back to `humanizer_node` only. Re-running the critic on each iteration would add a Haiku call per retry pass and is redundant — the critic already diagnosed the initial draft's structural issues; subsequent humanizer passes are language refinements on an already-diagnosed foundation. The critic brief from iteration 1 remains in state for all retry passes. |
| Critic agent receives all retrieved chunks, not a subset | `critic_node` passes all `retrieved_chunks` to the prompt — no slicing. This matches exactly what `draft_agent` received, so the critic can accurately assess whether claims in the draft are grounded. Passing only a subset (e.g. the first 5) risked false "substance: needs_work" verdicts for claims that were actually supported by chunks the critic was never shown. |
| Critic agent uses Haiku, not Sonnet | Diagnosis is pattern recognition (is the hook weak? are there vague claims?), not creative generation. Haiku is fast and cheap for classification tasks. Sonnet is reserved for the humanizer where creative rewriting quality matters. |
| Critic brief fallback is a neutral brief, not an exception | If the Haiku call fails or JSON parsing fails after 3 attempts, `critic_node` sets `critic_brief=_NEUTRAL_BRIEF` (all "strong") or `{}` depending on failure type. This ensures the humanizer always receives a safe input — the pipeline never breaks due to a failed critic call. |
| Critic brief is `{}` for draft mode, neutral dict for standard/polished parse failure | An empty dict `{}` from draft-mode bypass means "critic was skipped intentionally." `_format_critic_brief({})` returns empty critic_section — humanizer behaves as pre-critic for backward compat. |
| Anthropic client is instantiated at module level in each agent file | Client is created once at import time and reused across all calls — not re-instantiated on every function invocation. `max_retries=3` enables the SDK's built-in retry logic for 429 rate limit errors and transient network failures at no extra code cost. No shared `llm_client.py` — module-level per file is sufficient at current codebase size. Applies to all 7 agent files: `draft_agent.py`, `humanizer_agent.py`, `scorer_agent.py`, `ingestion_agent.py`, `vision_agent.py`, `visual_agent.py`, `ideation_agent.py`. |
| Ingestion deduplication uses SHA-256 hash of normalised content | `compute_content_hash()` in `ingestion_agent.py` strips and lowercases the content string before hashing. On every `ingest_content()` call, `query_by_hash()` checks for an existing match in ChromaDB metadata before the Claude tag extraction call runs. Duplicate content returns immediately with the existing chunk count and tags — zero Claude API calls. The hash is stored in each chunk's `content_hash` metadata field so future checks can find it. Content ingested before this feature was added has no `content_hash` in metadata and will not be deduplicated retroactively. Obsidian vault ingest (`/obsidian/ingest`) is excluded — its upsert-based flow already handles re-ingestion safely. |

---

| `/first-post` is a standalone conversion-focused route with full generation completion | The flow now does real work, not just a placeholder: it saves a minimal profile first, generates the first draft, auto-logs to history, and shows an in-page draft review screen with copy + workspace navigation. This closes the first-run loop without dropping users into an empty workspace. |
| Clerk JWT auth via PyJWT + JWKS | `auth/clerk.py` fetches Clerk's JWKS from `https://api.clerk.com/v1/jwks` (cached 1hr in memory); uses `RSAAlgorithm.from_jwk()` to select the signing key by `kid` header; decodes with `jwt.decode(..., algorithms=["RS256"])`. `CLERK_SECRET_KEY` is required for the JWKS endpoint. Any exception → 401. |
| Dev fallback to `user_id="default"` | When `ENVIRONMENT != "production"` and no Authorization header is present, `get_user_id()` returns `"default"` instead of raising 401. This preserves full local dev convenience — no token needed. Production always requires a valid token. |
| Per-user profile files at `DATA_DIR/profiles/profile_{user_id}.json` | Separates profiles per Clerk `sub` claim. The `"default"` user still falls back to `DATA_DIR/profile.json` if it exists (backward compat for existing local dev data). `PROFILES_DIR` is exposed from `config/paths.py`. |
| SQLite `ALTER TABLE posts ADD COLUMN user_id` migration is idempotent | Wrapped in try/except in `init_db()`. First deploy after this change adds the column; subsequent deploys silently pass the `except`. Existing rows default to `user_id='default'` (SQLite `DEFAULT 'default'`). No manual migration needed. |
| All existing rows in posts.db get `user_id='default'` | Railway production: the first deploy after this branch merges runs `init_db()` which adds the column. All pre-existing post history is attributed to `"default"`. If that user later creates a Clerk account, they will not see their old posts (different user_id). Acceptable for MVP. |
| Onboarding redirect via `useProfileCheck` in AppShell | After Clerk confirms auth, AppShell calls `GET /profile`. Only redirects to `/first-post` when `has_profile === false` (file does not exist). `has_profile: true` with empty name (`profile_complete: false`) is a returning user with a thin profile — they are allowed into the workspace without redirect. Public routes skip the check. |
| `contendo_intercept_done` localStorage key | Set to `"1"` by `OnboardingIntercept` on completion (or full skip). Checked by (1) `handleCTA()` in `first-post/page.tsx` — if absent, intercept is shown before navigating to the workspace; (2) `AppShell.tsx` safety net — if absent after `has_profile === true`, intercept is shown before rendering workspace children. Once set, both checks pass through immediately. Never expires — deliberately permanent per device. |
| In the `/first-post` flow, profile is saved before generation | Saving the profile first makes `has_profile` true immediately. If generation fails afterward, the user is still treated as a known user and can enter the workspace without getting trapped in first-run redirects. |
| The `/first-post` draft is written to sessionStorage before navigating to `/create` | `contentOS_last_post` and related keys are written by first-post CTA buttons; `CreatePost.tsx` already restores these keys on mount, so no additional CreatePost wiring is needed for preloaded draft handoff. |
| New-user routing via `useProfileCheck` | After Clerk confirms auth, AppShell calls `GET /profile`. Only `has_profile === false` triggers a redirect to `/first-post`. A returning user whose profile file exists but has an empty name (`profile_complete: false`) is not redirected — they can access the workspace. |
| `/onboarding` kept as backward-compat redirect | The old 5-step flow at `/onboarding` is no longer the new-user entry point. The page immediately calls `router.replace('/first-post')` on mount so any bookmarked or hardcoded links still work. The route stays in middleware's public list. `/first-post` is the canonical new-user experience. |
| In the `/first-post` flow, profile is saved before generation | Saving the profile first makes `has_profile` true immediately. If generation fails afterward, the user is still treated as a known user and can enter the workspace without getting trapped in first-run redirects. |
| The `/first-post` draft is written to sessionStorage before navigating to `/create` | `contentOS_last_post` and related keys are written by first-post CTA buttons; `CreatePost.tsx` already restores these keys on mount, so no additional CreatePost wiring is needed for preloaded draft handoff. |
| Frontend API layer via `useApi()` hook in `lib/api.ts` | Centralises all backend calls in one hook. `useAuth().getToken()` is called per-request to always attach a fresh token (Clerk tokens are short-lived). Components call `const api = useApi()` instead of raw `fetch()`. All request/response types are exported from `lib/api.ts` for IDE completions. |
| Em dashes and decorative hyphens banned in humanizer and refine prompts | Em dashes are one of the strongest signals of AI-generated text. Both `SYSTEM_PROMPT` and `REFINE_PROMPT` in `humanizer_agent.py` explicitly ban the em dash character (—) and decorative hyphenated compound modifiers (e.g. 'data-driven', 'production-ready'). The ban rule appears in the "AI writing patterns to eliminate" list and as a standalone line immediately after `{words_to_avoid}` in both prompts. Applies to both main generation and refinement flows. |
| Fabrication rule added to draft agent SOURCE ATTRIBUTION RULES | Prevents invention of personal incidents, named colleagues, specific timestamps, and events not present in ingested notes or user profile. Added as a `FABRICATION RULE` block in `SYSTEM_PROMPT` of `draft_agent.py`, immediately after the existing attribution rules. User publishes under their own name; a fabricated incident is a factual error they cannot take back. |

---

## 6. WHAT IS NOT BUILT YET

- Obsidian integration does not work after cloud deployment — vault path is a local filesystem path read by FastAPI. Guarded by `ENVIRONMENT=production` (returns HTTP 400) and hidden in the frontend when API URL is not localhost. Future full solution: vault zip upload or Electron desktop wrapper.

- Vercel and Railway/Render deployment config files
- YouTube transcript auto-fetching (removed — manual paste only)
- Tag filtering in Library (can't filter ChromaDB chunks by tag in the UI — only source-type filter exists)
- Bulk clear memory (individual sources can be deleted via the Library delete button, but there is no "clear all" option)
- Multi-format regeneration (regenerate always uses same format/tone)
