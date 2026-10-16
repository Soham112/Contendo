# Contendo: as-is architecture inventory

Snapshot of the repository at commit `24ceec4` (branch `main`, 2026-10-10). Read-only research: no code was changed, no database was queried, no external API was called, and no `.env` file was read. The project's permission rules also block `backend/.env.example` and `frontend/.env*` (`.claude/settings.json:6-10`), so environment variable names below come from code only.

How to read this document:

- Every statement carries the `file:line` it comes from. Paths are relative to the repository root.
- **[V]** means verified in code: the cited lines do what the statement says.
- **[I]** means inferred: the statement reads intent, or combines verified facts into a conclusion that could only be confirmed by running the system or looking at the live database.
- Sections 1 to 15 state facts only. Inconsistencies, dead code and duplication are in sections 13 and 15, also stated as facts. Nothing here proposes a fix or a target design.

---

## Summary

### Components

| # | Component | Where |
|---|---|---|
| 1 | Web frontend (Next.js 14 App Router) | `frontend/` |
| 2 | Chrome extension | `extension/` |
| 3 | Backend API (FastAPI, one uvicorn worker) | `backend/main.py`, `backend/routers/` |
| 4 | Auth | Supabase Auth; `backend/auth/supabase_jwt.py`, `frontend/middleware.ts` |
| 5 | Ingest pipeline | `backend/agents/ingestion_agent.py`, `backend/tools/`, `backend/utils/chunker.py` |
| 6 | Memory stores (Supabase Postgres + pgvector) | `backend/memory/`, `backend/migrations/` |
| 7 | Retrieval | `backend/agents/retrieval_agent.py`, `backend/memory/vector_store.py` |
| 8 | Generation pipeline (LangGraph, five variants) | `backend/pipeline/`, `backend/agents/` |
| 9 | LLM client, model table, price table | `backend/llm/` |
| 10 | Side model calls (refine, score, visuals, ideas, resume) | `backend/agents/`, `backend/routers/profile.py` |
| 11 | Observability (usage events, user events, generation traces) | `backend/memory/usage_store.py`, `backend/routers/analytics.py`, `backend/pipeline/trace.py` |
| 12 | Offline evals | `evals/` |
| 13 | Deployment | Vercel (frontend), Railway Docker (backend), two Supabase projects |

**1. Web frontend.** A Next.js 14 app whose pages are client components that call the backend through one hook, `useApi()`, which attaches the Supabase access token as a Bearer header (`frontend/lib/api.ts:169-185`) [V]. Signed-in pages render inside `AppShell`, which logs a page view, checks whether the user has a profile row and sends users without one to `/first-post` (`frontend/components/AppShell.tsx:12-23`, `frontend/hooks/useProfileCheck.ts:66-77`) [V]. The sidebar links to Create Post, Feed Memory, Get Ideas, Library, History and Settings (`frontend/components/Sidebar.tsx:23-73`) [V].

**2. Chrome extension.** A Manifest V3 extension that saves the current page or YouTube video to the user's memory by calling the production backend directly (`extension/manifest.json:7-10`, `extension/background.js:16,51,89,119`) [V]. The web app pushes the Supabase access token to it on load (`frontend/hooks/useProfileCheck.ts:36-46`) [V].

**3. Backend API.** FastAPI with ten routers registered in `backend/main.py:89-98` and one public route, `GET /health` (`backend/main.py:101-103`) [V]. Slow work (Claude calls, ingestion) runs in a thread pool via `run_in_threadpool`; the container starts a single uvicorn process (`backend/Dockerfile:41`) [V].

**4. Auth.** Supabase Auth with Google OAuth and email/password (`frontend/app/sign-in/[[...sign-in]]/page.tsx:26-39`) [V]. The backend verifies the JWT with HS256 against `SUPABASE_JWT_SECRET`, then ES256 against the project's JWKS, and returns the `sub` claim as `user_id` (`backend/auth/supabase_jwt.py:80-130`) [V]. The backend talks to Postgres with the service-role key (`backend/db/supabase_client.py:7-10`) [V]; every table has row-level security enabled (`backend/migrations/000_baseline_schema.sql:706-778`) [V].

**5. Ingest pipeline.** Every input type ends in one function, `ingest_content()`, which chunks text (500 words, 50 overlap), de-duplicates by content hash, tags it (Sonnet), assigns a `memory_context`, embeds and stores the chunks, extracts entities per chunk (Haiku), writes "Consolidated knowledge" summaries for entities seen in three or more sources (Haiku), and writes a source summary and topic node (Haiku) (`backend/agents/ingestion_agent.py:320-439`) [V].

**6. Memory stores.** Everything lives in Supabase Postgres: chunks and vectors in `embeddings` (pgvector, 384 dimensions), plus `profiles`, `posts`, `post_versions`, `entities`, `chunk_entities`, `experience_nodes`, `source_nodes`, `topic_nodes`, `source_retrieval_stats`, `usage_events`, `user_events` and `generation_traces` (`backend/migrations/000_baseline_schema.sql:72-385`) [V]. One exception: feedback messages are appended to a file on local disk (`backend/routers/feedback.py:59-61`) [V].

**7. Retrieval.** One query string (`topic. context`) is embedded locally and searched two ways in parallel: pgvector cosine and an in-memory BM25 index over the user's whole corpus; the two rankings are fused with Reciprocal Rank Fusion, filtered by per-chunk thresholds, and topped up with entity-linked chunks (`backend/agents/retrieval_agent.py:321-348`, `backend/memory/vector_store.py:465-511`) [V]. A coverage gate stops generation before drafting when the best scores are too low (`backend/agents/retrieval_agent.py:55-95`) [V].

**8. Generation pipeline.** A LangGraph graph with a shared head (`load_profile → retrieval → plan`) and one of three tails chosen by variant: A (draft → critic → humanizer → audit → enforcer → fact check), B (draft → checks → review → fixes), C (draft → checks → optional compress) (`backend/pipeline/graph.py:175-203`) [V]. The default is `C-Opus`: graph C with Claude Opus 5.5 as the drafter (`backend/config/features.py:33-34`, `backend/llm/models.py:71-74`) [V].

**9. LLM client.** Every Claude call goes through `complete()` or `complete_structured()`, which validate the model id, call the API with three SDK retries, log a usage event and append to the active trace (`backend/llm/client.py:72-75,103-166`) [V]. Model ids live in `backend/llm/models.py:14-18` and prices in `backend/llm/pricing.py:28-34` [V].

**10. Side model calls.** Outside the pipeline: selection refine, on-demand scoring, diagram generation and refinement, idea suggestions, resume extraction, image-to-text, and the memory-context classifier (sections 2 and 8).

**11. Observability.** Three record types: one `usage_events` row per Claude call with tokens, cost and model; one `user_events` row per frontend tracking event; one `generation_traces` row per pipeline run with inputs, retrieved chunks, every draft, checks and per-call token counts (sections 9 and 10).

**12. Offline evals.** Scripts that run the real pipeline against a separate Supabase project with three fictional personas and 27 goldens, judge the results with DeepEval metrics through Claude, and produce reports, a judge audit and a blind read (`evals/README.md:1-6`, `evals/goldens/goldens.jsonl`) [V].

**13. Deployment.** Frontend on Vercel, backend on Railway from `backend/Dockerfile`, data in Supabase. There is no CI configuration in the repository; two opt-in git hooks scan for secrets and run pytest (`scripts/git-hooks/pre-commit`, `scripts/git-hooks/pre-push`) [V].

### How a post gets from user input to the screen (production default, C-Opus)

```
Browser: /create (frontend/components/CreatePost.tsx)
  user types topic, picks format / tone / length, optional context
  │  POST /generate  {topic, format, tone, length, context, no_specifics:false}
  │  Authorization: Bearer <Supabase access token>
  ▼
FastAPI: routers/generate.py:156  ── get_user_id_dep verifies the JWT ──► user_id
  │  run_in_threadpool(run_pipeline)
  ▼
pipeline/graph.py:212 run_pipeline  (variant = PIPELINE_VARIANT or "C-Opus")
  │
  ├─ load_profile     profiles.data + all topics from posts          (no model)
  │                   first_post = user has no posts
  ├─ retrieval        embed query locally (MiniLM, 384-d)
  │                   ├─ pgvector cosine top 8  (RPC match_embeddings)
  │                   └─ BM25 top 8 over the user's whole corpus (in memory)
  │                   RRF fuse → keep chunks with cosine ≥ 0.30 or BM25 ≥ 0.30
  │                   + up to 4 entity-linked chunks
  │                   coverage gate ──► "low_coverage": stop, return closest sources
  ├─ plan             length target + perspective                    (no model)
  ├─ structure        pick archetype from the allowed set     (Haiku 4.5, tool call)
  ├─ draft            one call: sources block S1..Sn, voice profile,
  │                   structure, style + citation rules        (Opus 5.5, effort medium)
  │                   ──► truncated / refused / empty: stop, return no post
  ├─ strip            read <event> and <post>, drop anything else    (code)
  ├─ finalise         normalise em dashes, remove [[S1]] markers,
  │                   measure length                                 (code)
  ├─ checks           nine deterministic checks, recorded only       (code)
  └─ if over max words:
       compress       shorter replacements per sentence        (Opus 5.5)
       finalise → recheck                                            (code)
  │
  ├─ insert generation_traces row  ──► trace_id
  ▼
Response {status, post, score:0, scored:false, archetype, trace_id, ...}
  ▼
Browser: strips [DIAGRAM:]/[IMAGE:] placeholders, shows the post in the editor
  │  POST /log-post {topic, format, tone, content, authenticity_score, trace_id}
  ▼
posts row + post_versions row (version 1, "generated"); trace linked to the post
```

Sources for the diagram: `frontend/components/CreatePost.tsx:1107-1141`, `backend/routers/generate.py:156-207`, `backend/pipeline/graph.py:182-339`, `backend/pipeline/single_writer.py:54-75`, `backend/agents/retrieval_agent.py:321-399`, `backend/routers/history.py:65-96` [V].

---

## 1. Product surface

### 1.1 Routes

All files are under `frontend/app/`. "Public" means listed in `PUBLIC_PATHS` (`frontend/middleware.ts:4-14`); every other path redirects to `/sign-in?redirect_url=…` when there is no session (`frontend/middleware.ts:58-63`) [V].

| Route | File | Public | What the user can do |
|---|---|---|---|
| `/` | `page.tsx:1` | yes | Re-exports the welcome page [V] |
| `/welcome` | `welcome/page.tsx` | yes | Marketing page. Primary button goes to `/create` when signed in, else `/first-post` (`welcome/page.tsx:103-108`) [V] |
| `/about` | `about/page.tsx` | yes | Static page with a link to `/sign-up` (`about/page.tsx:68`) [V] |
| `/sign-in` | `sign-in/[[...sign-in]]/page.tsx` | yes | Google OAuth or email + password; a signed-in visitor is pushed to `/create` (`:15-16,26-44`) [V] |
| `/sign-up` | `sign-up/[[...sign-up]]/page.tsx` | yes | Google OAuth or email sign-up with an email redirect (`:20-40`) [V] |
| `/auth/callback` | `auth/callback/route.ts` | yes | Exchanges the OAuth code for a session, then redirects to the validated `next` path (`:10,33,40`) [V] |
| `/sso-callback` | `sso-callback/page.tsx` | yes | Legacy Clerk target; redirects to `/sign-in` (`:11-13`) [V] |
| `/onboarding` | `onboarding/page.tsx` | yes | Redirects to `/first-post` immediately (`:82-84`); the form code below the redirect remains in the file (`:90-142`) [V] |
| `/first-post` | `first-post/page.tsx` | yes | Six-screen onboarding that saves a profile and generates the first post (section 1.3) |
| `/create` | `create/page.tsx` → `components/CreatePost.tsx` | no | Generate, edit, refine, score, visuals, ideas panel (section 1.5) |
| `/feed-memory` | `feed-memory/page.tsx` → `components/FeedMemory.tsx` | no | Add memory from seven tabs (section 1.4) |
| `/ideas` | `ideas/page.tsx` | no | Request 3, 5 or 10 ideas, optionally on a topic; save ideas in `localStorage`; send one to `/create` (`:8-11,199,247-250,256`) [V] |
| `/library` | `library/page.tsx` | no | List sources with chunk count, tags and "used N times"; filter, sort, grid/list; topic map view; delete a source (`:134,220-229,546-576,611`) [V] |
| `/history` | `history/page.tsx` | no | Last 20 posts with versions; copy; open in editor; restore a version; delete; mark as published on LinkedIn / X / Medium / Other (`:180-190,199-237,528-533,647`) [V] |
| `/history/[id]` | `history/[id]/page.tsx` | no | One post: same actions as a history card (`:212-272`) [V] |
| `/settings` | `settings/page.tsx` | no | Cards for profile, voice, writing samples, memory stats, account (sign out), usage and tokens, integrations (`:171,225,270,316,349,404,464`) [V] |
| `/settings/profile` | `settings/profile/page.tsx` | no | Edit every profile field (`:343-426`) and save (`:231`) [V] |
| `/admin` | `admin/page.tsx` | no | Usage dashboard: calls, estimated cost, 14-day chart, users by cost (`:210,231-265`) [V] |
| `/admin/analytics` | `admin/analytics/page.tsx` | no | User-event dashboard over 7, 14, 30 or 90 days (`:210,285-292`) [V] |

The welcome page links to `/careers`, `/pricing`, `/privacy-policy` and `/terms-of-service` (`frontend/app/welcome/page.tsx:48,54,745,752`); no such route files exist under `frontend/app/` [V].

### 1.2 Sign-up and routing after sign-in

1. Sign-in or sign-up redirects through `/auth/callback?next=<path>`; the path is validated by `safeRedirectPath()` and defaults to `/create` (`frontend/lib/safe-redirect.ts:6,16-34`, `frontend/app/auth/callback/route.ts:10`) [V].
2. On any page that renders the app shell, `useProfileCheck` calls `GET /profile`; when `has_profile` is false it pushes `/first-post` (`frontend/hooks/useProfileCheck.ts:66-77`) [V]. `has_profile` is true when a `profiles` row exists for the user (`backend/routers/profile.py:23`, `backend/memory/profile_store.py:67-78`) [V].
3. A signed-in user with a profile who opens `/first-post` is sent to `/` (`frontend/app/first-post/page.tsx:956-963`) [V].
4. A user who has a profile but no `contendo_intercept_done` flag in `localStorage` sees the `OnboardingIntercept` overlay on any shell page (`frontend/components/AppShell.tsx:29-32,85-90`) [V].

### 1.3 First post (onboarding)

Entry: `/first-post`, optionally with `?topic=` or a topic stored in `sessionStorage` under `contendo_topic` (`frontend/app/first-post/page.tsx:56,926-940`) [V]. A signed-out visitor sees an auth screen (Google, or a link to email sign-in) that returns to `/first-post` with the topic (`:790-812,1300-1308`) [V].

| Screen | Asks | Source |
|---|---|---|
| 0 | Topic (at least 10 characters) and format | `:1326`, `:977` |
| 1 | Role, from nine fixed options | `:1377`, `frontend/lib/first-post-constants.ts:19-29` |
| 2 | Experience type, from five fixed options, plus a free-text detail | `:1452`, `first-post-constants.ts:85-111` |
| 3 | One of five opinion statements for the role's bucket, or a custom one | `:1523`, `first-post-constants.ts:47-76` |
| 4 | Audience pills and an optional voice sample | `:1611-1675` |
| 5 | Optional resume upload (PDF) or "Skip for now" | `:1686`, `:198`, `:1787-1795` |

