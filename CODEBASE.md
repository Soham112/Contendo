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
| `backend/main.py` | FastAPI app entry point — CORS config, lifespan hook (calls `init_db` + `init_hierarchy_db`), and router registration only (~40 lines) |
| `backend/routers/__init__.py` | Empty — marks routers/ as a Python package |
| `backend/routers/ingest.py` | `/ingest`, `/ingest-file`, `/scrape-and-ingest`, `/obsidian/preview`, `/obsidian/ingest` |
| `backend/routers/generate.py` | `/generate`, `/refine`, `/score`, `/generate-visuals` |
| `backend/routers/history.py` | `GET /history`, `POST /log-post`, `PATCH /history/{id}`, `DELETE /history/{id}`, `POST /history/{id}/restore/{vid}` |
| `backend/routers/library.py` | `GET /library`, `DELETE /library/source` |
| `backend/routers/ideas.py` | `GET /suggestions` |
| `backend/routers/stats.py` | `GET /stats` |
| `backend/routers/profile.py` | `GET /profile`, `POST /profile` — per-user profile read/write; returns `has_profile: bool` so frontend can detect new users needing onboarding |
| `backend/requirements.txt` | All Python dependencies pinned |
| `backend/.env.example` | Required env var template — `ANTHROPIC_API_KEY`, `DATA_DIR`, `FRONTEND_ORIGIN`, `ENVIRONMENT`, `CLERK_SECRET_KEY` |
| `backend/Dockerfile` | Production Docker image for Railway — Python 3.11-slim; pre-installs CPU-only `torch==2.2.2` from PyTorch CPU wheel registry (avoids 4 GB image limit); sentence-transformers model downloads at first request (not baked in); uses `$PORT` and `$DATA_DIR` |
| `backend/.dockerignore` | Excludes venv, pycache, local data files, .env from Docker build context |
| `backend/config/__init__.py` | Empty — marks config/ as a Python package |
| `backend/config/paths.py` | Single source of truth for all data paths; reads `DATA_DIR` env var, falls back to `backend/data/` for local dev; exposes `CHROMA_DIR`, `POSTS_DB_PATH`, `HIERARCHY_DB_PATH`, `PROFILE_PATH`, `PROFILES_DIR` |
| `backend/agents/ideation_agent.py` | Generates N content ideas from ChromaDB sample, profile, and posted topic history; accepts `user_id` param for per-user data isolation |
| `backend/auth/__init__.py` | Empty — marks auth/ as a Python package |
| `backend/auth/clerk.py` | Clerk JWT verification — `get_user_id(authorization)` verifies Bearer token via JWKS (1hr cache); falls back to `user_id="default"` in non-production when no token; `get_user_id_dep` is the FastAPI `Depends()` dependency used by all protected endpoints |
| `backend/agents/visual_agent.py` | Parses [DIAGRAM:] and [IMAGE:] placeholders from post; calls Claude to generate SVG for diagrams; returns reminder text for images |
| `backend/agents/ingestion_agent.py` | Chunks content, extracts tags via Claude Sonnet, upserts to ChromaDB; after successful upsert: generates a 2-3 sentence source summary via Claude Haiku and writes a source_node + topic_node to hierarchy_store (wrapped in try/except — never blocks ingestion); SHA-256 dedup via `query_by_hash()` before any Claude call |
| `backend/agents/vision_agent.py` | Sends base64 images to Claude vision, returns extracted text |
| `backend/agents/retrieval_agent.py` | Semantic search node in the LangGraph pipeline; builds a `retrieval_bundle` (chunks + source_contexts + topic_contexts) from hierarchy_store; sets `retrieved_context` (pre-formatted enriched text block) and always sets `retrieved_chunks` for backward compat; falls back to flat retrieval if hierarchy_store is empty |
| `backend/agents/draft_agent.py` | Calls Claude Haiku via `infer_archetype()` to classify the topic into one of 7 post archetypes, then generates the initial draft via Claude Sonnet; uses `_format_retrieval_context()` which prefers the enriched `retrieved_context` from state and falls back to flat `retrieved_chunks` |
| `backend/agents/critic_agent.py` | Diagnoses the initial draft across hook, substance, structure, and voice; produces a structured JSON brief; runs between `draft_node` and `humanizer_node`; uses Claude Haiku; skipped for draft quality mode |
| `backend/agents/humanizer_agent.py` | Rewrites draft to remove AI patterns, inject human voice; reads `critic_brief` from state and fixes flagged issues before humanizing if any area was rated "needs_work" |
| `backend/agents/scorer_agent.py` | Scores draft 0–100 across 5 dimensions, returns flagged sentences |
| `backend/pipeline/state.py` | TypedDict schema for shared LangGraph pipeline state; includes `archetype`, `user_id`, `critic_brief`, `retrieved_chunks` (backward compat flat list), `retrieval_bundle` (full hierarchical bundle), and `retrieved_context` (pre-formatted enriched text for draft prompt) |
| `backend/pipeline/graph.py` | LangGraph graph definition — nodes, edges, conditional retry loop |
| `backend/memory/vector_store.py` | ChromaDB init, upsert, semantic query, stats, delete_source, query_by_hash; `query_similar()` returns `source_id` and `chunk_index` per result; `query_similar_batch()` embeds all queries in a single batched forward pass then queries ChromaDB for each (significantly faster than N sequential `query_similar()` calls); `upsert_chunks()` stores `node_type:"chunk"`; `get_chunks_for_source()` and `get_adjacent_chunks()` for hierarchical sibling retrieval; collections namespaced as `contendo_{user_id}` |
| `backend/memory/profile_store.py` | Per-user profile read/write — `load_profile(user_id)`, `save_profile(profile, user_id)`, `profile_exists(user_id)`; legacy fallback to `data/profile.json` when `user_id="default"`; `DEFAULT_PROFILE` includes bio, location, target_audience, opinions, writing_samples; `profile_to_context_string()` formats all fields for prompt injection |
| `backend/memory/hierarchy_store.py` | SQLite store (path from `config.paths.HIERARCHY_DB_PATH`) for source_nodes and topic_nodes — `upsert_source_node`, `get_source_node`, `source_node_exists`, `upsert_topic_node`, `get_topic_node`, `find_matching_topic` (tag-overlap heuristic), `add_source_to_topic`; initialized in FastAPI lifespan |
| `backend/memory/feedback_store.py` | SQLite posts and post_versions tables — all functions accept `user_id` param for per-user isolation; `init_db()` runs idempotent `ALTER TABLE` migration to add `user_id` column; `_post_owned_by()` helper validates post ownership before version operations |
| `backend/tools/scraper_tool.py` | URL scraper using Jina Reader — `is_valid_url()`, `clean_scraped_text()`, `scrape_url()` |
| `backend/tools/obsidian_tool.py` | Obsidian vault reader — `read_vault()` yields cleaned note dicts, `get_vault_stats()` for preview, `clean_obsidian_markdown()` strips wikilinks/frontmatter/Dataview |
| `backend/tools/__init__.py` | Empty — tools directory retained for future use |
| `backend/utils/chunker.py` | 500-word chunks with 50-word overlap |
| `backend/utils/formatters.py` | Format + tone instruction strings per output type; `get_archetype_instructions()` returns structural prompt block for each of 7 post archetypes |
| `backend/utils/file_extractor.py` | Extracts plain text from PDF (PyMuPDF), DOCX (python-docx), and TXT files; raises ValueError on unsupported types, scanned PDFs, password-protected PDFs, and empty files |
| `backend/data/profile.json` | User voice and style profile — **gitignored**, never committed. Copy from `profile.template.json` to create. |
| `backend/data/profile.template.json` | Committed template with placeholder values — starting point for new users |
| `backend/data/chroma_db/` | ChromaDB persistent storage (gitignored) |
| `backend/data/posts.db` | SQLite post history (gitignored) |
| `backend/data/hierarchy.db` | SQLite hierarchy store — source_nodes + topic_nodes (gitignored) |
| `scripts/migrate_hierarchy.py` | One-time migration script: backfills hierarchy_store from existing ChromaDB data; idempotent; run with `python scripts/migrate_hierarchy.py [--dry_run] [--force] [--user_id default]` |
| `backend/venv/` | Python virtual environment (gitignored) |
| **Frontend** | |
| `frontend/app/layout.tsx` | Root layout — wraps body in `ClerkProvider`; mounts AppShell which renders Sidebar for app routes; `/welcome`, `/onboarding`, `/sign-in`, `/sign-up` bypass sidebar |
| `frontend/app/page.tsx` | Screen 1: Feed Memory (default route `/`) |
| `frontend/app/library/page.tsx` | Screen 2: Library (`/library`) — source cards, stats bar, text search, filter/sort; card placeholder areas use `getTitleGradient()` (deterministic charcode-sum gradient from `TITLE_GRADIENTS`) + `getSourceIcon()` (48px type-specific SVG illustrations: book/article, pencil/note, play/youtube, photo/image, layers/default) |
| `frontend/app/create/page.tsx` | Screen 3: Create Post (`/create`) |
| `frontend/app/ideas/page.tsx` | Screen 4: Get Ideas (`/ideas`) — standalone ideas screen with topic filter, count picker, save-for-later; ideas persisted in localStorage |
| `frontend/app/history/page.tsx` | Screen 5: Post History (`/history`) — searchable list, expandable post cards, version pills, restore, delete, diagram rendering |
| `frontend/app/history/[id]/page.tsx` | Post detail page (`/history/[id]`) — full-page view of a single post with version picker, restore, delete, diagram rendering |
| `frontend/app/welcome/page.tsx` | Landing page (`/welcome`) — editorial atelier marketing page; fixed glassmorphic nav with `font-headline italic` logo + CSS-only dropdowns + `btn-primary` CTA; hero with Noto Serif h1, feature cards, philosophy section, bento grid, `MOOD_GRADIENTS` staggered mood grid (8 tiles, charcode-deterministic), final CTA with dot-grid overlay; own top nav, AppShell sidebar suppressed |
| `frontend/app/globals.css` | Global styles — Tailwind directives, CSS custom properties for design tokens, `.btn-primary` gradient, `.glass` glassmorphism, `.font-headline`/`.serif-text`, grain texture overlay, custom scrollbar, `.input-editorial`, `.label-caps`, `.ghost-border` |
| `frontend/components/ui/ToastProvider.tsx` | Global custom lightweight React Context for floating success/error notifications |
| `frontend/components/AppShell.tsx` | Layout wrapper — renders Sidebar for all app routes; returns children unwrapped for `/welcome`, `/onboarding`, `/sign-in`, `/sign-up`; runs `useProfileCheck()` to redirect unauthenticated users or users without profiles to `/onboarding`; shows loading spinner while profile check is in flight |
| `frontend/components/Sidebar.tsx` | Left sidebar navigation — logo, six nav items (Feed Memory, Library, Create Post, Get Ideas, History, Settings), user row at bottom with real user avatar/name/email from `useUser()` and sign-out via `useClerk().signOut()` |
| `frontend/components/ui/TagInput.tsx` | Shared tag pill input component — used by onboarding and settings; accepts Enter/comma to add tags, Backspace to remove last, deduplicates; exports `TagInputProps` interface |
| `frontend/components/FeedMemory.tsx` | Feed Memory form — tabs (Article/Text, URL, File, YouTube, Image, Note, Obsidian), URL scraping, textarea, file upload with drag-and-drop, image upload, Obsidian vault preview/ingest flow, result display |
| `frontend/components/CreatePost.tsx` | Create Post — 4-state UI; dynamic autosave tracker; settings drawer; split-screen analysis panel. Pre-gen form: outlined "THE CENTRAL THEME" input, "FORMAT & MEDIUM" vertical pills, "VOICE & RESONANCE" horizontal pills, centered sparkle Generate button. Post-gen: "The Manuscript" Noto Serif heading + status pill, `whitespace-pre-wrap` textarea. Action buttons: three equal ghost buttons (Regenerate / Analyse / Gen.Visuals) + full-width `btn-primary` Copy. Analysis panel: SVG score ring (`stroke="#58614f"`), first `score_feedback` item as quote, remaining items as STRONG POINT/NEEDS ATTENTION focus cards, scrollable with `maxHeight:"50vh"` in stacked layout. |
| `frontend/middleware.ts` | Clerk v5 middleware — protects all routes except `/welcome`, `/sign-in(.*)`, `/sign-up(.*)`, `/onboarding` via `clerkMiddleware` + `createRouteMatcher` |
| `frontend/lib/api.ts` | `useApi()` hook — returns all typed API functions with Bearer token pre-attached via `useAuth().getToken()`; single source of truth for all backend calls; replaces raw `fetch()` in all components |
| `frontend/hooks/useProfileCheck.ts` | `useProfileCheck()` hook — runs after Clerk confirms auth, calls `GET /profile`, redirects to `/onboarding` if `has_profile === false`; no-op on public routes |
| `frontend/app/sign-in/[[...sign-in]]/page.tsx` | Clerk prebuilt `<SignIn />` page with Editorial Atelier wordmark (Noto Serif italic) and sage `#58614f` primary color |
| `frontend/app/sign-up/[[...sign-up]]/page.tsx` | Clerk prebuilt `<SignUp />` page, identical structure to sign-in page |
| `frontend/app/onboarding/page.tsx` | 5-step onboarding flow — collects name/role/bio/location, topics/audience, voice/words/rules, opinions, writing samples; uses shared `TagInput` component; posts to `POST /profile` on completion; redirects to `/` |
| `frontend/app/settings/page.tsx` | Profile editor at `/settings` — single-page (not stepped), all sections visible at once; loads via `GET /profile` on mount; sticky save button with amber dirty indicator; `beforeunload` guard; preserves `projects` field; Advanced section (collapsed) for technical/platform style notes |
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
| **Reads from state** | `profile`, `retrieved_chunks`, `topic`, `format`, `tone`, `context` |
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
  "hook":      { "verdict": "strong" | "needs_work", "fix": "instruction or null" },
  "substance": { "verdict": "strong" | "needs_work", "fix": "instruction or null" },
  "structure": { "verdict": "strong" | "needs_work", "fix": "instruction or null" },
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
  "has_profile": true
}
```
**Notes:** Returns the profile for the authenticated user. `has_profile` is `true` if the profile file exists and the `name` field is non-empty. `false` means the user has not completed onboarding. The profile is always returned (falling back to `DEFAULT_PROFILE`) regardless of `has_profile`.

---

### POST /profile
**Request body:** Full profile object (see profile.json schema below)
**Response:**
```json
{ "saved": true }
```
**Notes:** Saves the profile to `DATA_DIR/profiles/profile_{user_id}.json`. Creates the `profiles/` directory if it does not exist.

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
**Notes:** Ingests all vault notes via `read_vault()` → `ingest_content()` with `source_type="note"` and `source_title` set to the note filename stem. Per-note errors are caught and skipped; `skipped_files` counts notes that errored during ingestion (not the same as `get_vault_stats` skipped count which refers to short notes). Re-ingesting the same vault is safe — ChromaDB upsert prevents duplicate chunks. Can take 30–120 seconds for large vaults.

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
  "scored": true
}
```
**Notes:** Runs the full LangGraph pipeline. `quality` defaults to `"standard"` (1 humanizer pass, scorer skipped — lazy). Pass `"polished"` for up to 3 humanizer iterations with scorer running each pass. Pass `"draft"` to skip humanizer and scorer entirely. `scored` in the response indicates whether the scorer ran: `false` for `standard` and `draft` modes (use `POST /score` to score on demand), `true` for `polished` mode. Posts are NOT auto-saved by this endpoint — the frontend calls `/log-post` automatically after generation completes.

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
**Notes:** Returns up to 20 most recent saved posts, newest first. `svg_diagrams` is `null` for posts saved before the visuals feature or saved without diagrams. The JSON string stored in SQLite is parsed back to a list before returning. Each post includes a `versions` array (see `post_versions` schema) with all versions ordered by `version_number` ascending; `svg_diagrams` within each version is also parsed from JSON.

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
      "tags": ["rag", "machine learning", "production systems"]
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

