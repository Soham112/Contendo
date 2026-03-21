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
| `.gitignore` | Excludes venv, node_modules, .env, chroma_db data |
| **Backend** | |
| `backend/main.py` | FastAPI app — all routes, CORS config, SQLite post history init |
| `backend/requirements.txt` | All Python dependencies pinned |
| `backend/.env.example` | Required env var keys with no values |
| `backend/agents/ideation_agent.py` | Generates N content ideas from ChromaDB sample, profile, and posted topic history |
| `backend/agents/visual_agent.py` | Parses [DIAGRAM:] and [IMAGE:] placeholders from post; calls Claude to generate SVG for diagrams; returns reminder text for images |
| `backend/agents/ingestion_agent.py` | Chunks content, extracts tags via Claude, upserts to ChromaDB |
| `backend/agents/vision_agent.py` | Sends base64 images to Claude vision, returns extracted text |
| `backend/agents/retrieval_agent.py` | Semantic search node in the LangGraph pipeline |
| `backend/agents/draft_agent.py` | Generates initial post draft via Claude |
| `backend/agents/humanizer_agent.py` | Rewrites draft to remove AI patterns, inject human voice |
| `backend/agents/scorer_agent.py` | Scores draft 0–100 across 5 dimensions, returns flagged sentences |
| `backend/pipeline/state.py` | TypedDict schema for shared LangGraph pipeline state |
| `backend/pipeline/graph.py` | LangGraph graph definition — nodes, edges, conditional retry loop |
| `backend/memory/vector_store.py` | ChromaDB init, upsert, semantic query, stats |
| `backend/memory/profile_store.py` | profile.json read/write, defaults, profile-to-string formatter |
| `backend/memory/feedback_store.py` | SQLite posts and post_versions tables — log_post, get_recent_posts, get_all_topics_posted, add_version, get_versions, get_best_version, update_latest_version_svg |
| `backend/tools/__init__.py` | Empty — tools directory retained for future use |
| `backend/utils/chunker.py` | 500-word chunks with 50-word overlap |
| `backend/utils/formatters.py` | Format + tone instruction strings per output type |
| `backend/utils/file_extractor.py` | Extracts plain text from PDF (PyMuPDF), DOCX (python-docx), and TXT files; raises ValueError on unsupported types, scanned PDFs, password-protected PDFs, and empty files |
| `backend/data/profile.json` | User voice and style profile — **gitignored**, never committed. Copy from `profile.template.json` to create. |
| `backend/data/profile.template.json` | Committed template with placeholder values — starting point for new users |
| `backend/data/chroma_db/` | ChromaDB persistent storage (gitignored) |
| `backend/data/posts.db` | SQLite post history (gitignored) |
| `backend/venv/` | Python virtual environment (gitignored) |
| **Frontend** | |
| `frontend/app/layout.tsx` | Root layout — nav bar with links to all four screens |
| `frontend/app/page.tsx` | Screen 1: Feed Memory (default route `/`) |
| `frontend/app/library/page.tsx` | Screen 2: Library (`/library`) — source cards, stats bar, filter/sort |
| `frontend/app/create/page.tsx` | Screen 3: Create Post (`/create`) |
| `frontend/app/history/page.tsx` | Screen 4: Post History (`/history`) — cards, expandable content, copy |
| `frontend/app/globals.css` | Global styles — Tailwind directives, dark background, Inter font |
| `frontend/components/FeedMemory.tsx` | Feed Memory form — tabs (Article/Text, File, YouTube, Image, Note), textarea, file upload with drag-and-drop, image upload, result display |
| `frontend/components/CreatePost.tsx` | Create Post form — topic, format, tone, output + score display |
| `frontend/.env.local` | Sets `NEXT_PUBLIC_API_URL=http://localhost:8000` |
| `frontend/tailwind.config.ts` | Tailwind config scoped to app/ and components/ |
| `frontend/package.json` | Next.js 14 app with TypeScript + Tailwind |

---

## 2. AGENT CONTRACTS

### ingestion_agent.py
| | |
|---|---|
| **Reads** | `content: str`, `source_type: str` (passed directly, not from pipeline state) |
| **Writes** | Returns `{ chunks_stored: int, tags: list[str] }` — not a pipeline node |
| **Side effects** | Upserts chunks to ChromaDB with `source_title` (first 80 chars of content) and `ingested_at` (UTC ISO timestamp) |

### vector_store.py — get_all_sources()
| | |
|---|---|
| **Reads** | All ChromaDB chunk metadatas via `collection.get()` |
| **Returns** | `list[dict]` — one entry per unique `source_id` with `source_title`, `source_type`, `ingested_at`, `chunk_count`, `tags` (deduplicated) |
| **Sort** | Newest `ingested_at` first; sources without timestamp sort last |

### vision_agent.py
| | |
|---|---|
| **Reads** | `image_base64: str`, `media_type: str` (passed directly) |
| **Writes** | Returns `str` — extracted knowledge text |
| **Side effects** | None (output fed into ingestion_agent) |

### retrieval_node (retrieval_agent.py)
| | |
|---|---|
| **Reads from state** | `topic`, `context` |
| **Writes to state** | `retrieved_chunks: list[str]` |
| **Side effects** | Queries ChromaDB, filters below 0.3 cosine similarity |