On "Generate" (`frontend/app/first-post/page.tsx:1079-1166`) [V]:

1. If a resume was chosen: `POST /extract-resume`, then `POST /save-experience-nodes` in the background with no confirmation step (`:1014-1024`).
2. A profile is built by `buildMergedProfile` and saved with `POST /profile` (`:1040-1076,1098`). `role` is the chosen role label; `bio` is the experience detail typed on screen 2, else the resume's bio (`:1048-1049`); `opinions` is the chosen opinion plus the resume's; `writing_samples` is the voice sample plus the resume's; `words_to_avoid`, `writing_rules` and the three style-notes fields are saved empty (`:1064-1074`).
3. `POST /generate` with `tone: "casual"`, the chosen format, and a `context` built from experience type, detail, opinion and audience (`:291-306,1113-1118`). No `length` or `quality` is sent.
4. `POST /log-post` with the returned `trace_id` (`:1144-1153`).
5. The draft screen offers copy and two buttons. If the resume was skipped, a `ProfileGate` step offers it again; otherwise the `OnboardingIntercept` questions run if not done (`:1200-1213`). Both buttons end in `router.push(destination === 'feed' ? '/' : '/create')` (`:1211,1237,1243`) [V].

`OnboardingIntercept` asks chip questions and merges the answers into `voice_descriptors`, `target_audience` and `writing_rules` before saving the profile and setting `contendo_intercept_done` (`frontend/components/OnboardingIntercept.tsx:10,35-53,114-148`) [V].

What the backend does differently for a first post is in section 6.6.

### 1.4 Adding memory

Seven tabs in `frontend/components/FeedMemory.tsx:18-57` [V]. A first-visit tour runs once per browser (`:228-276`) [V].

| Tab | Request | `source_type` stored | Title | `memory_context` |
|---|---|---|---|---|
| Article (pasted text) | `POST /ingest` `{content, source_type:"article", memory_context}` (`FeedMemory.tsx:591-615`) | `article` | first line, cut at 80 characters (`ingestion_agent.py:370-373`) | pill value, else inferred |
| URL | `POST /scrape-and-ingest` (`:589`) | `article` (`routers/ingest.py:253`) | first `# ` heading of the scraped markdown, else the URL (`tools/scraper_tool.py:129-133`) | always inferred |
| File (PDF, DOCX, TXT; 10 MB) | `POST /ingest-file` (`:587`, `:1019`) | `article` (`routers/ingest.py:229`) | first sentence or line of the text, else the filename stem (`routers/ingest.py:109-131`) | always inferred |
| YouTube | `POST /fetch-youtube-transcript`, then `POST /ingest` with `source_type:"youtube"` and the video title; or a pasted transcript (`:598-612`) | `youtube` | video title from Supadata (`routers/ingest.py:313`) | pill value, else inferred |
| Image (PNG, JPEG, WebP) | `POST /ingest` with `raw_image` (`:596`, `:975`) | `image` | first line of the extracted text | always inferred: the endpoint does not pass `memory_context` or `source_title` for images (`routers/ingest.py:152`) [V] |
| Note | `POST /ingest` `{source_type:"note"}` | `personal_note` when the pill is work or personal project; `saved_content` when learning or observation; `note` with no pill (`routers/ingest.py:161-171`) [V] | first line | pill value, else inferred |
| Obsidian (zip; local path only when the API URL is localhost) | `POST /obsidian/preview-zip`, `POST /obsidian/ingest-zip` (`:486,511`); local: `/obsidian/preview`, `/obsidian/ingest` (`:435,459`) | `note` (`routers/ingest.py:349,433`) | note filename | always inferred |

- The four pills are Work, Personal project, Learning and Observation (`FeedMemory.tsx:1100-1103`) [V]. When text of 30 or more characters loses focus and no pill is chosen, the page calls `POST /suggest-memory-context` and pre-selects the answer (`:315-327`) [V].
- A duplicate returns a toast "This source is already in memory" and logs `feature_abandon` (`:625-639`) [V].
- Profile fields are a second input path: see section 5. Publishing a post with pasted "published content" appends that text to the profile's writing samples (`backend/routers/history.py:164-165`) [V]. That text is not ingested into `embeddings`.
- The Chrome extension is a third path: `scrapeAndIngest` for a page, and transcript fetch plus `/ingest` for YouTube (`extension/background.js:32-45,51,89,119`) [V]. It sends `title` and `url` fields (`extension/background.js:129`), which `IngestRequest` does not declare (`backend/routers/ingest.py:48-54`) [V].

### 1.5 Creating a post

Options on `/create` (`frontend/components/CreatePost.tsx`) [V]:

| Option | Values | Source |
|---|---|---|
| Topic | free text, required | `:1084-1087` |
| Format | LinkedIn Post, Medium Article, Thread | `:33-37` |
| Tone | Casual, Technical, Storytelling | `:39-43` |
| Length | Concise, Standard, Long-form | `:57-61` |
| Additional context | free text | `:633`, `:1108` |
| Quality | not offered: the request body has no `quality` field | `:1107-1110` |
| Opinion post without specifics | offered only inside the low-coverage notice, and only when the backend flag is on | `:2576-2586`, `frontend/components/LowCoverageNotice.tsx:71-108` |

Flow:

1. `generate()` clears the session, calls `POST /generate` and reads the response with `generateOutcome()` (`CreatePost.tsx:1073-1141`, `frontend/lib/generate-outcome.ts:39-51`) [V].
2. `low_coverage`: the notice lists the closest sources and offers "Add a source" (`LowCoverageNotice.tsx:53-63`) [V]. `draft_truncated`, `draft_refused`, `draft_empty` or an empty post: the message is shown as an error and nothing is saved (`CreatePost.tsx:1125-1130`) [V].
3. A post: placeholders `[DIAGRAM: …]` and `[IMAGE: …]` are stripped for display, the raw post is kept for visuals, and the post is auto-saved with `POST /log-post` carrying `trace_id` (`:1132-1141,996-1020`) [V].
4. Toolbar: Regenerate (a drawer where topic, format, tone, length and context can all be changed, `:522-661,1639`), Analyse (`POST /score`, `:1042-1069`), Generate visuals (`POST /generate-visuals`, `:1277`), Copy for LinkedIn and Copy for Medium (`:1246-1257`), Start over (`:1909`) [V].
5. Diagrams can be refined with an instruction (`POST /refine-visual`, `:287`), and are rendered through `DiagramView` as an `<img>` data URI (`frontend/components/DiagramView.tsx:36-41`) [V].
6. An ideas panel calls `GET /suggestions` (`:1332`) [V].
7. State is kept in `sessionStorage` under `contentOS_*` keys; on return, an interstitial asks whether to continue the saved post (`:13-26,776-821,2334`) [V].

### 1.6 Selection refine

Selecting text in the editor opens an inline input. Submitting calls `POST /refine-selection` with the selection, the instruction, the full post, the current `trace_id` and the post id (`CreatePost.tsx:1172-1187`) [V]. On `status: "reverted"` a toast shows the message and nothing changes (`:1188-1191`). Otherwise the selection is replaced by offset, the post is patched with `PATCH /history/{id}` (which adds a "refined" version), and any `note` is shown as a toast (`:1193-1207`) [V]. Backend behaviour is in section 8.1.

### 1.7 History and editing

- `GET /history` returns the 20 most recent posts with all their versions (`backend/routers/history.py:48-62`) [V].
- "Open in editor" writes the post into the `contentOS_*` session keys and navigates to `/create` (`frontend/app/history/page.tsx:180-190`) [V]. No `trace_id` is stored for it; refine then relies on `post_id` (`CreatePost.tsx:1178-1186`, `backend/memory/trace_store.py:33-44`) [V].
- Restore sets the post's content and score to a chosen version's (`backend/routers/history.py:169-190`) [V].
- "Mark as published" stores the platform, timestamp and optional pasted content (`backend/routers/history.py:150-166`) [V].

### 1.8 Admin pages

Both admin pages ask `GET /admin/me` and redirect non-admins to `/` (`frontend/lib/useIsAdmin.ts:19-25`, `frontend/app/admin/page.tsx:198-203`, `frontend/app/admin/analytics/page.tsx:195-203`) [V]. The sidebar shows admin links only when that call says so (`frontend/components/Sidebar.tsx:87,144`) [V]. The backend enforces access itself with `require_admin` (`backend/auth/supabase_jwt.py:144-149`) [V].

---

## 2. Backend API

Auth column: **user** = `Depends(get_user_id_dep)`; **admin** = `Depends(require_admin)`; **none** = public. A missing or invalid token returns 401 unless `ALLOW_DEV_AUTH=1` (`backend/auth/supabase_jwt.py:64-77`) [V]. `backend/tests/test_endpoint_auth_coverage.py:11-19` lists `/health` as the only public route and an empty `KNOWN_UNPROTECTED` [V].

### 2.1 Generation (`backend/routers/generate.py`)

| Method, path | Auth | Request | Response | Calls |
|---|---|---|---|---|
| `POST /generate` (`:156`) | user | `topic`, `format`, `tone`, `length="standard"`, `context=""`, `quality="standard"`, `no_specifics=false` (`:29-37`) | `status`, `message`, `post`, `score`, `score_feedback`, `iterations`, `archetype`, `scored`, `retrieval_confidence`, `trace_id`, `closest_sources[]`, `suggestion`, `no_specifics_enabled`, `review` (`:69-92`) | `run_pipeline` in a thread pool (`:172-182`); then the log-only fact check as a background task when the result carries one (`:189-190`) |
| `POST /refine-selection` (`:210`) | user | `selected_text`, `instruction` (max 2,000 chars), `full_post` (max 30,000), `trace_id?`, `post_id?` (`:25-26,106-113`) | `rewritten_text`, `status` (`ok`/`reverted`), `message`, `note`, `sources_used`, `sources_message` (`:116-125`); 409 `refine_sources_missing` when the post has no usable trace (`:242-246`) | `agents.refine_agent.refine_selection` |
| `POST /score` (`:256`) | user | `post_content` | `score` (int or null), `score_feedback[]`, `message` | `agents.scorer_agent.score_text` |
| `POST /generate-visuals` (`:274`) | user | `post_content` | `{visuals: [{type, placeholder, description, position, svg_code, reminder_text}]}` | `agents.visual_agent.generate_visuals` |
| `POST /refine-visual` (`:290`) | user | `svg_code`, `refinement_instruction`, `original_description`, `style_hint?` | `{svg_code}` | `agents.visual_agent.generate_svg_for_diagram` |

`POST /generate` returns 400 for an empty topic or for `no_specifics=true` while the flag is off (`:162-169`); Anthropic overload becomes 503, every other failure a generic 500 (`:139-153`) [V].

### 2.2 Ingest (`backend/routers/ingest.py`)

| Method, path | Auth | Request | Response | Calls |
|---|---|---|---|---|
| `POST /ingest` (`:134`) | user | `content`, `source_type`, `raw_image?`, `content_origin?`, `source_title?`, `memory_context?` (`:48-54`) | `chunks_stored`, `tags[]`, `duplicate`, `message` | image: `extract_from_image` then `ingest_content`; otherwise `ingest_content` |
| `POST /suggest-memory-context` (`:191`) | user | `content` | `{suggested_context}` | experience cross-reference, else Haiku classifier (`:206-208`) |
| `POST /ingest-file` (`:212`) | user | multipart `file` (max 10 MB; `.pdf`, `.docx`, `.txt`) | as `/ingest` | `extract_text_from_file`, `ingest_content` |
| `POST /scrape-and-ingest` (`:241`) | user | `url` | `chunks_stored`, `tags`, `title`, `word_count`, optional `duplicate`, `message` | `scrape_url` (Jina Reader), `ingest_content` |
| `POST /fetch-youtube-transcript` (`:274`) | user | `url` | `transcript`, `video_id`, `title`; 503 when `SUPADATA_API_KEY` is unset | Supadata REST API (`:294-299`); nothing is ingested |
| `POST /obsidian/preview` (`:317`) | user | `vault_path` | vault stats; 403 unless `ALLOW_LOCAL_PATH_INGEST=1` | `get_vault_stats` |
| `POST /obsidian/ingest` (`:329`) | user | `vault_path` | totals; 403 as above | `read_vault`, `ingest_content` per note |
| `POST /obsidian/preview-zip` (`:368`) | user | multipart zip (max 50 MB) | vault stats | `extract_vault_from_zip`, `get_vault_stats_from_dir` |
| `POST /obsidian/ingest-zip` (`:398`) | user | multipart zip (max 50 MB) | `total_files_processed`, `total_chunks_stored`, `total_words_processed`, `skipped_files`, `all_tags` | `extract_vault_from_zip`, `read_vault`, `ingest_content` per note |

### 2.3 Profile (`backend/routers/profile.py`)

| Method, path | Auth | Request | Response | Calls |
|---|---|---|---|---|
| `GET /profile` (`:20`) | user | none | `{profile, has_profile, profile_complete}`; `profile_complete` is "name is non-empty" (`:25`) | `load_profile` |
| `POST /profile` (`:33`) | user | any JSON object (untyped `dict`, `:35`) | `{saved, user_id}`; 500 if the read-back name differs (`:49-55`) | `save_profile` |
| `POST /extract-resume` (`:61`) | user | multipart PDF | `{profile, experience_nodes}`; saves nothing (`:185-191`) | PyMuPDF, then one Sonnet call, `max_tokens=3000`, `event_type="resume_extract"` (`:134-141`) |
| `POST /save-experience-nodes` (`:198`) | user | `{nodes: [...]}` | `{saved, count}` | `save_experience_nodes`: delete all of the user's nodes, then insert (`backend/memory/experience_store.py:66`) |

### 2.4 History (`backend/routers/history.py`)

| Method, path | Auth | Request | Response |
|---|---|---|---|
| `GET /history` (`:48`) | user | none | `{posts: [...]}`, 20 newest, each with `versions[]` |
| `POST /log-post` (`:65`) | user | `topic`, `format`, `tone`, `content`, `authenticity_score`, `svg_diagrams?`, `archetype=""`, `trace_id?` | `{post_id, saved}`; inserts the post and version 1; links the trace (`:72-95`) |
| `PATCH /history/{post_id}` (`:99`) | user | any of `content`, `authenticity_score`, `svg_diagrams` | `{updated}`; a content change adds a "refined" version (`:118-127`) |
| `DELETE /history/{post_id}` (`:134`) | user | none | `{deleted}` or 404 |
| `PATCH /history/{post_id}/publish` (`:150`) | user | `platform`, `published_content?` | `{published}`; appends `published_content` to the profile's writing samples (`:164-165`) |
| `POST /history/{post_id}/restore/{version_id}` (`:169`) | user | none | `{restored, version_number, content, authenticity_score}` |

### 2.5 Library, ideas, stats, feedback, analytics, admin