## 4. DATA SCHEMAS

### profile.json (full structure)

**Location:** `DATA_DIR/profiles/profile_{user_id}.json` (per-user); legacy `DATA_DIR/profile.json` for `user_id="default"` if it exists
**Gitignored:** Yes — personal details never committed.
**Auto-created:** `load_profile()` returns `DEFAULT_PROFILE` copy if the file does not exist.
**Forward-compatible:** Missing keys are filled in from `DEFAULT_PROFILE` on load — adding new fields never breaks existing profiles.
**New users:** Redirected to `/onboarding` after Clerk sign-up; `POST /profile` creates their profile file.

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | User's name — `profile_exists()` checks this field is non-empty |
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
| Split-screen analysis layout breaks out of max-width container | When analysis is open on wide viewports (`>= 900px`), CreatePost applies `position: fixed; left: 14rem; right: 0; top: 0; bottom: 0` to escape the parent `max-w-3xl` constraint and use the full available viewport width beside the sidebar. The standard stacked layout is used on narrow viewports or when analysis is closed. |
| Landing page at `/welcome` has its own layout | `frontend/app/welcome/page.tsx` renders a complete standalone page (top nav, hero, feature cards, how-it-works section, footer) using its own inline nav — not the shared Sidebar. `AppShell` detects `pathname === "/welcome"` and renders `{children}` directly without the sidebar wrapper. |
| Settings drawer for regeneration replaces inline form | After a post is generated, the topic/format/tone/context inputs are hidden. Clicking "Regenerate" opens a right-side drawer (`SettingsDrawer`) where the user edits settings and confirms. This keeps the post content area clean and uncluttered after generation. |
| Topic displayed above post content box after generation | In both split and stacked layouts, after generation the current topic is shown as a small `TOPIC` label + value line above the post textarea. This is display-only; topic changes go through the settings drawer. |
| Post detail page at `/history/[id]` | Individual posts have a dedicated full-page view accessible via the dynamic route `/history/[id]`. The page fetches from `GET /history`, finds the matching post by id, and renders the full content with version picker, restore, delete, and diagrams — same features as the expanded card in `/history` but with more space. |
| User can delete posts from History | `DELETE /history/{post_id}` removes the SQLite row; frontend filters the card from state without a page reload. |
| `/refine` does not run the full pipeline | Refinement is a targeted one-pass fix: `refine_draft()` + `score_text()` only. No retrieval, no draft agent, no retry loop — running the full pipeline would discard the user's manual edits |
| `score_text()` extracted from `scorer_node` | Scoring logic lives in exactly one place (`scorer_agent.py`); both the LangGraph pipeline (`scorer_node`) and the standalone `/refine` endpoint call `score_text()` internally — no duplication |
| Default generation quality is standard | 1 humanizer pass, 1 scorer pass, no automatic retry loop. Replaces the previous default of polished mode which ran up to 3 iterations automatically. The Refine Draft button is the on-demand polishing step for users who want additional passes after seeing the initial result. |
| Quality modes: draft, standard, polished | `draft` — skip humanizer and scorer entirely, return raw draft agent output. `standard` — 1 humanizer pass + 1 scorer pass, no retry (default). `polished` — up to 3 humanizer passes, retry if score below 75. Quality is passed in the POST /generate request body and defaults to `standard` if not provided. |
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
| `main.py` split into 6 focused `APIRouter` files under `backend/routers/` | Each router owns its endpoints and imports only what it needs. `main.py` is now ~40 lines — CORS config, lifespan hook, and router registration only. Pydantic models that are used by only one router live in that router file; no shared `models.py` was needed. When Clerk auth middleware is added, it attaches at the app level in `main.py` and extracts `user_id` before any router handler runs — no changes to individual router files required. |
| ChromaDB collections namespaced per user as `contendo_{user_id}` | Data isolation layer that auth will sit on top of. The default single-user collection is `contendo_default` — existing single-user deployments are unaffected. All `vector_store.py` functions accept `user_id: str = "default"`. All call sites in router files (`library.py`, `ingest.py`, `stats.py`) currently pass `user_id="default"` (hardcoded); the pipeline receives `user_id` from the `POST /generate` request body. When Clerk auth is added, `"default"` is replaced with the JWT-extracted user ID at each endpoint — no changes to `vector_store.py` or the pipeline internals required. Existing data in the old `"contendo"` collection is not auto-migrated; the single user must re-ingest. |
| Chunks prefixed with `[source_type: X]` before reaching draft agent | `retrieval_node` prepends `[source_type: article]`, `[source_type: note]`, `[source_type: youtube]`, or `[source_type: image]` to each chunk string. Preserves attribution metadata without changing the `list[str]` schema of `retrieved_chunks` in `PipelineState`. The draft agent's SOURCE ATTRIBUTION RULES use this label to distinguish content the user personally wrote (notes — attributable to direct experience) from content they read or watched (articles, youtube, images — must be framed as external references, never as first-person claims). Prevents the fabrication of personal experiences by combining the user's employer/role from their profile with technical details from external chunks. Missing or `"unknown"` source_type defaults to `"article"` as the safe assumption. |
| Critic agent runs once per generation, not per retry iteration | The retry loop in polished mode routes back to `humanizer_node` only. Re-running the critic on each iteration would add a Haiku call per retry pass and is redundant — the critic already diagnosed the initial draft's structural issues; subsequent humanizer passes are language refinements on an already-diagnosed foundation. The critic brief from iteration 1 remains in state for all retry passes. |
| Critic agent receives all retrieved chunks, not a subset | `critic_node` passes all `retrieved_chunks` to the prompt — no slicing. This matches exactly what `draft_agent` received, so the critic can accurately assess whether claims in the draft are grounded. Passing only a subset (e.g. the first 5) risked false "substance: needs_work" verdicts for claims that were actually supported by chunks the critic was never shown. |
| Critic agent uses Haiku, not Sonnet | Diagnosis is pattern recognition (is the hook weak? are there vague claims?), not creative generation. Haiku is fast and cheap for classification tasks. Sonnet is reserved for the humanizer where creative rewriting quality matters. |
| Critic brief fallback is a neutral brief, not an exception | If the Haiku call fails or JSON parsing fails after 3 attempts, `critic_node` sets `critic_brief=_NEUTRAL_BRIEF` (all "strong") or `{}` depending on failure type. This ensures the humanizer always receives a safe input — the pipeline never breaks due to a failed critic call. |
| Critic brief is `{}` for draft mode, neutral dict for standard/polished parse failure | An empty dict `{}` from draft-mode bypass means "critic was skipped intentionally." `_format_critic_brief({})` returns empty critic_section — humanizer behaves as pre-critic for backward compat. |
| Anthropic client is instantiated at module level in each agent file | Client is created once at import time and reused across all calls — not re-instantiated on every function invocation. `max_retries=3` enables the SDK's built-in retry logic for 429 rate limit errors and transient network failures at no extra code cost. No shared `llm_client.py` — module-level per file is sufficient at current codebase size. Applies to all 7 agent files: `draft_agent.py`, `humanizer_agent.py`, `scorer_agent.py`, `ingestion_agent.py`, `vision_agent.py`, `visual_agent.py`, `ideation_agent.py`. |
| Ingestion deduplication uses SHA-256 hash of normalised content | `compute_content_hash()` in `ingestion_agent.py` strips and lowercases the content string before hashing. On every `ingest_content()` call, `query_by_hash()` checks for an existing match in ChromaDB metadata before the Claude tag extraction call runs. Duplicate content returns immediately with the existing chunk count and tags — zero Claude API calls. The hash is stored in each chunk's `content_hash` metadata field so future checks can find it. Content ingested before this feature was added has no `content_hash` in metadata and will not be deduplicated retroactively. Obsidian vault ingest (`/obsidian/ingest`) is excluded — its upsert-based flow already handles re-ingestion safely. |