### draft_node (draft_agent.py)
| | |
|---|---|
| **Reads from state** | `profile`, `retrieved_chunks`, `topic`, `format`, `tone`, `context` |
| **Writes to state** | `current_draft: str` |
| **Side effects** | 1 Claude API call |

### humanizer_node (humanizer_agent.py)
| | |
|---|---|
| **Reads from state** | `profile`, `current_draft` |
| **Writes to state** | `current_draft: str` (overwrites), `iterations: int` (increments by 1) |
| **Side effects** | 1 Claude API call per invocation |

### scorer_node (scorer_agent.py)
| | |
|---|---|
| **Reads from state** | `current_draft` |
| **Writes to state** | `score: int`, `score_feedback: list[str]` |
| **Side effects** | 1 Claude API call |

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
  "iterations": 2
}
```
**Notes:** Runs the full LangGraph pipeline. `quality` defaults to `"standard"` (1 humanizer + 1 scorer pass, no retry loop). Pass `"polished"` for up to 3 humanizer iterations. Pass `"draft"` to skip humanizer and scorer entirely. Posts are NOT auto-saved by this endpoint — the frontend calls `/log-post` automatically after generation completes.

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
  ]
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

**Location:** `backend/data/profile.json`
**Gitignored:** Yes — personal details never committed. Copy from `backend/data/profile.template.json` to create.
**Auto-created:** `load_profile()` creates a minimal default if the file does not exist, but the output will be generic until the user fills in their real profile.
**Forward-compatible:** Missing keys are filled in from defaults on load — adding new fields to the template does not break existing profiles.

| Field | Type | Description |
|-------|------|-------------|
| `name` | str | User's name |
| `role` | str | Role/title — injected into every draft prompt |
| `bio` | str | 2–3 sentence summary of who they are and what they believe |
| `location` | str | City, country |
| `target_audience` | str | Who they write for — shapes tone and framing |
| `topics_of_expertise` | list[str] | Domains the user knows deeply |
| `projects` | list[dict] | Built things — name, description with real numbers, stack |
| `opinions` | list[str] | Strong takes the user actually holds — not facts |
| `phrases_i_use` | list[str] | Natural phrases specific to this person |
| `words_to_avoid` | list[str] | Injected into humanizer prompt as banned language |
| `writing_rules` | list[str] | Style rules injected into draft and humanizer prompts |
| `technical_voice_notes` | list[str] | How the user specifically explains hard technical things |
| `linkedin_style_notes` | str | Format-specific style notes for LinkedIn posts |
| `medium_style_notes` | str | Format-specific style notes for Medium articles |
| `thread_style_notes` | str | Format-specific style notes for threads |
| `writing_samples` | list[str] | Real past posts — the single most powerful signal for voice matching |

---

### ChromaDB collection
| Property | Value |
|----------|-------|
| Collection name | `contendo` |
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
| All Claude calls use `claude-sonnet-4-6` | Spec requirement; no other model used anywhere |
| ChromaDB similarity threshold is 0.3 | Cosine similarity — chunks below this are too semantically distant to help |
| profile.json has auto-merge on load | Ensures new profile fields added in code appear without manual migration |
| CORS allows `*.vercel.app` wildcard | Covers all preview and production Vercel deployments without hardcoding URLs |
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
| Score and feedback hidden by default | Score ring, iterations, feedback, and refine section are collapsed behind a "Show authenticity analysis" toggle. Post textarea and action buttons are always visible. Preference stored in `contentOS_show_analysis` sessionStorage. Scorer still runs every time — this is display only. |
| Ideas persist in sessionStorage until dismissed | `contentOS_last_ideas` stores the ideas array; panel is restored on mount if key exists. Panel stays open after "Use this" (idea gets a checkmark). Cleared only by explicit X dismiss, Regenerate, or restored-session dismiss. |
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
| Post versioning uses a parent + child table design | The `posts` table is the parent record (one row per generation session); `post_versions` stores every historical version. Every generation creates v1; every refinement creates the next version. SVG diagram updates do not create new versions — `update_latest_version_svg()` stamps diagrams onto the current version row in place. |
| Best version tracked by highest authenticity_score | `get_best_version()` orders by `authenticity_score DESC, version_number DESC` so ties go to the latest version. The History UI highlights the best version with a green "Best" badge. |
| Restore writes to sessionStorage, not a new PATCH | Restoring a version calls `POST /history/{post_id}/restore/{version_id}`, which updates the `posts` row. The frontend then writes the restored content to `contentOS_last_post` and related keys so Create Post picks it up immediately without an extra fetch. |

---

## 6. WHAT IS NOT BUILT YET

- User authentication (single user only for now — no auth layer)
- Profile editing screen (profile.json must be edited manually)
- Dedicated brainstorm / ideas screen (the Get Ideas panel on Create Post exists, but there is no standalone ideas-management screen)
- Vercel and Railway/Render deployment config files
- YouTube transcript auto-fetching (removed — manual paste only)
- Tag filtering in Library (can't filter ChromaDB chunks by tag in the UI — only source-type filter exists)
- Delete / clear memory (no way to remove sources or chunks via UI)
- Multi-format regeneration (regenerate always uses same format/tone)