| Method, path | Auth | Request | Response | File |
|---|---|---|---|---|
| `GET /library` | user | none | `{sources[], total_chunks, total_sources}` with `retrieval_count` per source | `routers/library.py:15-25` |
| `GET /library/clusters` | user | none | `{clusters[], unclustered_sources[], total_sources, total_tags}`; a cluster is a tag shared by two or more sources | `routers/library.py:28-89` |
| `DELETE /library/source` | user | `{source_title}` | `{deleted, chunks_removed, message}` or 404 | `routers/library.py:92-108` |
| `GET /suggestions` | user | `count` 1 to 15 (default 8), `topic?` | `{suggestions[]}` or `{sparse: true, suggestions: []}` | `routers/ideas.py:10-23` |
| `GET /stats` | user | none | `{total_chunks, tags[]}` | `routers/stats.py:18-23` |
| `GET /usage/me` | user | none | totals, this-week totals, breakdown by `event_type` | `routers/stats.py:45-93` |
| `POST /feedback` | user | `message`, `page` | `{received}`; appends to `feedback.jsonl`, sends a Telegram message when configured | `routers/feedback.py:46-67` |
| `POST /log-event` | user | `event_type`, `page_url?`, `button_name?`, `metadata` | `{logged}`; inserts into `user_events` in a background task | `routers/analytics.py:47-54` |
| `GET /admin/me` | user | none | `{is_admin}` | `routers/admin.py:17-20` |
| `GET /admin/usage` | admin | none | `distinct_users`, `calls`, `cost_usd`, `daily[14]`, `top_users[]` | `routers/admin.py:23-97` |
| `GET /admin/analytics-data` | admin | `days` 1 to 365 (default 30) | event breakdown, page views, button clicks, funnels, daily events, retention, feed-memory usage | `routers/analytics.py:57-284` |
| `GET /health` | none | none | `{status: "ok"}` | `main.py:101-103` |

CORS allows `http://localhost:3000`, `https://localhost:3000`, `FRONTEND_ORIGIN`, and any origin matching `https://.*\.vercel\.app`, with credentials (`backend/main.py:72-87`) [V].

---

## 3. Data model

Schema source: `backend/migrations/000_baseline_schema.sql` (a `pg_dump`), plus `002` to `006`. There is no file numbered `001` [V]. Row-level security is enabled on all thirteen tables with no policies in the dump (`000_baseline_schema.sql:706-778`) [V].

### 3.1 `embeddings` (the vector store)

Embeddings live in Postgres with pgvector. No ChromaDB or SQLite is used by the code (`backend/memory/vector_store.py:1-5`) [V]; `chromadb==0.5.23` is still in `backend/requirements.txt:6` and nothing imports it [V].

| Property | Value | Source |
|---|---|---|
| Embedding model | `all-MiniLM-L6-v2`, sentence-transformers, loaded lazily in-process | `vector_store.py:39,57-61` |
| Dimension | 384 | `000_baseline_schema.sql:89` |
| Index | `ivfflat`, cosine ops, `lists=100` | `000_baseline_schema.sql:561` |
| Search function | `match_embeddings(query_embedding, match_user_id, match_count)`: filter by `user_id`, order by cosine distance, limit | `000_baseline_schema.sql:40-61` |
| Chunk size | 500 words | `backend/utils/chunker.py:3` |
| Overlap | 50 words | `backend/utils/chunker.py:4` |
| Chunking detail | all whitespace is collapsed to single spaces first, so chunk text has no line breaks | `backend/utils/chunker.py:16` |

| Column | Type | Written by | Read by |
|---|---|---|---|
| `id` | text PK | `{source_id}_{i}` (`vector_store.py:116`); `consolidation_{user_id}_{entity_id}` (`memory/consolidation_store.py:33`) | fusion key, entity lookups (`vector_store.py:399-409,628`) |
| `user_id` | text | `vector_store.py:117` | every query filter |
| `content` | text | chunk text | retrieval, BM25 corpus, prompts |
| `embedding` | vector(384) | `vector_store.py:119` | RPC; `_fill_real_similarity` (`:386-393`) |
| `source_id` | text | UUID per ingest (`ingestion_agent.py:378`); the entity id for consolidation rows (`consolidation_store.py:41`) | grouping in Library, adjacent-chunk lookup |
| `source_title` | text | see section 1.4; `[Consolidated knowledge: <entity>]` for consolidation rows (`consolidation_store.py:42`) | Library, delete, retrieval stats, trace, closest sources |
| `source_type` | text | section 1.4; `consolidation` (`consolidation_store.py:43`) | frame decision, sources block `type=`, ideation labels |
| `tags` | text, comma-separated | the source's tags, the same on every chunk (`vector_store.py:108,123`) | Library, clusters, frame decision, sources block |
| `chunk_index` | int | `vector_store.py:124` | adjacent-chunk lookup (`:689-720`) |
| `total_chunks` | int | `vector_store.py:125` | copied into result dicts only [I] |
| `content_hash` | text | SHA-256 of the whole source, lower-cased and stripped (`ingestion_agent.py:80-82`); `""` for consolidation rows | duplicate check (`vector_store.py:523-542`) |
| `node_type` | text, default `chunk` | `chunk` (`vector_store.py:127`); `consolidation` (`consolidation_store.py:48`) | frame decision (`utils/frames.py:101-103`) |
| `memory_context` | text, nullable | `vector_store.py:128`; `NULL` for consolidation rows | frame decision, consolidation buckets, trace |
| `ingested_at` | timestamptz | `vector_store.py:129`; `NULL` for consolidation rows | Library sort, ideation "oldest source" |

Per-chunk metadata is exactly the columns above. Authorship (self or external), frame and entities are not stored on the chunk: frame is computed at read time (section 4.3), and entities are in `chunk_entities`.

### 3.2 `profiles`

`id uuid` (FK to `auth.users`), `data jsonb`, `created_at` (`000_baseline_schema.sql:248-252,698-699`) [V]. Written by `save_profile` (`backend/memory/profile_store.py:61-64`); read by `load_profile` and `profile_exists` (`:38-58,67-78`) [V]. `load_profile` writes back to the row when a default key is missing (`:51-57`) [V]. Contents of `data` are in section 5.

### 3.3 `posts` and `post_versions`

| Table.column | Written by | Read by |
|---|---|---|
| `posts.id`, `user_id` (uuid, FK `auth.users`) | `log_post` (`memory/feedback_store.py:34-44`) | all post queries |
| `posts.topic` | `log_post` | history; `get_all_topics_posted` for the draft prompt and `first_post` (`feedback_store.py:59-67`) |
| `posts.format`, `tone`, `archetype` | `log_post` | history |
| `posts.content`, `authenticity_score`, `svg_diagrams` | `log_post`, `update_post` (`:73-97`) | history |
| `posts.published_at`, `published_platform`, `published_content` | `mark_published` (`:111-138`) | history |
| `posts.created_at` | default | ordering |
| `post_versions.post_id`, `version_number`, `content`, `authenticity_score`, `version_type`, `svg_diagrams` | `add_version` (`:156-185`), `update_latest_version_svg` (`:245-267`) | `get_versions` (`:188-199`) |

`post_versions` has no `user_id`; ownership is checked through `posts` (`feedback_store.py:145-153`) [V]. `version_type` is `generated` or `refined` (`backend/routers/history.py:86,124`) [V]. Deleting a post cascades to versions and sets `generation_traces.post_id` to null (`000_baseline_schema.sql:674-683`) [V].

### 3.4 `entities` and `chunk_entities`

- `entities`: `entity_id`, `user_id`, `entity_name` (stored normalised), `entity_type` (one of eight values), `created_at`; unique on `(user_id, entity_name, entity_type)` (`000_baseline_schema.sql:107-114,465-466`) [V]. Written by `upsert_entity` (`backend/memory/entity_store.py:72-116`); read by query matching and consolidation (`:150-158,215-265`) [V].
- `chunk_entities`: `chunk_id` (text, the `embeddings.id`, no foreign key), `entity_id` (FK, cascade), `user_id`, `relationship_type` (`mentions`, `explains`, `used_in`, `contrasts_with`) (`000_baseline_schema.sql:72-78,666-667`) [V]. Written by `upsert_chunk_entities` (`entity_store.py:119-143`) [V].
- `relationship_type` is selected only by `get_entities_for_chunk` (`entity_store.py:182-200`), which nothing calls [V].

### 3.5 `experience_nodes`

`experience_id`, `user_id`, `node_type` (`work`, `personal_project`, `education`), `entity_name`, `role`, `start_date`, `end_date`, `domain_areas` (comma-separated), `description`, `context_label`, `created_at` (`000_baseline_schema.sql:121-134`) [V]. Written by `save_experience_nodes` (`backend/memory/experience_store.py:56-82`) [V]. Read by: the ingest cross-reference (`agents/ingestion_agent.py:258-292`), the sparse-memory ideas path (`agents/ideation_agent.py:172-183`), and `retrieval_node`, which loads them into state on every run (`agents/retrieval_agent.py:329-336`) [V]. The only reader of that state field is pipeline A's fact check (`agents/fact_check_agent.py:122-125`) [V].

### 3.6 `source_nodes` and `topic_nodes`

The columns the code uses are not the columns in the baseline schema:

| Table | Columns in `000_baseline_schema.sql` | Columns the code writes |
|---|---|---|
| `source_nodes` | `id`, `user_id`, `source_id`, `source_title`, `source_type`, `summary`, `tags`, `ingested_at` (`:259-268`); primary key `id` only (`:513-514`) | `source_id`, `user_id`, `source_title`, `source_type`, `ingested_at`, `tags`, `total_chunks`, `topic_id`, `source_summary`, `created_at`, upserted `on_conflict="source_id"` (`backend/memory/hierarchy_store.py:30-41`) |
| `topic_nodes` | `id`, `user_id`, `tag`, `source_ids` (`:328-333`) | `topic_id`, `user_id`, `topic_label`, `topic_summary`, `representative_tags`, `child_source_ids`, `created_at`, upserted `on_conflict="topic_id"` (`hierarchy_store.py:97-105`) |

[V] for both columns of the table. Reads order by `created_at` (`hierarchy_store.py:75,133`) [V]. The ingest caller wraps the hierarchy step in `try/except` and logs a warning (`agents/ingestion_agent.py:418-434`); the retrieval caller swallows exceptions with `pass` (`agents/retrieval_agent.py:122-125,147-155`) [V]. Whether the live tables match the baseline file or the code could not be checked (section 15).

### 3.7 `source_retrieval_stats`

`id`, `user_id`, `source_title`, `retrieval_count`, `last_retrieved_at`; unique on `(user_id, source_title)` (`000_baseline_schema.sql:295-301,529-530`) [V]. Written once per distinct source title per generation (`agents/retrieval_agent.py:354-360`, `memory/retrieval_stats_store.py:24-49`) [V]. `retrieval_count` is read for the Library (`retrieval_stats_store.py:52-60`) [V]. `last_retrieved_at` is written and never read [V].

### 3.8 `usage_events`, `user_events`, `generation_traces`

Columns and writers are in sections 9.5 and 10.

### 3.9 Columns never read or never written

| Column | Status | Evidence |
|---|---|---|
| `generation_traces.eval_status` | never written, never read; holds its default `pending` | only hits are the two migrations and `CODEBASE.md` (repository-wide search for `eval_status`) [V] |
| `source_nodes.summary` | never written or read by code | `hierarchy_store.py:30-41` writes `source_summary` instead [V] |
| `topic_nodes.tag`, `topic_nodes.source_ids` | never written or read by code | `hierarchy_store.py:97-105` [V] |
| `source_retrieval_stats.last_retrieved_at` | written, never read | `retrieval_stats_store.py:37-46,56` [V] |
| `usage_events.metadata`, `usage_events.model` | written, never read by backend code | written `memory/usage_store.py:58-66`; selects at `routers/admin.py:34`, `routers/stats.py:49` omit them [V] |
| `user_events.created_at` | default only; code reads and filters on `timestamp` | `routers/analytics.py:70-71` [V] |
| `chunk_entities.relationship_type` | written, read only by an uncalled function | section 3.4 [V] |
| `entities.created_at`, `experience_nodes.created_at`, `profiles.created_at` | defaults or writes only; no reader | `entity_store.py`, `experience_store.py:47`, `profile_store.py` [V] |
| `generation_traces.retrieved_context` | written by every run; selected by `get_trace_sources` (`memory/trace_store.py:12`) but not used by its caller (`agents/refine_agent.py:138-156`) | [V] |
| `generation_traces.score`, `iterations`, `archetype` (columns) | written; no backend reader. Evals read whole rows with `select("*")` (`evals/judge.py:108`) | `pipeline/trace.py:91-93` [V] |
| Profile key `years_of_experience` | read (`utils/frames.py:41`), never written by any form, default or extraction prompt | `memory/profile_store.py:8-35`, `routers/profile.py:95-104` [V] |
| Profile keys `location`, `linkedin_style_notes`, `medium_style_notes`, `thread_style_notes` | written by settings and defaults; read by no prompt builder | `profile_store.py:114-163` [V] |

---

## 4. Ingest pipeline

### 4.1 Steps in `ingest_content()` (all input types)

`backend/agents/ingestion_agent.py:320-439` [V], in order:

| # | Step | Model call | Detail |
|---|---|---|---|
| 1 | Chunk | none | `chunk_text()`; an empty result returns `chunks_stored: 0` (`:336-338`) |
| 2 | Duplicate check | none | hash of the whole content; if any row of this user has the hash, return the existing chunk count and tags with `duplicate: true` and stop (`:341-348`) |
| 3 | Tags | Sonnet 4.6, `max_tokens=150`, `event_type="ingest_tags"` | 3 to 8 lower-case tags from the first 1,500 words; JSON array, with a comma-split fallback (`:85-111`) |
| 4 | `memory_context` | Haiku 4.5, `max_tokens=10`, `event_type="memory_context_classify"`, only when not supplied or invalid | see 4.2 (`:352-368`) |
| 5 | Title | none | when no title was passed: first line, cut at 80 characters (`:370-373`) |
| 6 | Embed and store | none (local model) | one row per chunk (`:380-390`) |
| 7 | Invalidate BM25 cache | none | `:394` |
| 8 | Entities | Haiku 4.5 per chunk, `max_tokens=300`, `event_type="ingest_entities"`, up to five in parallel | up to ten entities per chunk; failures return `[]` (`:166-196,199-255`) |
| 9 | Consolidation | Haiku 4.5 per qualifying entity, `max_tokens=300`, `event_type="consolidation"` | see 4.5 (`:409-414`) |
| 10 | Hierarchy | Haiku 4.5, `max_tokens=120`, `event_type="ingest_summary"` | 2 to 3 sentence summary of the first 700 words; topic assignment (see 4.6) (`:418-434`) |

All of this runs synchronously inside the request, in a thread pool (`backend/routers/ingest.py:172-179`) [V]. Steps 8, 9 and 10 are each wrapped so a failure never fails ingestion (`:399-404,409-414,418-434`) [V]. The per-chunk entity calls run in executor threads, where the trace context variable does not propagate (`backend/llm/client.py:77-82`) [V].

Steps that run before `ingest_content` for some input types:

| Input | Extra step | Source |
|---|---|---|
| Image | Sonnet 4.6 vision call, `max_tokens=1500`, `event_type="vision_extract"`; media type guessed from the data-URI header | `routers/ingest.py:139-152`, `agents/vision_agent.py:20-52` |
| URL | `GET https://r.jina.ai/<url>`; lines under 15 characters, bare URLs and image lines are dropped; rejected under 200 characters or when two or more challenge-page phrases match | `tools/scraper_tool.py:4-29,40-60,81-126` |
| File | PyMuPDF for PDF (rejects under 100 characters), python-docx paragraphs, UTF-8 or Latin-1 text | `utils/file_extractor.py:5-66` |
| YouTube | Supadata transcript API (`text=true`) | `routers/ingest.py:294-314` |
| Obsidian | per note: strip YAML front matter, wikilinks, block refs, highlights, embeds, Dataview blocks; skip `.obsidian`, `.trash`, `templates`, `.git` and notes under 100 characters; a note whose ingest raises is skipped silently | `tools/obsidian_tool.py:9-40,57-70`, `routers/ingest.py:356-357,440-441` |

