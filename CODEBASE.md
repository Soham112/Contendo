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
| `backend/main.py` | FastAPI app — all 3 routes, CORS config, SQLite post history init |
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
| `backend/memory/feedback_store.py` | SQLite posts table — log_post, get_recent_posts, get_all_topics_posted |
| `backend/tools/__init__.py` | Empty — tools directory retained for future use |
| `backend/utils/chunker.py` | 500-word chunks with 50-word overlap |
| `backend/utils/formatters.py` | Format + tone instruction strings per output type |
| `backend/data/profile.json` | User voice and style profile — auto-created on first run |
| `backend/data/chroma_db/` | ChromaDB persistent storage (gitignored) |
| `backend/data/posts.db` | SQLite post history (gitignored) |
| `backend/venv/` | Python virtual environment (gitignored) |
| **Frontend** | |
| `frontend/app/layout.tsx` | Root layout — nav bar with links to all three screens |
| `frontend/app/page.tsx` | Screen 1: Feed Memory (default route `/`) |
| `frontend/app/create/page.tsx` | Screen 2: Create Post (`/create`) |
| `frontend/app/history/page.tsx` | Screen 3: Post History (`/history`) — cards, expandable content, copy |
| `frontend/app/globals.css` | Global styles — Tailwind directives, dark background, Inter font |
| `frontend/components/FeedMemory.tsx` | Feed Memory form — tabs, textarea, image upload, result display |
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
| **Side effects** | Upserts chunks to ChromaDB |

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
| **Reads** | `profile.json` from disk |
| **Writes to state** | `profile: dict`, `iterations: 0` |

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
**Notes:** Runs the full LangGraph pipeline. Every generated post is saved to SQLite.

---

### POST /log-post
**Request body:**
```json
{
  "topic": "string",
  "format": "linkedin post | medium article | thread",
  "tone": "casual | technical | storytelling",
  "content": "string — the post text (may differ from generated if user edited it)",
  "authenticity_score": 82
}
```
**Response:**
```json
{ "post_id": 7, "saved": true }
```
**Notes:** User-initiated only — never called automatically. The content saved may differ from the originally generated draft if the user edited it before saving.

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
      "authenticity_score": 82
    }
  ]
}
```
**Notes:** Returns up to 20 most recent saved posts, newest first.

---

### GET /suggestions
**Query params:** `count` (int, default 5, range 1–10)
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
**Notes:** Calls ideation_agent, which samples ChromaDB broadly, reads all previously posted topics from feedback_store, and asks Claude to generate ideas that avoid repetition.

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
```json
{
  "name": "Soham",
  "role": "Builder and founder",
  "voice_descriptors": ["direct", "opinionated", "first-person", "conversational", "no fluff"],
  "writing_rules": [
    "Never start sentences with 'I' back-to-back.",
    "Use short paragraphs — max 3 sentences.",
    "Prefer concrete examples over abstract claims.",
    "No corporate jargon or buzzwords.",
    "Vary sentence length: mix short punchy lines with longer ones.",
    "Avoid passive voice.",
    "Never use filler phrases like 'In conclusion' or 'It is worth noting'."
  ],
  "topics_of_expertise": ["AI and LLMs", "product building", "startups", "developer tools"],
  "linkedin_style_notes": "Hook in the first line...",
  "medium_style_notes": "Start in the middle of the story...",
  "thread_style_notes": "Each tweet stands alone but pulls into the next...",
  "words_to_avoid": ["leverage", "synergy", "delve", "unlock", "game-changer", "revolutionary", "transformative", "it's important to note", "in today's world", "crucial"]
}
```
**Location:** `backend/data/profile.json`
**Auto-created:** Yes — on first call to `load_profile()` if file does not exist.
**Forward-compatible:** Missing keys are filled in from defaults on load.

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
| `content` | TEXT | Post text as saved (may be user-edited) |
| `authenticity_score` | INTEGER | Score at time of generation (0–100) |

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
| Posts are not auto-saved | User must explicitly click "Save to history" on Screen 2 — auto-save removed from `/generate` to give the user control over what enters their history |
| feedback_store.py owns the SQLite table | `main.py` no longer contains `init_db` or `save_post` — all DB logic is in `feedback_store.py`; `init_db()` is called from the FastAPI lifespan |
| draft_node injects posted topics | `load_profile_node` fetches `get_all_topics_posted()` and stores in pipeline state; `draft_node` formats them into the prompt to prevent repeated angles |
| `source_type: "youtube"` treated identically to `"article"` in ingestion | Same chunking + embedding pipeline; only difference is the UI label |
| Diagrams generated as SVG, converted to PNG in browser | Claude returns self-contained SVG; Canvas API converts at 2x viewBox resolution for retina quality — no server-side image processing needed |
| Image placeholders are not auto-generated | `[IMAGE:]` placeholders return reminder cards so the user adds real photos or screenshots — Claude is not called for these |
| PNG exported at 2x resolution | Canvas dimensions are set to 2× the SVG viewBox width/height, parsed dynamically from the returned SVG element |
| Placeholders never auto-stripped from post textarea | `[DIAGRAM:]` and `[IMAGE:]` remain in the editable textarea — user removes them manually before copying |

---

## 6. WHAT IS NOT BUILT YET

- User authentication (single user only for now — no auth layer)
- Profile editing screen (profile.json must be edited manually)
- Ideation / ideas screen (brainstorming feature deferred)
- Vercel and Railway/Render deployment config files
- YouTube transcript auto-fetching (removed — manual paste only)
- Tag filtering in memory (can't filter ChromaDB by tag in the UI)
- Delete / clear memory (no way to remove chunks via UI)
- Multi-format regeneration (regenerate always uses same format/tone)