---

| Clerk JWT auth via PyJWT + JWKS | `auth/clerk.py` fetches Clerk's JWKS from `https://api.clerk.com/v1/jwks` (cached 1hr in memory); uses `RSAAlgorithm.from_jwk()` to select the signing key by `kid` header; decodes with `jwt.decode(..., algorithms=["RS256"])`. `CLERK_SECRET_KEY` is required for the JWKS endpoint. Any exception → 401. |
| Dev fallback to `user_id="default"` | When `ENVIRONMENT != "production"` and no Authorization header is present, `get_user_id()` returns `"default"` instead of raising 401. This preserves full local dev convenience — no token needed. Production always requires a valid token. |
| Per-user profile files at `DATA_DIR/profiles/profile_{user_id}.json` | Separates profiles per Clerk `sub` claim. The `"default"` user still falls back to `DATA_DIR/profile.json` if it exists (backward compat for existing local dev data). `PROFILES_DIR` is exposed from `config/paths.py`. |
| SQLite `ALTER TABLE posts ADD COLUMN user_id` migration is idempotent | Wrapped in try/except in `init_db()`. First deploy after this change adds the column; subsequent deploys silently pass the `except`. Existing rows default to `user_id='default'` (SQLite `DEFAULT 'default'`). No manual migration needed. |
| All existing rows in posts.db get `user_id='default'` | Railway production: the first deploy after this branch merges runs `init_db()` which adds the column. All pre-existing post history is attributed to `"default"`. If that user later creates a Clerk account, they will not see their old posts (different user_id). Acceptable for MVP. |
| Onboarding redirect via `useProfileCheck` in AppShell | After Clerk confirms auth, AppShell calls `GET /profile`. If `has_profile === false`, the user is pushed to `/onboarding`. Public routes (`/welcome`, `/sign-in`, `/sign-up`, `/onboarding`) skip the check. The hook exposes `loading` so AppShell can show a spinner while the check is in flight. |
| Frontend API layer via `useApi()` hook in `lib/api.ts` | Centralises all backend calls in one hook. `useAuth().getToken()` is called per-request to always attach a fresh token (Clerk tokens are short-lived). Components call `const api = useApi()` instead of raw `fetch()`. All request/response types are exported from `lib/api.ts` for IDE completions. |

---

## 6. WHAT IS NOT BUILT YET

- Obsidian integration does not work after cloud deployment — vault path is a local filesystem path read by FastAPI. Guarded by `ENVIRONMENT=production` (returns HTTP 400) and hidden in the frontend when API URL is not localhost. Future full solution: vault zip upload or Electron desktop wrapper.

- Vercel and Railway/Render deployment config files
- YouTube transcript auto-fetching (removed — manual paste only)
- Tag filtering in Library (can't filter ChromaDB chunks by tag in the UI — only source-type filter exists)
- Bulk clear memory (individual sources can be deleted via the Library delete button, but there is no "clear all" option)
- Multi-format regeneration (regenerate always uses same format/tone)