### 4.2 How `memory_context` is decided

1. If the request carries a valid value, it is used as is (`ingestion_agent.py:356,364`) [V].
2. Otherwise an experience cross-reference runs: each of the user's `experience_nodes` names is normalised and searched as a substring of the lower-cased text; a `work` node match gives `work`, else a `personal_project` match gives `personal_project` (`:258-292`) [V].
3. Otherwise a Haiku classifier reads the first 200 words and returns one of the four labels; any failure or unexpected answer gives `learning` (`:139-163`) [V].

The classifier prompt lists example phrases for each label (`:32-47`) [V].

### 4.3 How authorship, frames and `source_type` are decided

- `source_type` is set by the endpoint (section 1.4). For the Note tab it is derived from `content_origin`, then from `memory_context` (`routers/ingest.py:161-171`) [V]. The web frontend never sends `content_origin` (`frontend/lib/api.ts:11-17`); the extension does (`extension/background.js:129`) [V].
- **Authorship is not stored.** It is derived whenever a chunk is used, by `chunk_frame()` (`backend/utils/frames.py:90-123`) [V]:

| Order | Condition | Frame | Authorship |
|---|---|---|---|
| 1 | `node_type` or `source_type` is `consolidation` | `CONSOLIDATION` | external |
| 2 | `memory_context == "work"` | `PERSONAL_WORK` | self |
| 3 | `memory_context == "personal_project"` | `PERSONAL_PROJECT` | self |
| 4 | `memory_context == "observation"` | `OBSERVATION` | external |
| 5 | `memory_context` is not `learning` and `source_type` is `note` or `personal_note` | `PERSONAL` | self |
| 6 | a tag and a profile topic of expertise contain one another as substrings | `EXPERT_OUTSIDER` | external |
| 7 | otherwise | `LEARNING_JUNIOR`, `LEARNING_MID` or `LEARNING_SENIOR` | external |

`authorship()` returns `self` for the three `PERSONAL*` frames and `external` for everything else (`frames.py:26,130-132`) [V]. Seniority for row 7 comes from `years_of_experience`, else keywords in the role title, else `mid` (`frames.py:35-74`) [V].

Because `ingest_content` always ends with a non-null `memory_context` (4.2), row 5 applies only to rows ingested before that column existed [I].

### 4.4 Tags and entities

- Tags are extracted once per source and copied onto every chunk (`ingestion_agent.py:350`, `vector_store.py:108,123`) [V].
- Entities are extracted per chunk with a type and a relationship type (`ingestion_agent.py:49-78`) [V]. Names are normalised before storage: parentheticals, non-numeric dots and hyphens, and suffixes such as "framework", ".js", "db" are removed, then lower-cased (`memory/entity_store.py:15-65`) [V].
- A `chunk_entities` row links a chunk id to an entity id: this is the entity/chunk relationship (`entity_store.py:119-143`) [V]. It is used in two places: retrieval enrichment (section 6.4) and the consolidation source count.

### 4.5 "Consolidated knowledge" summaries

- Trigger: after entity extraction, `maybe_consolidate_entities` takes the entities whose links span three or more distinct sources (source id = chunk id without its last `_N`) and keeps those whose stored name equals, lower-cased, a name just extracted (`agents/consolidation_agent.py:149-192`, `memory/entity_store.py:215-265`) [V]. The names compared on one side are raw extraction output (`ingestion_agent.py:231`) and on the other the normalised stored names (`consolidation_agent.py:169-178`) [V].
- Input: up to 12 linked chunks, 80 words each, grouped by `memory_context` into work, personal project, learning, observation and other (`consolidation_agent.py:46-100`) [V].
- Output: a plain-text brief with the lines `entity`, `direct experience (work)`, `direct experience (personal)`, `learned knowledge`, `gap` (`:28-44`) [V].
- Storage: one `embeddings` row per (user, entity), re-written on each run, with `source_type="consolidation"`, `node_type="consolidation"`, `source_title="[Consolidated knowledge: <name>]"`, `tags=<name>` (`memory/consolidation_store.py:22-56`) [V].
- Use: the row is retrieved like any chunk and framed `CONSOLIDATION` ("Background only … cannot be the evidence for a first-person event", `utils/frames.py:160-164`) [V]. `get_all_sources` does not filter by `node_type`, so these rows are also grouped into the Library list (`memory/vector_store.py:545-589`) [I].

### 4.6 Experience nodes, source nodes, topic nodes

- **Experience nodes** are the user's jobs, side projects and education entries extracted from a resume (`routers/profile.py:105-124`) and saved by `/save-experience-nodes`, which replaces the whole set (`memory/experience_store.py:56-82`) [V]. Uses are listed in section 3.5.
- **Source nodes** hold one row per source with a summary and a topic id; **topic nodes** group sources that share two or more tags, or start a new topic labelled with the first tag and an empty summary (`ingestion_agent.py:295-317`, `memory/hierarchy_store.py:148-162`) [V]. Nothing later fills `topic_summary` in the backend (`ingestion_agent.py:313`); `scripts/migrate_hierarchy.py` is a one-off script outside the app [V].

### 4.7 Delete and re-upload

- `DELETE /library/source` deletes every `embeddings` row of the user with that `source_title` (`memory/vector_store.py:592-610`) [V]. Two sources with the same title are deleted together [I].
- Not touched by a delete: `source_nodes`, `topic_nodes`, `chunk_entities`, `entities`, the entity's consolidation row, and `source_retrieval_stats` (`vector_store.py:592-610`, `routers/library.py:92-108`) [V].
- The BM25 cache is not invalidated on delete; it expires after 300 seconds (`vector_store.py:45,304-312`, `routers/library.py:92-108`) [V].
- Traces keep the text of the chunks they used (`pipeline/trace.py:25-44`) [V].
- Re-uploading identical content while it is still stored returns `duplicate: true` and makes no model call (`ingestion_agent.py:341-348`) [V]. The hash covers content only, so the same text under a different source type or context is also a duplicate [V].
- Re-uploading after a delete finds no hash and runs the full pipeline with a new `source_id` (`ingestion_agent.py:378`) [V]. The deleted source's `chunk_entities` rows remain and still count as a distinct source in the consolidation threshold [I].
- Edited content has a different hash and is stored as an additional source; the old version stays (`evals/README.md:68-70`) [V].

---

## 5. Profile

### 5.1 What is stored

`profiles.data` is a free-form JSON object. `DEFAULT_PROFILE` defines 14 keys: `name`, `role`, `bio`, `location`, `voice_descriptors`, `writing_rules`, `topics_of_expertise`, `target_audience`, `words_to_avoid`, `opinions`, `writing_samples`, `linkedin_style_notes`, `medium_style_notes`, `thread_style_notes` (`backend/memory/profile_store.py:8-35`) [V]. `POST /profile` accepts any keys (`backend/routers/profile.py:35`) [V]. Experience nodes are stored separately (section 3.5).

### 5.2 How it is collected

| Path | Fields | Source |
|---|---|---|
| First-post answers | `role`, `bio` (from the experience detail), `target_audience`, `opinions`, `writing_samples`; the rest empty | `frontend/app/first-post/page.tsx:1040-1076` |
| Resume extraction (one Sonnet call) | `name`, `role`, `bio`, `location`, `topics_of_expertise`, `voice_descriptors` (inferred "from their domain and seniority"), `opinions` ("they likely hold"), plus experience nodes | `backend/routers/profile.py:95-116` |
| Name fallback | Google `full_name`, else the email prefix | `first-post/page.tsx:1090-1093` |
| Onboarding intercept | `voice_descriptors`, `target_audience`, `writing_rules` | `frontend/components/OnboardingIntercept.tsx:35-53,116-137` |
| Settings | every field | `frontend/app/settings/profile/page.tsx:343-426` |
| Publishing a post | `writing_samples` gains the published text; de-duplicated, last 10 kept | `backend/memory/profile_store.py:81-95` |

### 5.3 Which parts reach which prompts

Two formatters exist (`backend/memory/profile_store.py:114-163`) [V]:

- `profile_voice_context()`: name, role, target audience, voice descriptors, writing rules (followed by a "style only" sentence), words to avoid, and each writing sample cut to 500 characters under a "do not reuse any facts" line.
- `profile_to_context_string()`: all of the above plus bio, topics of expertise and opinions.

| Consumer | Receives | Source |
|---|---|---|
| Draft prompt, all variants | voice context | `agents/draft_prompt.py:219` |
| Draft style rules, single writer | `words_to_avoid` again | `agents/draft_prompt.py:353` |
| Selection refine, both writers | voice context and `words_to_avoid` | `agents/refine_agent.py:237-238`, `agents/refine_cited_agent.py:44` |
| Critic and humanizer (pipeline A) | voice context; `words_to_avoid` | `agents/critic_agent.py:111`, `agents/humanizer_agent.py:118-119` |
| Review (variant B) | name and role only [I from the prompt template] | `agents/review_prompt.py:19-20` |
| Fact check (pipeline A) | name, role, employers from work experience nodes | `agents/fact_check_agent.py:117-129` |
| Idea suggestions | the whole-profile string; `topics_of_expertise`, `role`, `bio` also seed the sampling queries | `agents/ideation_agent.py:157,206-223` |
| Frame decision (code) | `topics_of_expertise`, `role`, `years_of_experience` | `utils/frames.py:41,54,118` |
| Deterministic `banned_text` check (code) | `words_to_avoid` | `pipeline/checks.py:216-221` |
| Specifics guard (pipeline A and the legacy refine writer; code) | every profile value except `writing_samples` counts as a source of facts | `utils/specifics.py:247-251` |
| Generation trace | the whole profile as `profile_snapshot` | `pipeline/trace.py:73` |
| Structure choice, compress, scorer, visuals, ingest calls | nothing from the profile in the prompt text (the structure and compress calls use the profile only to compute frames) | `agents/archetype_agent.py:197-198`, `agents/compress_agent.py:85` |

`bio`, `opinions` and `topics_of_expertise` reach no writing prompt in any variant: `profile_voice_context` leaves them out by design (`profile_store.py:144-148`) [V]. `location` and the three style-notes fields reach no prompt at all [V].

---

## 6. Retrieval

All in `backend/agents/retrieval_agent.py` and `backend/memory/vector_store.py`; thresholds in `backend/config/retrieval.py`.

### 6.1 Query

One string: `"{topic}. {context}"` when there is context, else the topic (`retrieval_agent.py:326`) [V]. There is no query rewriting or expansion, and no model call in retrieval [V].

### 6.2 Hybrid search

1. The query is embedded once (`vector_store.py:482`) [V].
2. Two searches run in a two-thread pool with a 10 second timeout each (`vector_store.py:484-494`) [V]:
   - **Vector**: `match_embeddings` RPC, top 8 by cosine, filtered by `user_id` only (`vector_store.py:136-153`) [V].
   - **BM25**: `BM25Okapi` over every row of the user (content and metadata, no vectors), cached per user in process memory for 300 seconds and dropped on ingest (`vector_store.py:45-48,260-322,455-462`) [V]. Tokens are lower-cased, stop words dropped, plurals and possessives folded (`vector_store.py:223-257`) [V]. Each hit gets `bm25_norm` = score divided by the most a single chunk could score for the query's tokens (`vector_store.py:325-362`) [V].
3. **RRF**: `score = Σ 1 / (60 + rank + 1)` over both lists, keyed by row id; the top 8 are kept and tagged with `rrf_score` and `rrf_rank` (`vector_store.py:412-452,503`) [V].
4. BM25-only hits get their real cosine by fetching their vectors (`vector_store.py:380-396,505-510`) [V].

### 6.3 Filters and ranking

- **Metadata filters: none.** No search filters on `source_type`, `memory_context`, tags, date or `node_type`; the only filter is `user_id` (`000_baseline_schema.sql:58`, `vector_store.py:271`) [V]. Consolidation rows compete with ordinary chunks.
- **Relevance filter**: a chunk is kept when its own cosine ≥ 0.30 or its own `bm25_norm` ≥ 0.30 (`retrieval_agent.py:28-33`, `config/retrieval.py:14-15`) [V].
- **Order**: RRF order, followed by entity-linked additions (`retrieval_agent.py:345-347`) [V]. There is no reranker [V].

### 6.4 Entity enrichment

Entities whose stored name (three or more characters) is a substring of the normalised query are looked up; chunks linked to them and not already present are fetched (up to 8 candidates), given their real cosine, sorted, and the top 4 appended with `entity_linked: true` (`retrieval_agent.py:249-318`) [V]. They are not subject to the relevance filter and are not counted by confidence or the coverage gate (`retrieval_agent.py:391-399`) [V]. Maximum chunks per run: 8 + 4 = 12.

### 6.5 Bundle, confidence and the coverage gate

- `_build_retrieval_bundle` looks up each chunk's source node, the topic node, and one adjacent chunk for the first three sources (`retrieval_agent.py:98-166`) [V]. `_format_retrieved_context` turns that into a text block stored as `state["retrieved_context"]` (`:169-246,350`) [V]. No prompt builder reads `retrieved_context`, `source_contexts` or `topic_contexts`; the drafter's sources come from `bundle["chunks"]` only (`agents/draft_prompt.py:181-183,340-341`) [V].
- **Confidence** (from the raw fused results, before filtering): `high` when top cosine ≥ 0.45; `medium` when the gate passes; else `low` (`retrieval_agent.py:40-52`, `config/retrieval.py:25`) [V].
- **Coverage gate**: covered when top cosine ≥ 0.30 or top `bm25_norm` ≥ 0.30 (`retrieval_agent.py:36-37`, `config/retrieval.py:20-21`) [V].

| Decision | When | Effect |
|---|---|---|
| `pass` | covered | draft |
| `bypassed` | not covered, `no_specifics` requested | draft (unreachable while `NO_SPECIFICS_MODE_ENABLED = False`, `config/features.py:11`) |
| `skipped_first_post` | not covered, user has no posts | draft |
| `low_coverage` | not covered otherwise | graph ends; response has `status: "low_coverage"`, an empty post, up to three closest sources (title, 200-character preview, similarity) and a fixed suggestion |

Source: `retrieval_agent.py:55-95`, `pipeline/graph.py:91-100,295-309` [V]. A trace row is still written for a gated run (`pipeline/graph.py:279-287`) [V].

### 6.6 The first-post path

- `first_post` is true when the user has no rows in `posts` (`pipeline/graph.py:40-41`) [V].
- The gate does not block (`skipped_first_post`). When the gate was skipped, the perspective is forced to `opinion` (`pipeline/graph.py:59-66`) [V].
- Length target is 70 to 100 words whatever was requested, and the format instructions use `concise` (`utils/formatters.py:70,97-99`, `agents/draft_prompt.py:220-224`) [V].
- A "FIRST POST RULE" block forbids placeholders and multi-section structure (`agents/draft_prompt.py:69-73,231`) [V]; the `banned_text` check flags a placeholder line in a first post (`pipeline/checks.py:222-227`) [V].
- With the `opinion` perspective, the structure choice is limited to `contrarian_take`, `teach_me_something` and `general`, and is shown no chunks (`agents/archetype_agent.py:33,85-86,113,197`) [V].
- With no chunks, the "NO NOTES RULE" is prepended (`agents/draft_prompt.py:75-86,212-214`) [V]. The onboarding answers reach the model only as the request's `context` (section 1.3) [V].

### 6.7 Fallbacks

| Failure | What happens | Source |
|---|---|---|
| Vector search raises or times out | warning logged; BM25 results are used alone | `vector_store.py:487-501` |
| BM25 raises or times out | warning logged; vector results are used alone | `vector_store.py:491-499` |
| Both empty | hybrid returns `[]` | `vector_store.py:496-497` |
| Similarity fill-in for BM25-only hits fails | those hits get similarity 0.0 | `vector_store.py:505-510` |
| Anything in the hybrid block raises | `print`, then a vector-only search (`query_similar`); `retrieval_path = "flat_fallback"`, no enrichment, no stats | `retrieval_agent.py:363-377` |
| The vector-only fallback also raises | empty results; the run continues as if memory were empty, so a non-first post ends as `low_coverage` (labelled `STOPGAP` in code) | `retrieval_agent.py:369-374` |
| Entity enrichment fails | chunks unchanged, warning | `retrieval_agent.py:316-318` |
| Source or topic node lookup fails | skipped silently (`pass`) | `retrieval_agent.py:122-125,147-155` |
| Retrieval-stat write fails | `print`, ignored | `retrieval_agent.py:361-362` |
| Experience-node load fails | empty list, debug log | `retrieval_agent.py:334-335` |

All [V]. The run logs the first 50 characters of the topic and prints the first 120 characters of the first retrieved chunk (`retrieval_agent.py:343,409-410`) [V].

---

## 7. Generation

### 7.1 Variants

| Variant | Graph | Draft model | Review model | Small model | Source |
|---|---|---|---|---|---|
| A | A | Sonnet 4.6 (fixed) | none | Haiku 4.5 (fixed) | `backend/llm/client.py:28-29` |
| B | B | Sonnet 4.6 | Sonnet 4.6 | Haiku 4.5 | `backend/llm/models.py:63-67` |
| C | C | Sonnet 4.6 | not used | Haiku 4.5 | same |
| B-Opus | B | Opus 5.5 | Sonnet 4.6 | Haiku 4.5 | `backend/llm/models.py:71-74` |
| **C-Opus (default)** | C | Opus 5.5 | not used | Haiku 4.5 | `backend/config/features.py:33-34` |

`PIPELINE_VARIANT` overrides the default; an unknown value stops the server at startup (`config/features.py:42-57`, `backend/main.py:48-52`) [V]. The variant is never a request field (`config/features.py:29`) [V]. All five graphs are compiled at import (`pipeline/graph.py:209`) [V].

### 7.2 C-Opus, step by step

Shared head, then `wire_draft_only` (`pipeline/single_writer.py:54-75`) [V].

| # | Step | Model | Prompt | Inputs | Outputs |
|---|---|---|---|---|---|
| 1 | `load_profile` | none | none | `user_id` | `profile`, `posted_topics`, `first_post` (`pipeline/graph.py:34-42`) |
| 2 | `retrieval` | none (local embedder) | none | topic, context | bundle, confidence, coverage gate (section 6) |
| 3 | `plan` | none | none | format, length, `first_post`, confidence, chunks | `length_target`, `perspective` (`pipeline/graph.py:45-68`) |
| 4 | `structure` | Haiku 4.5, structured tool call, `max_tokens=300`, `event_type="archetype"` | `ARCHETYPE_PROMPT` in `agents/archetype_agent.py:35-57` | topic, context, format, the sources block, the allowed archetype keys with one line each | `archetype`, `archetype_decision` (`archetype_agent.py:187-230`) |
| 5 | `draft` | Opus 5.5, `output_config.effort="medium"`, `event_type="generate"` | `CITED_PROMPT` in `agents/draft_prompt.py:310-329` | voice context, format and tone, length rule, sources block `S1..Sn`, topic, context, posted topics, perspective rule, grounding block, structure, source rules, style rules, citation rules, event rule (story types), visual rules, output format | the draft inside `<post>` (and `<event>`), with `[[…]]` markers (`agents/draft_agent.py:119-153`) |
| 6 | `strip` | none | none | draft text | post body, `event`, `draft_format`; `<event>none</event>` switches the archetype to `general` (`pipeline/finalise.py:103-135`) |
| 7 | `finalise` | none | none | marked body | clean post, `citations` spans, `citation_failures`, `multi_sentence_spans`, `final_validation` (`pipeline/finalise.py:138-159`) |
| 8 | `checks` | none | none | spans, source index, chunks, request, profile | `checks_before_trim`, `checks_final` (`pipeline/checks.py:284-304`) |
| 9 | `compress`, only when over the maximum | Opus 5.5, same effort and budget as the draft, `event_type="compress"` | system `COMPRESS_PROMPT`, user data from `build_compress_prompt` (`agents/compress_prompt.py:20-60`) | sources block, numbered sentences with word counts and markers, the limit and the excess | shorter replacements in `<fixes>`; `compress_result` (`agents/compress_agent.py:58-126`) |
| 10 | `finalise_compressed`, `recheck` | none | none | the spliced post | `final_validation`, `checks_final` (`pipeline/finalise.py:162-180`, `pipeline/checks.py:307-312`) |

Details, all [V]:

- **Plan.** Length ranges are in one table: LinkedIn 100–180 / 250–350 / 450–600 words, Medium 350–500 / 700–900 / 1,200–1,800; threads have no word target (`utils/formatters.py:52-68`). Low retrieval confidence removes the minimum (`formatters.py:101-102`). Perspective is `experience`, `learned`, `mixed` or `opinion`, from the chunks' authorship (`utils/frames.py:390-398`).
- **Structure.** Eight archetypes (`utils/formatters.py:181-269`). Three are story types and are offered only when at least one chunk is self-authored (`agents/archetype_agent.py:78-87`). A failed call, a truncated answer or a key outside the allowed set gives `general` with a recorded reason (`archetype_agent.py:204-221`).
- **Sources block.** Each chunk becomes `<source id="S1" kind="<frame label>" type="<source_type>" tags="…">text</source>`; titles and database ids are not shown (`utils/frames.py:261-304`).
- **Draft budget.** `max(2000, ceil(max_words × 2.5 × 1.25))` output tokens for the Claude 4.7 tokenizer, plus 3,500 for thinking, capped at 16,000 (`utils/formatters.py:143-161`, `llm/client.py:35,45,50-56`).
- **No retry in the draft step.** A `refusal` stop reason, a `max_tokens` stop, or an empty post ends the run with `draft_refused`, `draft_truncated` or `draft_empty` and no post (`agents/draft_agent.py:147-152`, `pipeline/finalise.py:132-133,155-156,199-200`, `pipeline/graph.py:311-325`).
- **Finalise.** Em dashes outside code, URLs and quoted literals become a comma, a full stop, or an en dash between digits (`utils/formatters.py:26-46`). Length is counted as prose words: headings, placeholder lines and code blocks are excluded (`pipeline/finalise.py:83-87`).
- **Checks.** Nine types: `citation_malformed`, `citation_unknown_id`, `uncited_span`, `specific_not_in_cited_source`, `view_contains_specific`, `event_unverified`, `mixed_authorship_span`, `over_length`, `banned_text` (`pipeline/checks.py:39-42`). Under C and C-Opus they are recorded in the trace and nothing acts on them or shows them (`pipeline/checks.py:284-294`).
- **Compress.** A replacement is used only if it names an existing sentence once, is not a deletion, is one sentence, keeps the sentence's marker and list marker, has fewer words, adds no number, date or time reference, and leaves sentence boundaries unchanged (`pipeline/compress.py:58-86,143-176`). Outcomes: `compressed`, `still_over` (shorter post kept), `compress_failed` (post unchanged) (`agents/compress_agent.py:61-73`). There is one compress call per post and no second attempt.
- **Under-length** is recorded and nothing lengthens a post (`pipeline/finalise.py:21`).
- **Quality.** No node in graph C reads `quality`; every value runs the same steps (`pipeline/single_writer.py:54-75`, `config/features.py:24-25`).
- **What the response carries under C-Opus.** `score` 0, `scored` false, `iterations` 0, `review` null, and no fact-check job (`pipeline/graph.py:37,292,327-339`; `pipeline/redraft.py:300-306`). The fact check node exists only in graph A (`pipeline/graph.py:143`), so no fact check of any kind runs under the default.

### 7.3 Cost per post

List prices per million tokens, input / output (`backend/llm/pricing.py:28-34`, "checked 2026-10-10") [V]:

| Model | Input | Output |
|---|---|---|
| Opus 5.5 | $4.00 | $20.00 |
| Sonnet 5.5 | $2.00 | $10.00 |
| Haiku 5.5 | $0.10 ($0.50 above 100,000 prompt tokens) | $0.50 ($2.50) |
| Sonnet 4.6 | $3.00 | $15.00 |
| Haiku 4.5 | $1.00 | $5.00 |

`call_cost` is `(input × price_in + output × price_out) / 1,000,000`, with thinking tokens billed as output; no call uses prompt caching or batching (`llm/pricing.py:4-7,37-46`) [V].

A C-Opus post is one Haiku 4.5 call plus one Opus 5.5 call, plus a second Opus 5.5 call when the draft is over length (section 7.2) [V]. Measured on the "full" ablation, 20 posts per variant, as recorded in the plan: C-Opus $0.055 per post and 22.1 s median wall time; A $0.041 and 32.9 s; C $0.018 and 14.3 s; B-Opus $0.229 and 41.4 s (`docs/plans/single-writer.md:577`) [V that the document says so; the figures were not recomputed here].

### 7.4 `PIPELINE_VARIANT=A`

The rollback switch (`config/features.py:27-28`) [V]. After `plan` (`pipeline/graph.py:134-169`) [V]:

| Step | Model | What it does | Source |
|---|---|---|---|
| draft | Haiku 4.5 (archetype, with an event note and quote), then Sonnet 4.6, `max_tokens=2000`; one retry when the specifics guard finds unsupported numbers or dates, then removal of the offending sentences | first draft, no citation markers | `agents/draft_agent.py:54-94` |
| critic | Haiku 4.5, structured, `max_tokens=600` | five verdicts with free-text fixes; skipped for `quality="draft"`; a failure records `{"error": …}` | `agents/critic_agent.py:95-140` |
| humanizer | Sonnet 4.6, `max_tokens=2000`, one guard retry | whole-post rewrite; keeps its input if the retry still adds facts | `agents/humanizer_agent.py:107-163` |
| predictability audit | Haiku, Sonnet, Haiku (up to five calls with the retry) | rewrites the most "AI-sounding" sentence, then rhythm; all exceptions swallowed | `agents/predictability_audit_agent.py:128-197` |
| scorer loop | Sonnet 4.6, structured, `max_tokens=800`; only `quality="polished"` | loops back to the humanizer while score < 75 and iterations < 3 | `pipeline/graph.py:30-31,110-131`, `agents/scorer_agent.py:72-88` |
| word-count enforcer | Haiku 4.5, `max_tokens=2000`, one guard retry | trims or expands to the target; all exceptions swallowed | `agents/word_count_enforcer_agent.py:52-146` |
| fact check | none in the graph for normal posts: it marks the check `pending`; a Haiku call runs after the response and writes flags to the trace | log-only | `agents/fact_check_agent.py:227-235,299-318`, `config/fact_check.py:7` |
| finalize | none | em-dash normalisation; validation recorded only | `pipeline/graph.py:103-107` |

### 7.5 Status of B, B-Opus and C

- All three are fully wired and selectable by `PIPELINE_VARIANT` or by `run_pipeline(variant=…)` (`config/features.py:30`, `pipeline/graph.py:175-179,253`) [V]. None is the default; the code comments describe them as the ablation's variants and state that evals pass the variant directly (`config/features.py:14-29`) [V].
- **C** is C-Opus with Sonnet 4.6 as the drafter [V].
- **B and B-Opus** add, after the checks: a structured review in parallel groups of four sentences on the review model (`agents/review_agent.py:71-76,245`), a code step that derives issues by fixed rules (`pipeline/review_rules.py`), code fixes (delete a sentence nothing states, replace a wrong marker), then at most one of a targeted fix or a full redraft, a second review, compress, and an outcome of `clean`, `fixed`, `issues_remain` or `not_reviewed` (`pipeline/single_writer.py:104-155`, `pipeline/fixes.py:1-39`) [V]. `quality="draft"` under B skips the review (`pipeline/single_writer.py:89-94`) [V].
- B's `review` summary is returned by `/generate` (`routers/generate.py:92,206`) and the frontend does not read it: `GenerateResponse` in `frontend/lib/api.ts:52-72` has no `review` field [V]. The code labels this a stopgap (`pipeline/graph.py:239-242`) [V].

---

## 8. Selection refine and other model calls

### 8.1 Selection refine

`backend/agents/refine_agent.py`, `refine_cited_agent.py`, `refine_prompt.py` [V].

1. The post's trace is loaded by `trace_id`, else the newest trace linked to `post_id` (`memory/trace_store.py:15-45`). No identifier, no trace, or a trace without usable stored chunks raises `MissingRefineSources` → HTTP 409 (`refine_agent.py:132-142`).
2. **Trace has a `source_index`** (a single-writer post): the model that drafted the post (read from `node_outputs.models.draft`) rewrites the passage from the stored sources block, with a marker on every sentence, `max_tokens` 500 plus thinking room; the passage goes through the deterministic passage checks; one retry with the findings; then the selection is kept with `status: "reverted"` (`refine_agent.py:159-178`, `refine_cited_agent.py:26-97`). Every attempt is appended to the trace under `node_outputs.refine_selection` (`refine_cited_agent.py:67-76`).
3. **No `source_index`** (pipeline A's posts and older ones): Sonnet 4.6, `max_tokens=500`, frame-formatted sources, the specifics guard on numbers, dates, durations and money, one retry, then `reverted` (`refine_agent.py:235-282`).
4. A refused or truncated reply is never used (`refine_agent.py:252,266-267`, `refine_cited_agent.py:78-83`). An optional `<note>` from the model is returned separately (`refine_agent.py:96-97,193-196`).

Event types: `refine_selection`, `refine_selection_retry`.

### 8.2 Every other model call

| Call | When | Model | Purpose | Source |
|---|---|---|---|---|
| Score | "Analyse" on `/create` (`POST /score`); pipeline A in `polished` | Sonnet 4.6, structured, `max_tokens=800`, `event_type="score"` | five 0–20 dimensions summed in code; `null` when no valid answer | `agents/scorer_agent.py:45-69` |
| Diagram | `POST /generate-visuals`, one call per `[DIAGRAM: …]` placeholder | Sonnet 4.6, `max_tokens=4000`, `event_type="visual_svg"` | SVG from the description; a visual style is picked by keywords in the description | `agents/visual_agent.py:64-74,90-126,145-184` |
| Diagram refine | `POST /refine-visual` | same | edit an SVG by instruction | `agents/visual_agent.py:106-111` |
| Ideas | `GET /suggestions` | Sonnet 4.6, `max_tokens=2000`, `event_type="ideation"` | ideas from sampled chunks; under 10 chunks, from experience nodes; with neither, `{sparse: true}` and no call | `agents/ideation_agent.py:153-341` |
| Resume extraction | `POST /extract-resume` | Sonnet 4.6, `max_tokens=3000`, `event_type="resume_extract"` | profile fields and experience nodes | `routers/profile.py:134-141` |
| Image to text | image ingest | Sonnet 4.6, `max_tokens=1500`, `event_type="vision_extract"` | transcribe or describe the image | `agents/vision_agent.py:25-50` |
| Memory-context classifier | ingest without a context; `POST /suggest-memory-context` | Haiku 4.5, `max_tokens=10` | one of four labels | `agents/ingestion_agent.py:139-163` |
| Tags, entities, source summary, consolidation | ingest | Sonnet (tags), Haiku (rest) | section 4.1 | `agents/ingestion_agent.py` |
| Fact check | pipeline A only | Haiku 4.5 find (`max_tokens=400`), Sonnet 4.6 rewrite (`max_tokens=1000`) when enforced | section 7.4 | `agents/fact_check_agent.py:161-195,249-255` |
| Eval judge | evals only | Haiku 4.5 or Sonnet 4.6, `event_type="eval_judge"` | DeepEval metrics | `evals/eval_config.py:10-14` |

All calls are non-streaming (`llm/client.py:31-35`) [V]. The idea sampler's "hybrid batch" function delegates to vector-only search (`memory/vector_store.py:514-520`) [V].

---

## 9. Evaluation

### 9.1 Harness

`evals/` runs from a separate working directory with the backend's virtualenv (`evals/README.md:82-90`) [V].

| Script | Does | Source |
|---|---|---|
| `env.py`, `guard.py` | refuse to run unless `EVAL_SUPABASE_URL` is exactly the project named by `EXPECTED_PROJECT_REF`; disable dotenv; set every backend env var explicitly | `evals/README.md:13-25`, `evals/guard.py:30-61` |
| `seed.py` | save each persona's profile and experience nodes, ingest its sources with their `memory_context`, add seed posts so `first_post` is false | `evals/README.md:65-70` |
| `reset.py` | delete the eval users' rows from twelve tables | `evals/guard.py:76-89` |
| `run.py` | call `run_pipeline` per golden as its persona; write `meta.json` and `runs.jsonl`; run the log-only fact check after timing | `evals/README.md:92-94,111-113` |
| `judge.py`, `judge_model.py`, `metrics.py` | build test cases from the trace row (no re-run); judge through `llm.client.complete()`; cache per (golden, metric, judge model) | `evals/README.md:95-103` |
| `report.py`, `reporting.py` | markdown reports and judge comparisons | `evals/report.py:1-13` |
| `ablate.py`, `ablation.py`, `spend.py` | the multi-variant ablation under one spend cap ($14 by default) | `evals/eval_config.py:32,78`, `evals/spend.py:1-15` |
| `instrument.py` | run B's review on every variant's final post, record-only | `evals/instrument.py:1-21` |
| `blind.py` | judge audit (10 findings to mark) and blind read (rank posts per golden) | `evals/blind.py:1-12` |
| `review_regression.py` | run eight fixed cases against the review model | `evals/review_regression.py:1-16`, `evals/fixtures/review_cases.jsonl` |

`run.py` uses `features.pipeline_variant()` when no `--variant` is given (`evals/run.py:116`) [V].

### 9.2 Goldens and personas

- Three personas: `ds`, `pm`, `founder`, each with a profile, experience nodes, seed posts and markdown sources carrying `title`, `source_type` and `memory_context` headers (`evals/loaders.py:1-19`, `evals/fixtures/personas/`) [V].
- 27 goldens, nine per persona, with difficulty `rich`, `sparse` or `off_topic` (`evals/goldens/goldens.jsonl`, 27 lines) [V]. Fields: `id`, `persona`, `difficulty`, `topic`, `context`, `format`, `tone`, `length`, `expected_source_titles`, optional `expected_perspective` and `note` (`evals/README.md:174-180`) [V].
- Goldens never exercise the first-post path, because seeding adds posts (`docs/plans/single-writer.md:425`) [V].

### 9.3 Metrics and thresholds

`answer_relevancy` 0.7, `contextual_relevancy` 0.5, `faithfulness` 0.8, `unsupported_specifics` 0.7, `source_recall` 0.5 (deterministic) (`evals/eval_config.py:17-23`) [V]. The default judge is Haiku; the ablation reads `unsupported_specifics` from Sonnet (`eval_config.py:10,82`) [V].

### 9.4 Judges and their recorded reliability

| Instrument | Recorded finding | Source |
|---|---|---|
| `unsupported_specifics` judge (Sonnet) | 3 of 10 audited findings judged correct; "too lenient": right both times it failed a post, wrong seven times it passed one. The audit bar is 8 of 10, so the ablation decision dropped this criterion | `docs/plans/single-writer.md:576`, `evals/eval_config.py:87-89` |
| Haiku versus Sonnet as judge | on six goldens, the two disagreed on pass/fail for `unsupported_specifics` on three (mean 0.87 versus 0.62) | `evals/baselines/compare-haiku-sonnet.md` |
| Log-only fact check | "over-flags paraphrases of the sources (0/5 on supported claims, 2026-10-03)"; 41 sentences flagged on 18 of 20 posts in the 2026-10-08 run; reports label it "leads, not verdicts" | `backend/agents/fact_check_agent.py:217-218`, `docs/plans/single-writer.md:280`, `evals/README.md:111-113` |
| Structured review (variant B) | seven of eight regression cases pass; `changed_detail` right on 3 of 12, so it and `ai_rhythm` are record-only | `docs/plans/single-writer.md:268-270`, `backend/pipeline/redraft.py:61` |
| Instrument | uses the reviewer B was fixed against, so it favours B by construction | `evals/instrument.py:1-4` |
| Blind read | one reader, no sources shown; decided the default (C-Opus ranked first in 10 of 10) | `docs/plans/single-writer.md:575,578` |
| Sentence-level read with sources | found unsupported sentences and wrong attributions in both Opus variants | `docs/plans/single-writer.md:578` |

### 9.5 `generation_traces`: every field

Row built by `build_trace_row` (`backend/pipeline/trace.py:56-94`), inserted by `run_pipeline` after every run, including gated and no-post runs; a failed insert is logged and the request continues with `trace_id: null` (`pipeline/graph.py:282-287`) [V].

| Column | Content | Set by |
|---|---|---|
| `id` | UUID, returned as `trace_id` | database default |
| `user_id` | caller | `trace.py:61` |
| `post_id` | the saved post | `POST /log-post` when it carries `trace_id` (`routers/history.py:89-95`); null until then and after the post is deleted |
| `created_at` | insert time | default |
| `topic`, `context`, `format`, `tone`, `length`, `quality` | request inputs | `trace.py:62-67` |
| `retrieval_query` | the query string | `trace.py:68` |
| `retrieval_path` | `hybrid` or `flat_fallback` | `trace.py:69` |
| `retrieval_confidence` | `low`, `medium`, `high` | `trace.py:70` |
| `retrieved` | one object per chunk used: `chunk_id`, `source_id`, `source_title`, `source_type`, `similarity`, `bm25_score`, `bm25_norm`, `rrf_score`, `rrf_rank`, `entity_linked`, `memory_context`, `tags`, `frame`, `authorship`, `text` | `trace.py:25-44,71` |
| `retrieved_context` | the hierarchy-enriched text block (not what the drafter saw) | `trace.py:72` |
| `profile_snapshot` | the whole profile | `trace.py:73` |
| `node_outputs` | see below | `trace.py:74-89` |
| `llm_calls` | per call: `event_type`, `model`, `input_tokens`, `output_tokens`, `thinking_tokens`, `stop_reason`, `latency_ms` | `llm/client.py:154-164`, `trace.py:90` |
| `score`, `iterations`, `archetype` | final values (score 0 unless pipeline A in `polished`) | `trace.py:91-93` |
| `eval_status` | default `pending` | **nothing sets it** (section 3.9) |

`node_outputs` keys always present (`trace.py:74-87`): `variant`, `no_specifics`, `length_target`, `perspective`, `archetype_decision`, `draft_frame_block`, `draft_history`, `critic_brief`, `score_history`, `specifics_guard`, `coverage_gate`, `fact_check`, `final_post` [V].

Keys present only when the run set them (`trace.py:50-53,88`): `models`, `source_index`, `event`, `citations`, `citation_failures`, `multi_sentence_spans`, `draft_format`, `draft_truncated`, `draft_refused`, `draft_empty`, `compress_result`, `checks_before_trim`, `checks_final`, `review_first`, `review_second`, `review`, `step_timings`, `final_validation` [V].

Keys added after the run by updates: `fact_check` (log-only result, `memory/trace_store.py:86-88`), `refine_selection` (list, `:91-99`), `specifics_guard` entries from a legacy refine (`:102-109`) [V]. Each update reads the JSON, changes it in Python and writes it back (`trace_store.py:60-83`) [V].

`trim_result` is declared in state but no longer set (`pipeline/state.py:116-118`) [V].

---

## 10. Observability and cost

### 10.1 `usage_events`

One row per `complete()` call: `user_id`, `event_type`, `input_tokens`, `output_tokens`, `estimated_cost_usd`, `model`, `metadata`, `created_at` (`000_baseline_schema.sql:360-369`, `006_add_usage_model.sql:3`, `backend/memory/usage_store.py:58-66`) [V].

- Written by a direct REST POST with the service-role key, fire-and-forget, scheduled onto the server's event loop from worker threads (`usage_store.py:21-39,84-109`) [V].
- A failed insert logs a warning and is dropped; a model with no price logs a warning and writes no row (`usage_store.py:34-39,52-55,68-69`) [V].
- `metadata` is `{topic, format, archetype}` for drafter and compress calls, and `{count, topic, kb_chunks}` for ideas (`agents/draft_agent.py:46-51`, `agents/ideation_agent.py:297`) [V].
- `event_type` values in the code: `generate`, `generate_retry`, `archetype`, `compress`, `targeted_fix`, `redraft`, `review`, `critic`, `humanize`, `humanize_retry`, `predictability_audit_step1/2/3` (with retry suffixes), `word_count_enforcer`, `word_count_enforcer_retry`, `fact_check`, `fact_check_rewrite`, `fact_check_recheck`, `score`, `refine_selection`, `refine_selection_retry`, `visual_svg`, `ideation`, `resume_extract`, `vision_extract`, `ingest_tags`, `ingest_summary`, `ingest_entities`, `memory_context_classify`, `consolidation`, `trim`, `eval_judge` [V, from the `event_type=` arguments in `backend/agents/`, `backend/routers/profile.py`, `evals/eval_config.py:14`].

### 10.2 `user_events`

`user_id`, `event_type` (`page_view`, `button_click`, `feature_start`, `feature_complete`, `feature_abandon`), `page_url`, `button_name`, `metadata`, `timestamp` (`000_baseline_schema.sql:376-385`, `backend/routers/analytics.py:22-26`) [V]. Sent by `useTracking().logEvent` (`frontend/lib/useTracking.ts:24-39`); a page view is logged on every path change (`frontend/components/AppShell.tsx:18-23`) [V].

### 10.3 Logging

- Python `logging` at `LOG_LEVEL` (default INFO) to the process output (`backend/main.py:11-12`) [V]. There is no log shipping, metrics or error-tracking integration in the repository [V].
- Request user ids, profile names, the first 200 characters of resume text, and topic and chunk excerpts are logged (`backend/routers/profile.py:22-29,131,143`, `backend/agents/retrieval_agent.py:343,410`) [V]. `/refine-selection` logs only the exception class (`backend/routers/generate.py:250-251`) [V].
- Some modules use `print` (`backend/agents/retrieval_agent.py:362,364,410`) [V].
- The frontend logs profile-save status to the browser console (`frontend/lib/api.ts:403-406`) [V].

### 10.4 Admin and user views

- `/admin` reads `GET /admin/usage`, which loads every `usage_events` row and aggregates in Python (`backend/routers/admin.py:31-37`) [V]. It shows calls and cost today, this week and all time, a 14-day chart and per-user totals; it does not break down by model or event type (`admin.py:34,83-97`) [V].
- `/admin/analytics` reads `GET /admin/analytics-data`, which loads all `user_events` in the window and aggregates in Python (`backend/routers/analytics.py:68-74`) [V]. "Retention" is the count of users with 1, 2 and 5 or more `generate_btn` clicks (`analytics.py:254-271`) [V].
- `/settings` shows the user's own totals from `GET /usage/me`, including "API cost to date" (`frontend/app/settings/page.tsx:132,451`) [V].
- Feedback goes to `DATA_DIR/feedback.jsonl` and, when configured, a Telegram chat (`backend/routers/feedback.py:24-44,59-66`) [V]. No page reads the file.

### 10.5 What is and is not recorded

| Recorded | Not recorded |
|---|---|
| Tokens, cost, model and event type per Claude call | Request latency per endpoint; Claude latency outside pipeline traces |
| Full trace per pipeline run, including runs that produced no post | Any trace for ingest, ideas, scoring, visuals or resume extraction (usage events only) |
| Every refine attempt on a single-writer post | Refine attempts on legacy posts, except a guard retry |
| Deterministic check results per post | Whether the user edited, kept or published a sentence (only final content and versions) |
| Retrieval scores per chunk used | Chunks that were retrieved and filtered out; retrieval errors (they become empty results) |
| Per-step wall time, variant B only (`pipeline/single_writer.py:78-86`) | Per-step wall time under C-Opus |
| Entity extraction usage events | Entity extraction calls in any trace (`llm/client.py:79-82`) |

All [V] from the cited code; the "not recorded" column states the absence of any such write in the files read.

---

## 11. Infrastructure

| Item | Fact | Source |
|---|---|---|
| Frontend host | Vercel; production URL `contendo-six.vercel.app` | `CLAUDE.md:4`, `extension/manifest.json:9` |
| Frontend config | no `vercel.json`; `next.config.mjs` is an empty config | `frontend/next.config.mjs:1-4` |
| Backend host | Railway, Docker; production URL `contendo-production.up.railway.app` | `CLAUDE.md:4`, `extension/background.js:16` |
| Backend image | `python:3.11-slim`; CPU-only `torch==2.2.2` installed first; `CMD uvicorn main:app --host 0.0.0.0 --port $PORT` (one process, no `--workers`) | `backend/Dockerfile:1,20-22,41` |
| Railway config | `buildTimeout = 1800` and nothing else | `backend/railway.toml:1-2` |
| Embedding model | downloaded from Hugging Face on first use, not baked into the image | `README.md` section "Backend Deployment to Railway" (first cold-start note) |
| Disk | `DATA_DIR=/data` in the image; the code writes only `feedback.jsonl` there | `backend/Dockerfile:34`, `backend/config/paths.py:22-29`, `backend/routers/feedback.py:59-61` |
| Supabase projects | production, and `contendo-dev` for evals ("same schema as production via `000_baseline_schema.sql`") | `evals/README.md:3-5` |
| Migrations | SQL files run by hand in the Supabase SQL editor; no migration runner | `backend/migrations/005_generation_traces.sql:23`, `README.md` (Railway section) |
| In-process state | BM25 index per user, JWKS cache, the embedding model, five compiled graphs | `memory/vector_store.py:48-50`, `auth/supabase_jwt.py:26-30`, `pipeline/graph.py:209` |

**Deploy flow.** The repository contains no deploy scripts or workflow files. The README describes connecting Railway and Vercel to the GitHub repository with root directories `backend/` and `frontend/` (`README.md`, "Production Deployment" sections 2 and 5) [V]. Recent history shows merges of pull requests into `main` (`git log`: "Merge pull request #150 …") [V]. That each merge deploys automatically is [I].

**CI checks.** There is no `.github/` directory and no CI configuration [V]. Checks that exist:

| Check | Trigger | Source |
|---|---|---|
| Secret scan (Anthropic key and JWT shapes) on staged files | `pre-commit` hook, active only after `git config core.hooksPath scripts/git-hooks` | `scripts/git-hooks/pre-commit:1-48` |
| Backend `pytest` | `pre-push` hook, same opt-in; skipped when `backend/venv` is missing | `scripts/git-hooks/pre-push:1-30` |
| Backend tests | 47 test files, in-memory fakes for Supabase, Claude and the embedder | `backend/tests/`, `backend/tests/conftest.py` |
| Eval tests | 5 test files, no network | `evals/tests/` |
| Frontend tests | 4 vitest files; `npm test` | `frontend/package.json:9`, `frontend/lib/*.test.ts`, `frontend/app/first-post/page.test.tsx` |
| Vercel build | `next build` on deploy [I] | `README.md` ("Vercel runs `npm run build` automatically") |

**Environment variable names per service** (names only; from code):

| Service | Names | Source |
|---|---|---|
| Backend | `ANTHROPIC_API_KEY`, `SUPABASE_URL`, `SUPABASE_SERVICE_ROLE_KEY`, `SUPABASE_JWT_SECRET`, `ADMIN_USER_IDS`, `ENVIRONMENT`, `ALLOW_DEV_AUTH`, `ALLOW_LOCAL_PATH_INGEST`, `FRONTEND_ORIGIN`, `DATA_DIR`, `LOG_LEVEL`, `PIPELINE_VARIANT`, `SUPADATA_API_KEY`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `PORT` | `evals/guard.py:44-61`, `backend/Dockerfile:37` |
| Backend (named only in a docstring) | `TAVILY_API_KEY` | `backend/tools/scraper_tool.py:69-76` |
| Frontend | `NEXT_PUBLIC_API_URL`, `NEXT_PUBLIC_SUPABASE_URL`, `NEXT_PUBLIC_SUPABASE_ANON` | `frontend/lib/api.ts:5`, `frontend/lib/supabase.ts:4-5` |
| Evals | `EVAL_SUPABASE_URL`, `EVAL_SUPABASE_SERVICE_ROLE_KEY`, `ANTHROPIC_API_KEY`, `EXPECTED_PROJECT_REF`; optional `LOG_LEVEL`, `SUPABASE_JWT_SECRET`, `PIPELINE_VARIANT` | `evals/guard.py:30-37` |
| Extension | none; the API base URL, the web origin and the extension id are constants | `extension/background.js:16`, `extension/popup.js:18`, `frontend/hooks/useProfileCheck.ts:10` |

**Scheduled jobs.** None. There is no cron, queue or scheduler in the repository [V]. Deferred work is limited to: FastAPI `BackgroundTasks` for the log-only fact check (pipeline A only), `asyncio.create_task` for user events and Telegram, and the 300-second BM25 cache expiry (`backend/routers/generate.py:189-190`, `backend/routers/analytics.py:53`, `backend/routers/feedback.py:63-65`, `backend/memory/vector_store.py:45`) [V].

---

## 12. Every `STOPGAP` comment

Seventeen comments in code carry the label; all are in `backend/`. A search of `frontend/`, `extension/`, `evals/` and `scripts/` found none [V].

| # | File:line | What it says | Proper fix named |
|---|---|---|---|
| 1 | `backend/pipeline/graph.py:239` | Variant B's review summary is not shown by the frontend | `feat/citations-ui`: expose per-sentence citations and recorded check and review results |
| 2 | `backend/pipeline/compress.py:54` | Structural checks on a compress replacement do not verify meaning: stance can change, a name or event can be added | semantic verification of each replacement against its original (`eval/faithfulness-judge`) |
| 3 | `backend/pipeline/compress.py:79` | Money keys omit currency identity, so equal amounts in different currencies compare equal | structured money extraction (amount + currency) |
| 4 | `backend/agents/retrieval_agent.py:341` | Topic excerpts are logged | `fix/retrieval-failure-status`: request ids, categories and counts instead of content |
| 5 | `backend/agents/retrieval_agent.py:370` | A failed fallback query becomes empty results and low coverage | `fix/retrieval-failure-status`: record retrieval errors and return an explicit failure |
| 6 | `backend/agents/retrieval_agent.py:406` | Source excerpts are logged | `fix/retrieval-failure-status` |
| 7 | `backend/agents/humanizer_agent.py:41` | A regex on model prose guesses which part of a critic fix is a worked example | none here; removed with pipeline A (`chore/remove-pipeline-a`) |
| 8 | `backend/agents/draft_prompt.py:153` | Prompt-only relationship checks cannot prove source attribution | an independent faithfulness judge, plus `feat/citations-ui` |
| 9 | `backend/utils/formatters.py:287` | The style rules' phrase examples are shared with frozen pipeline A | a description-based style block when A is removed |
| 10 | `backend/agents/fact_check_agent.py:217` | Normal-mode fact check is log-only because the find-prompt over-flags paraphrases | citation-based drafting plus verification against the cited chunk |
| 11 | `backend/agents/fact_check_agent.py:285` | Removing one sentence can orphan the next | citation-based drafting |
| 12 | `backend/utils/specifics.py:60` | The currency suffix list is open-ended; unlisted currencies are checked only as bare numbers | structured extraction of money, dates and durations |
| 13 | `backend/utils/specifics.py:70` | The "time" phrases are an open-ended list; other wordings are not seen | the same structured extraction |
| 14 | `backend/utils/frames.py:56` | Seniority is guessed from keywords matched as substrings of the role title | `years_of_experience`, or an explicit seniority field at onboarding |
| 15 | `backend/utils/frames.py:115` | "In the author's field" is decided by substring overlap of profile topics and chunk tags | decide it at ingest, semantically, and store it (`fix/ingest-attribution`) |
| 16 | `backend/utils/frames.py:207` | The source title is not shown to the model, because stored metadata does not say whether a title is real or derived | record `title_origin` at ingest, migrate and backfill (`fix/ingest-attribution`) |
| 17 | `backend/utils/frames.py:337` | Reaction and generalisation restrictions are prompt-only | an independent faithfulness judge, plus `feat/citations-ui` |

Two further comments refer to these without adding one: `backend/agents/archetype_agent.py:93` (to #16) and `backend/agents/fact_check_agent.py:24` (to #10) [V]. Tests document #3 and #16 (`backend/tests/test_compress_review.py:91-92`, `backend/tests/test_perspective_frames.py:58`) [V].

---

## 13. Known bugs, and dead or unwired code

### 13.1 Bugs and limits recorded in `docs/plans/single-writer.md` and the code

| # | Recorded issue | Source |
|---|---|---|
| 1 | A retrieval error is reported as low coverage: a Supabase disconnect gated golden ds-09 as if memory did not cover the topic | `docs/plans/single-writer.md:57`; `backend/agents/retrieval_agent.py:370-374` |
| 2 | The author's own notes are stored with an external frame (four recorded occurrences), producing "an article on … suggests" for the author's own practice; the review cannot catch it | `docs/plans/single-writer.md:60` |
| 3 | Ingest labels any text that names an employer or project as the user's own work | `CODEBASE.md` section 6 ("audit I1"); `backend/agents/ingestion_agent.py:258-292` |
| 4 | Golden pm-04 is blocked by the coverage gate although memory covers it (cosine 0.24, BM25 0.09) | `evals/README.md:159-166` |
| 5 | The archetype choice picked `before_after` in 13 of 16 drafted posts with a self-authored note | `CODEBASE.md` section 6 |
| 6 | The `teach_me_something` structure asks for an analogy, so the drafter invents one | `docs/plans/single-writer.md:65` |
| 7 | Compress can change stance or add a name; nothing in code stops a replacement from adding a name | `docs/plans/single-writer.md:336,338`; stopgap #2 |
| 8 | The sentence-level read with sources found unsupported sentences and wrong attributions in C-Opus and B-Opus posts | `docs/plans/single-writer.md:578` |
| 9 | Trim by deletion reversed a post's meaning in production (trace `fb714878-…`); replaced by compress | `docs/plans/single-writer.md:330` |
| 10 | Pipeline A: `word—word` is one token before normalisation and two after, so a 100-word post becomes 101 | `docs/plans/single-writer.md:104` |
| 11 | Pipeline A measures length with `count_words`, which counts placeholder lines | `docs/plans/single-writer.md:59` |
| 12 | Pipeline A's enforcer swallows every exception and never checks that its output met the target | `docs/plans/single-writer.md:102` |
| 13 | Past production Haiku costs were logged at a quarter of the real price | `docs/plans/single-writer.md:543` |
| 14 | Flaky test `test_repeated_unknown_kids_do_not_refetch_within_cooldown` (about one failure in twelve) | `docs/plans/single-writer.md:58` |
| 15 | `off_topic` raised a likely false positive on a closing question (variant B) | `docs/plans/single-writer.md:319` |
| 16 | The check matcher passes a bare number against any figure of that value in the cited source ("41 meetings" against "41 percent") | `docs/plans/single-writer.md:199` |
| 17 | The pydantic pin (2.10.3) is below what `deepeval` and current Supabase packages need | `docs/plans/single-writer.md:56` |
| 18 | Shared prompt blocks themselves contain em dashes | `docs/plans/single-writer.md:72`; `backend/utils/formatters.py:341`, `backend/agents/draft_prompt.py:207` |
| 19 | The plan's status line says the independent-review fixes were "built in scratch pending Soham's apply; no production migration has been run" | `docs/plans/single-writer.md:9` |

There are no `xfail` tests and `KNOWN_UNPROTECTED` is empty (`backend/tests/test_endpoint_auth_coverage.py:19`) [V].

### 13.2 Dead or unwired code

"Unreferenced" means a search of `backend/`, `evals/`, `scripts/` and `frontend/` outside tests found only the definition.

| Item | Evidence |
|---|---|
| `backend/agents/trim_agent.py` (`trim_node`) | its own header says "UNUSED" (`:1-5`); referenced only by tests (`backend/tests/test_trim.py:72`, `test_finalise.py:136`) [V] |
| Pipeline A's modules (`critic_agent`, `humanizer_agent`, `predictability_audit_agent`, `word_count_enforcer_agent`, `fact_check_agent`, the scorer loop) | wired only into graph A (`backend/pipeline/graph.py:134-169`); not run under the default [V] |
| Variant B's modules (`review_agent`, `review_prompt`, `redraft_prompt`, `pipeline/fixes.py`, `redraft.py`, `review_rules.py`, `review_validation.py`) | wired only into graph B (`backend/pipeline/single_writer.py:104-155`); exceptions: `issue_entries`, `format_problems`, `NEVER_ADD` and `QUOTED_MATERIAL` are used by the cited refine (`agents/refine_cited_agent.py:21`, `agents/refine_prompt.py:14`) [V] |
| No-specifics mode | flag off (`backend/config/features.py:11`); `/generate` rejects it (`routers/generate.py:164-169`); the frontend buttons render only when the flag is on (`frontend/components/LowCoverageNotice.tsx:71`) [V] |
| `_format_retrieved_context`, `source_contexts`, `topic_contexts`, sibling-chunk lookup | computed every run (`agents/retrieval_agent.py:98-246,348-350`); no prompt reads them (section 6.5) [V] |
| `state["retrieved_chunks"]` | set "for backward compat" (`retrieval_agent.py:379-389`); read as a fallback by pipeline A's prompt and by `has_chunks` (`agents/draft_prompt.py:184,212`) [V] |
| `state["experience_nodes"]` | loaded every run; read only by pipeline A's fact check (section 3.5) [V] |
| `vector_store.init_chroma` | no-op, unreferenced (`backend/memory/vector_store.py:74-76`) [V] |
| `vector_store.get_chunks_for_source` | unreferenced (`:663-686`) [V] |
| `vector_store.query_similar_batch` | computes a batch of embeddings and does not use them; each query is embedded again (`:208-212`) [V] |
| `feedback_store.get_best_version`, `feedback_store.restore_version` | unreferenced (`backend/memory/feedback_store.py:202-242`); the restore endpoint uses `update_post` (`routers/history.py:179-184`) [V] |
| `feedback_store.init_retrieval_stats_db`, `increment_retrieval`, `get_retrieval_counts` | duplicates of `memory/retrieval_stats_store.py`; callers import the latter (`agents/retrieval_agent.py:15`, `routers/library.py:6`) [V] |
| `init_db`, `init_hierarchy_db`, `init_retrieval_stats_db` | no-ops called at startup (`backend/main.py:59-61`) [V] |
| `entity_store.get_entity_names_for_user`, `get_entities_for_chunk` | unreferenced (`backend/memory/entity_store.py:161-200`) [V] |
| `experience_store.get_experience_nodes_by_type`, `delete_experience_node` | unreferenced (`backend/memory/experience_store.py:101-137`) [V] |
| `hierarchy_store.get_sources_for_user` | unreferenced (`backend/memory/hierarchy_store.py:70-82`) [V] |
| `consolidation_store.get_all_consolidation_chunks`, `delete_consolidation_chunk`; `get_consolidation_chunk` | first two unreferenced; the third is imported and never called (`agents/consolidation_agent.py:24`) [V] |
| `utils.specifics.grounding_texts` | referenced only by tests and a docstring (`backend/utils/specifics.py:254,349`) [V] |
| `config/paths.py`: `CHROMA_DIR`, `POSTS_DB_PATH`, `HIERARCHY_DB_PATH`, `PROFILE_PATH`, `PROFILES_DIR` | defined; only `FEEDBACK_PATH` is imported (`routers/feedback.py:12`) [V] |
| `requirements.txt`: `chromadb`, `asyncpg`, `Pillow` | no import of `chromadb`, `asyncpg` or `PIL` in `backend/`, `evals/` or `scripts/` (`backend/requirements.txt:6,11,19`) [V] |
| `/obsidian/preview` and `/obsidian/ingest` | return 403 unless `ALLOW_LOCAL_PATH_INGEST=1` (`routers/ingest.py:25-29`) [V] |
| `IngestRequest.content_origin` | sent only by the extension (section 4.3) [V] |
| Request field `quality` | accepted and stored in the trace; no effect under C or C-Opus; never sent by the frontend (sections 1.5, 7.2) [V] |
| Response fields `score`, `score_feedback`, `iterations`, `scored`, `review` | constant under C-Opus (section 7.2) [V] |
| `/onboarding` page body | unreachable after the redirect (`frontend/app/onboarding/page.tsx:82-142`) [V] |
| `/sso-callback` | legacy Clerk target (`frontend/app/sso-callback/page.tsx:11-13`) [V] |
| `scripts/migrate_to_supabase.py`, `scripts/migrate_hierarchy.py` | one-off scripts; the second creates its own Anthropic client and model string (`scripts/migrate_hierarchy.py:47-56`) [V] |
| `frontend/components/ReviewNotice.tsx`, `evals/review_cases.py` | named in the plan (`docs/plans/single-writer.md:442,444`); neither file exists [V] |
| Columns | section 3.9 |

---

## 14. Size hotspots

### 14.1 Source files over 400 lines

Tracked files, line counts from `wc -l`; tests, lock files, snapshots and markdown excluded.

| Lines | File |
|---|---|
| 2,731 | `frontend/components/CreatePost.tsx` |
| 1,806 | `frontend/app/first-post/page.tsx` |
| 1,465 | `frontend/components/FeedMemory.tsx` |
| 905 | `frontend/app/library/page.tsx` |
| 876 | `frontend/app/history/page.tsx` |
| 785 | `backend/migrations/000_baseline_schema.sql` |
| 778 | `frontend/app/welcome/page.tsx` |
| 757 | `backend/memory/vector_store.py` |
| 662 | `frontend/app/admin/analytics/page.tsx` |
| 624 | `frontend/app/settings/profile/page.tsx` |
| 513 | `frontend/app/settings/page.tsx` |
| 506 | `frontend/app/history/[id]/page.tsx` |
| 481 | `frontend/app/ideas/page.tsx` |
| 455 | `backend/routers/ingest.py` |
| 440 | `frontend/app/onboarding/page.tsx` |
| 439 | `backend/agents/ingestion_agent.py` |
| 417 | `frontend/lib/api.ts` |
| 412 | `backend/agents/retrieval_agent.py` |

Test files over 400 lines: `backend/tests/test_fabrication_regressions.py` (552), `evals/tests/test_ablation.py` (484), `backend/tests/test_review.py` (476), `backend/tests/test_generation_trace.py` (450), `backend/tests/test_checks.py` (405). Reference documents: `PROMPTS.md` (1,897), `CODEBASE.md` (1,243), `README.md` (539).

### 14.2 Functions over 80 lines

Python, measured with the `ast` module over tracked `.py` files:

| Lines | Location | Function |
|---|---|---|
| 227 | `backend/routers/analytics.py:58` | `get_analytics_data` |
| 148 | `backend/agents/ideation_agent.py:153` | `generate_suggestions` |
| 133 | `evals/run.py:87` | `main` |
| 130 | `backend/routers/profile.py:62` | `extract_resume` |
| 128 | `backend/pipeline/graph.py:212` | `run_pipeline` |
| 120 | `backend/agents/ingestion_agent.py:320` | `ingest_content` |
| 114 | `evals/judge.py:41` | `main` |
| 95 | `backend/agents/word_count_enforcer_agent.py:52` | `word_count_enforcer_node` |
| 94 | `scripts/migrate_hierarchy.py:110` | `migrate` |
| 94 | `evals/reporting.py:89` | `build_report` |
| 92 | `backend/agents/review_agent.py:245` | `review_post` |
| 92 | `backend/agents/retrieval_agent.py:321` | `retrieval_node` |
| 89 | `backend/agents/trim_agent.py:89` | `trim_node` |

TypeScript, measured with the TypeScript compiler's parser over tracked `.ts` and `.tsx` files (named functions only; React components include their JSX):

| Lines | Location | Function |
|---|---|---|
| 2,061 | `frontend/components/CreatePost.tsx:671` | `CreatePost` |
| 1,286 | `frontend/components/FeedMemory.tsx:180` | `FeedMemory` |
| 937 | `frontend/app/first-post/page.tsx:862` | `FirstPostContent` |
| 687 | `frontend/app/welcome/page.tsx:92` | `WelcomePage` |
| 486 | `frontend/app/settings/profile/page.tsx:139` | `ProfileSettingsPage` |
| 472 | `frontend/app/admin/analytics/page.tsx:191` | `AnalyticsDashboard` |
| 446 | `frontend/app/settings/page.tsx:68` | `SettingsHubPage` |
| 380 | `frontend/app/history/page.tsx:146` | `PostCard` |
| 364 | `frontend/app/onboarding/page.tsx:77` | `OnboardingPage` |
| 358 | `frontend/app/library/page.tsx:548` | `LibraryPage` |
| 353 | `frontend/app/history/[id]/page.tsx:154` | `PostDetailPage` |
| 328 | `frontend/app/first-post/page.tsx:460` | `ProfileGate` |
| 323 | `frontend/app/ideas/page.tsx:159` | `IdeasPage` |
| 263 | `frontend/app/history/page.tsx:614` | `HistoryPage` |
| 249 | `frontend/lib/api.ts:169` | `useApi` |
| 248 | `frontend/app/library/page.tsx:297` | `TopicMapView` |
| 235 | `frontend/components/OnboardingIntercept.tsx:82` | `OnboardingIntercept` |
| 193 | `frontend/components/Sidebar.tsx:75` | `Sidebar` |
| 170 | `frontend/components/CreatePost.tsx:250` | `DiagramBlock` |
| 163 | `frontend/app/library/page.tsx:114` | `SourceCard` |
| 146 | `frontend/components/CreatePost.tsx:522` | `SettingsDrawer` |
| 145 | `frontend/app/sign-up/[[...sign-up]]/page.tsx:9` | `SignUpPage` |
| 125 | `frontend/app/sign-in/[[...sign-in]]/page.tsx:9` | `SignInPage` |
| 108 | `frontend/components/FeedMemory.tsx:554` | `handleSubmit` |
| 100 | `frontend/app/admin/page.tsx:194` | `AdminPage` |
| 98 | `frontend/components/ui/FeedbackButton.tsx:12` | `FeedbackModal` |
| 97 | `frontend/components/LowCoverageNotice.tsx:11` | `LowCoverageNotice` |
| 88 | `frontend/app/first-post/page.tsx:368` | `DraftScreen` |
| 88 | `frontend/app/first-post/page.tsx:1079` | `handleGenerate` |
| 82 | `frontend/components/AppShell.tsx:12` | `AppShell` |

---

## 15. Open questions

Places where the code is ambiguous, or where code and documents disagree. Each is stated as the two facts that conflict.

### 15.1 Code that cannot be settled by reading

| # | Question | The facts |
|---|---|---|
| 1 | Do `source_nodes` and `topic_nodes` in the live databases match the code or the baseline file? | The code writes columns the baseline schema does not have and upserts on a column with no unique constraint (section 3.6). Failures are swallowed on both the write and the read path. `evals/README.md:3-5` says the eval project was built from the baseline file. If the tables match the file, every hierarchy write fails silently and one Haiku summary call per ingest is spent on a row that is not stored [I]. |
| 2 | Has `006_add_usage_model.sql` been applied in production? | The usage writer always sends `model` (`backend/memory/usage_store.py:64`); a failed insert only logs a warning (`:34-39`). The plan says no production migration has been run (`docs/plans/single-writer.md:9`) and that the migration must be applied before deploying (`:627`). Commit `24ceec4` is on `main`. |
| 3 | What is `PIPELINE_VARIANT` set to on Railway? | The code default is `C-Opus`; the plan says the variable is unset in production (`docs/plans/single-writer.md:354`). Not verifiable from the repository. |
| 4 | Can the dev-auth user save anything? | `DEV_USER_ID` is the string `"default"` (`backend/auth/supabase_jwt.py:19`); `posts.user_id` and `profiles.id` are `uuid` columns with foreign keys to `auth.users` (`000_baseline_schema.sql:209,249,690-699`). |
| 5 | Which consolidations actually trigger? | Just-extracted names are compared raw against normalised stored names (section 4.5), so an entity written as "React.js" does not match its stored form "react" [I]. |
| 6 | What does an "opinion" first post see? | The structure step is given no chunks under the `opinion` perspective (`backend/agents/archetype_agent.py:113,197`), but the draft prompt builds its sources block from the bundle regardless of perspective (`backend/agents/draft_prompt.py:340-341`), and the bundle can hold entity-linked chunks when nothing passed the relevance filter (`backend/agents/retrieval_agent.py:345-347`). |
| 7 | Where should the first-post "feed memory" button go? | The handler and prop are named for Feed Memory (`frontend/app/first-post/page.tsx:1292`), and the destination is `/`, the welcome page (`:1211,1237,1243`). |
| 8 | Is the profile `bio` meant to be the first-post experience detail? | `buildMergedProfile` stores the sentence typed as "specific context" for one post as the profile's bio (`frontend/app/first-post/page.tsx:1049`). |
| 9 | Do async handlers block the event loop? | Several `async` handlers call the synchronous Supabase client directly, for example `GET /history` with one versions query per post (`backend/routers/history.py:49-62`), `GET /library` (`backend/routers/library.py:15-25`), and the `/log-event` insert inside a task (`backend/routers/analytics.py:31-40`). The server runs one worker (`backend/Dockerfile:41`). `CLAUDE.md` names only Claude calls and ingestion as slow sync code. |
| 10 | Is `docs/architecture/as-is.md` meant to be shared? | `.gitignore:73` ignores `docs/` ("Local planning docs (never pushed)"), so this file and `docs/plans/single-writer.md` are untracked. |

### 15.2 Code versus documents

| # | Document says | Code says |
|---|---|---|
| 1 | `.claude/rules/backend-agents.md` (pipeline order bullet) and `README.md:135-146` describe the pipeline as draft → critic → humanizer → audit → scorer → enforcer | the default pipeline is C-Opus (`backend/config/features.py:34`) |
| 2 | `CLAUDE.md` "Rules": models are `claude-sonnet-4-6` for generation and `claude-haiku-4-5-20251001` for classification | the default drafter is `claude-opus-5-5` (`backend/llm/models.py:16,71-74`) |
| 3 | `CODEBASE.md` section 5: "Retrieval confidence calibration — always generate, never block" | the coverage gate ends the run with `low_coverage` (`backend/pipeline/graph.py:91-100`) |
| 4 | `CODEBASE.md` section 5: the default quality "standard runs 1 critic pass + 1 humanizer pass"; "Scorer runs lazily … the graph routes humanizer → finalize" | under the default no node reads `quality` (section 7.2); graph A routes audit → enforcer → fact check → finalize (`backend/pipeline/graph.py:150-168`) |
| 5 | `CODEBASE.md` section 6: "YouTube transcript auto-fetching (removed — manual paste only)" | `POST /fetch-youtube-transcript` exists and the YouTube tab calls it (`backend/routers/ingest.py:274`, `frontend/components/FeedMemory.tsx:600`) |
| 6 | `CODEBASE.md` section 6: "Multi-format regeneration (regenerate always uses same format/tone)" is not built | the Regenerate drawer accepts a new topic, format, tone, length and context (`frontend/components/CreatePost.tsx:519,658`) |
| 7 | `CODEBASE.md` section 4, `embeddings`: `node_type` is `chunk`; `source_type` lists six values | consolidation rows use `node_type` and `source_type` `consolidation` (`backend/memory/consolidation_store.py:43,48`) |
| 8 | `CODEBASE.md` section 4, `generation_traces.llm_calls`: `[{event_type, model, input_tokens, output_tokens, latency_ms}]`; migration `005` comment says the same | entries also carry `thinking_tokens` and `stop_reason` (`backend/llm/client.py:156-164`) |
| 9 | `005_generation_traces.sql:12`: "similarity is a fixed 0.35 for BM25-only and entity-linked chunks" | both get their real cosine (`backend/memory/vector_store.py:380-396`, `backend/agents/retrieval_agent.py:307`) |
| 10 | `CODEBASE.md` section 4, profile: `linkedin_style_notes` and the other two are "format-specific style notes"; `words_to_avoid` is "injected into humanizer prompt" | the style-notes fields reach no prompt; `words_to_avoid` reaches the draft, refine and humanizer prompts and a code check (section 5.3) |
| 11 | `profile_to_context_string` docstring: used for "idea suggestions, selection refine" (`backend/memory/profile_store.py:152-153`) | selection refine uses `profile_voice_context` (`backend/agents/refine_agent.py:237`, `backend/agents/refine_cited_agent.py:44`) |
| 12 | `backend/utils/formatters.py:109-110` (`word_count_rule` docstring): "`word_count_enforcer_node` counts in code and trims or expands afterwards" | the enforcer runs only in graph A; under the default nothing expands (`backend/pipeline/finalise.py:21`) |
| 13 | `evals/run.py:6,91`: the default variant is "PIPELINE_VARIANT, else A" | `features.pipeline_variant()` defaults to `C-Opus` (`evals/run.py:116`, `backend/config/features.py:34`) |
| 14 | `evals/README.md:87`, `backend/config/retrieval.py:5`: 24 goldens | `evals/goldens/goldens.jsonl` has 27 lines; the plan says 27 (`docs/plans/single-writer.md:398`) |
| 15 | `evals/README.md:5-6`: "Running goldens and judging come later" | the same file documents run, judge, report and ablation commands (`evals/README.md:82-157`) |
| 16 | `README.md` Vercel section lists one variable, `NEXT_PUBLIC_API_URL` | the frontend also requires `NEXT_PUBLIC_SUPABASE_URL` and `NEXT_PUBLIC_SUPABASE_ANON` (`frontend/lib/supabase.ts:4-5`, `frontend/middleware.ts:28-29`) |
| 17 | `README.md` Railway variable table | omits `PIPELINE_VARIANT`, `TELEGRAM_BOT_TOKEN`, `TELEGRAM_CHAT_ID`, `LOG_LEVEL`, `ALLOW_LOCAL_PATH_INGEST` (`evals/guard.py:44-61`) |
| 18 | `.claude/rules/frontend.md`: all API calls go through `useApi()`; "`app/settings/page.tsx` still uses raw fetch" | still true: `fetch(\`${API}/usage/me\`)` (`frontend/app/settings/page.tsx:132`) |
| 19 | `.claude/rules/backend-data.md`: "don't query Supabase directly from routers" | `routers/admin.py:32-37`, `routers/stats.py:47-53` and `routers/analytics.py:34-40,68-74` query the client directly |
| 20 | `CLAUDE.md` "Rules": never create an `anthropic.Anthropic` client or write a model string outside `llm/` | `scripts/migrate_hierarchy.py:47-56` does both (a one-off script) |
| 21 | `frontend/lib/api.ts:164-168`: the backend "allows [no session] in non-production via the dev fallback" | the fallback depends on `ALLOW_DEV_AUTH=1` only, in any environment except `production` (`backend/config/security.py:39-45`) |
| 22 | Create page length hints: LinkedIn standard "~200-300 words", concise "~100-150", Medium long-form "~1200-1600" (`frontend/components/CreatePost.tsx:63-74`) | backend ranges: 250–350, 100–180, 1,200–1,800 (`backend/utils/formatters.py:52-63`) |
| 23 | Create page tone descriptions: Storytelling is "Scene-driven, lesson earned … Opens with a moment, builds tension" (`frontend/components/CreatePost.tsx:42,54`) | the backend's storytelling tone "does not license a scene, a moment or an event the sources don't describe" (`backend/utils/formatters.py:326-331`) |
| 24 | `CreatePost.tsx:81` types the response status without `draft_empty` | `frontend/lib/api.ts:58` and the backend include it (`backend/pipeline/graph.py:315`) |
| 25 | Plan section 9 lists `frontend/components/ReviewNotice.tsx` to be created, and section 6 describes a notice for `issues_remain` (`docs/plans/single-writer.md:341,444`) | no such component exists and the frontend ignores `review` (section 7.5) |
| 26 | `CLAUDE.md` "no cheap fixes": no global trigger-word lists | unlabelled keyword lists exist: diagram style by description keywords (`backend/agents/visual_agent.py:64-74`), challenge-page phrases (`backend/tools/scraper_tool.py:4-18`), BM25 stop words that include "first", "lesson" and "lessons" (`backend/memory/vector_store.py:221-233`), and classifier example phrases (`backend/agents/ingestion_agent.py:40-44`) |

---

Files created: `docs/architecture/as-is.md` (this file; the folder `docs/architecture/` was created for it, as requested). Two temporary measuring scripts were written to the session scratchpad outside the repository and deleted afterwards.

Stopgaps introduced: none.
