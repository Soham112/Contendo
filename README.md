# Contendo

A personal content generation system that learns your knowledge base and writes in your voice. You feed it articles, YouTube videos, images, and notes — it stores them as semantic memory. When you want to publish, it retrieves the most relevant knowledge, drafts content in your style, humanizes it, scores it, and hands you a final editable post.

Built for a single user. No auth, no bloat — just a fast loop from raw knowledge to publishable content.

---

## Architecture

```mermaid
flowchart TD
    subgraph UI["Frontend (Next.js 14) — 5 Screens + Landing Page"]
        NAV["Left Sidebar (Sidebar.tsx)\nFeed Memory / Library / Create Post / Get Ideas / History"]
        S1["Screen 1: Feed Memory (/)\n(Article / URL / File / YouTube / Image / Note / Obsidian)"]
        S2["Screen 2: Library (/library)\n(Source cards, stats, filter/sort)"]
        S3["Screen 3: Create Post (/create)\n(Settings drawer / Split-screen analysis / Topic header)"]
        S4["Screen 4: Get Ideas (/ideas)\n(Topic filter / Save for later / Use this → prefill Create Post)"]
        S5["Screen 5: History (/history)\n(Versioned posts, restore, delete, diagrams)"]
        S5b["Post Detail (/history/[id])\n(Full-page post view, version picker, restore)"]
        S6["Landing Page (/welcome)\n(Own top nav, bypasses sidebar)"]
    end

    subgraph API["FastAPI Backend — 17 Endpoints"]
        R1["POST /ingest\nPOST /ingest-file\nPOST /scrape-and-ingest"]
        R1b["POST /obsidian/preview\nPOST /obsidian/ingest"]
        R2["POST /generate"]
        R2b["POST /refine"]
        R3["POST /log-post (auto-save)"]
        R4["GET /history\nPATCH /history/{id}\nDELETE /history/{id}\nPOST /history/{id}/restore/{vid}"]
        R5["GET /library\nDELETE /library/source"]
        R6["GET /suggestions"]
        R7["POST /generate-visuals"]
        R8["GET /stats"]
    end

    subgraph Pipeline["LangGraph Pipeline"]
        N1["1. load_profile_node\nLoad profile + posted topics"]
        N2["2. retrieval_node\nSemantic search ChromaDB"]
        N3["3. draft_node\nInfer archetype (Claude Haiku) → generate initial draft (Claude Sonnet)"]
        N4["4. humanizer_node\nRemove AI patterns, inject voice"]
        N5["5. scorer_node\nScore 0–100 across 5 dimensions"]
        N6{"Quality mode?\ndraft/standard → finalize\npolished → check score + iterations"}
        N7["finalize_node"]
    end

    subgraph Agents["Standalone Agents"]
        A1["visual_agent\n(SVG generation per DIAGRAM placeholder)"]
        A2["ideation_agent\n(multi-query knowledge base sampling)"]
    end

    subgraph Memory["Memory Layer"]
        DB1["ChromaDB\n(vector store — chunks + metadata)"]
        DB2["profile.json\n(voice, style, words to avoid)"]
        DB3["SQLite posts.db\n(posts + post_versions tables)"]
    end

    NAV --> S1
    NAV --> S2
    NAV --> S3
    NAV --> S4
    NAV --> S5
    S5 --> S5b
    S1 --> R1
    S1 --> R1b
    S1 --> R8
    S2 --> R5
    S3 --> R2
    S3 --> R2b
    S3 --> R3
    S3 --> R7
    S4 --> R6
    S5 --> R4
    S5b --> R4

    R1 --> DB1
    R1b --> DB1
    R2 --> N1
    R3 --> DB3
    R4 --> DB3
    R5 --> DB1
    R6 --> A2
    R7 --> A1

    N1 --> N2
    N2 --> N3
    N3 --> N4
    N4 --> N5
    N5 --> N6
    N6 -->|"finalize"| N7
    N6 -->|"retry (polished mode only)"| N4
    N7 --> DB3

    N1 --- DB2
    N2 --- DB1
    A2 --- DB1
```

---

## The Five Screens

Navigation across all five screens is handled by a persistent left sidebar (`Sidebar.tsx`), rendered by `AppShell.tsx` for every route except `/welcome`. The landing page at `/welcome` has its own top nav and bypasses the sidebar entirely.

**Screen 1 — Feed Memory (`/`):** The user selects an input type (Article/Text, URL, File, YouTube, Image/Diagram, Note, or Obsidian vault) and adds their content. For **URL**, the backend scrapes the page via Jina Reader and stores it automatically. For **File**, PDF, DOCX, and TXT uploads (up to 10 MB) are accepted — text is extracted server-side. For **Image/Diagram**, Claude vision extracts the knowledge as text first. For **Obsidian**, the user enters their local vault folder path; a preview step shows how many notes and words will be ingested before committing. The YouTube tab shows a textarea for manual paste — auto-fetching was removed after YouTube blocked bot-based transcript retrieval. For all types, content is chunked into 500-word overlapping segments, embedded locally with `sentence-transformers`, and upserted into ChromaDB. The response shows how many chunks were stored and what tags were auto-extracted.

**Screen 2 — Library (`/library`):** Shows everything the user has fed into memory, grouped by source (one card per ingest call, not per chunk). A stats bar shows total sources, total chunks, and unique tag count. Source cards display the type badge (Article/Note/Image/YouTube), title derived from the first 80 characters of the content, date added, chunk count, and tag pills. Searchable by title and tags, filterable by source type, sortable newest/oldest. This gives the user full visibility into what knowledge the system has before generating a post.

**Screen 3 — Create Post (`/create`):** The user enters a topic, picks a format and tone, and clicks Generate. Before generation, all settings are shown inline. After generation, the settings form is replaced by the generated post in an editable textarea, with a small topic header displayed above the post. A "View authenticity analysis" toggle reveals the score panel; when open on wide viewports (≥ 900px), the layout switches to a fixed split screen — post on the left, score and refine controls on the right — escaping the normal max-width container to use the full viewport beside the sidebar. The settings drawer (opened via "Regenerate") lets the user edit topic/format/tone/context and re-run without losing the current post. "Generate visuals" parses `[DIAGRAM:]` and `[IMAGE:]` placeholders and generates SVGs via Claude. Posts are **auto-saved** to history immediately after generation with a realtime tracking indicator ("Saved just now") — no manual save step required. Session state (post, score, visuals, ideas) persists in sessionStorage so navigating away and back restores the last session cleanly on the editor view.

**Screen 4 — Get Ideas (`/ideas`):** A dedicated brainstorm screen. The user optionally enters a topic focus and picks how many ideas to generate (3–15). The ideation agent runs multi-query diversity sampling across the knowledge base and returns content suggestions. Ideas generated in a session persist in localStorage (`contendo_ideas`) and are restored on page revisit. Individual ideas can be saved for later (`contendo_saved_ideas` localStorage key); saved ideas appear in a "SAVED" subsection. Clicking "Use this" writes the idea title to `contentOS_last_topic` and the format to `contentOS_prefill_format` in sessionStorage, then redirects to Create Post where both are pre-filled.

**Screen 5 — History (`/history`):** All auto-saved posts, newest first. Searchable by topic and content string matches. Each card shows topic, format/tone badges, authenticity score, and date. Every generation creates version 1; every refinement creates the next version. Version pills in the card header show the score for each version (color-coded green/amber/red) with the best version starred. Clicking a pill switches the expanded view to that version's content. Any version can be restored to Create Post with one click. Cards can be deleted with a confirmation step. Global toast notifications pop up confirming system interactions. If SVG diagrams were saved alongside the post, they are rendered inline in the expanded view with an "Open as PNG" button. Individual posts also have a dedicated full-page detail view at `/history/[id]`.

---

## Agent Pipeline

| Step | Agent | Job |
|------|-------|-----|
| 1 | `load_profile_node` | Reads `profile.json`, injects user voice and style into state. Also loads all previously posted topics from SQLite to prevent repeated angles. |
| 2 | `retrieval_node` | Queries ChromaDB for the 8 most semantically relevant chunks; builds a `retrieval_bundle` with source summaries and adjacent sibling chunks from `hierarchy_store`; sets `retrieved_context` (enriched prompt block) and always sets `retrieved_chunks` for backward compat; falls back to flat retrieval if hierarchy_store is empty |
| 3 | `draft_node` | First calls Claude Haiku (`infer_archetype()`) to classify the topic into one of 7 post archetypes. Then calls Claude Sonnet to produce a draft using the enriched `retrieved_context` (source summaries + sibling chunks for top sources) or flat `retrieved_chunks` as fallback |
| 4 | `humanizer_node` | Calls Claude to strip AI writing patterns, vary sentence structure, and inject the user's authentic voice. Also exposes `refine_draft()` for targeted post-generation edits via `/refine` |
| 5 | `scorer_node` | Calls Claude to score the draft 0–100 across 5 dimensions; uses 3-attempt JSON parse to handle markdown-wrapped responses |
| 6 | Conditional | **draft** mode: skip humanizer and scorer entirely, return raw draft. **standard** mode (default): 1 humanizer pass; scorer skipped during generation — scored lazily on demand via `POST /score` when user clicks the analysis toggle. **polished** mode: up to 3 humanizer passes with scorer running each iteration; retries if score < 75 and iterations < 3. |

---

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Frontend | Next.js 14 (App Router) | File-based routing, RSC-ready, deploys instantly to Vercel |
| Styling | TailwindCSS | Utility-first, zero config, great with Next.js |
| Font | Noto Serif + Inter (Google Fonts) | Noto Serif for headlines (`font-headline`), Inter for body/UI — loaded via `@import` in `globals.css`; editorial atelier aesthetic |
| Backend | FastAPI (Python 3.11) | Async, typed, auto-docs, fast iteration |
| LLM | claude-sonnet-4-6 (Anthropic) | Best balance of quality and speed for generation tasks |
| Embeddings | sentence-transformers (all-MiniLM-L6-v2) | Local, no API key, good semantic quality for retrieval |
| Vector DB | ChromaDB | Local persistent storage, simple Python API, no infra needed |
| Agent orchestration | LangGraph | Stateful graph with conditional edges — perfect for retry loops |
| Post history | SQLite (sqlite3) | Zero-config, single-file, sufficient for one user |
| HTTP client | httpx | URL scraping via Jina Reader |
| PDF extraction | PyMuPDF (fitz) | Fast text extraction from PDFs; detects scanned/image-only files |
| DOCX extraction | python-docx | Plain text extraction from Word documents |
| Deployment (frontend) | Vercel | Native Next.js hosting |
| Deployment (backend) | Railway or Render | Simple Python service hosting |

---

## Local Development Setup

```bash
# 1. Clone the repo
git clone <repo-url>
cd <project-root>

# 2. Create and activate the Python virtual environment
python3 -m venv backend/venv
source backend/venv/bin/activate

# 3. Install Python dependencies
pip install -r backend/requirements.txt

# 4. Configure environment variables
cp backend/.env.example backend/.env
# Open backend/.env and fill in your ANTHROPIC_API_KEY

# 5. Start the backend (from project root, venv must be active)
cd backend
uvicorn main:app --reload

# 6. In a new terminal, start the frontend
cd frontend
npm install
npm run dev

# 7. Open the app
# http://localhost:3000
```

---

## Setup your profile

The system writes in YOUR voice — but it needs to know who you are first.

Before running the system for the first time:

1. Copy the profile template:
   ```bash
   cp backend/data/profile.template.json backend/data/profile.json
   ```

2. Open `backend/data/profile.json` and fill in every field:
   - `name`, `role`, `bio` — who you are
   - `topics_of_expertise` — what you know deeply
   - `projects` — what you have built (with real numbers)
   - `opinions` — strong takes you actually hold
   - `phrases_i_use` — words and phrases natural to you
   - `words_to_avoid` — language that does not sound like you
   - `writing_samples` — paste 3–5 of your real past posts here
   - `technical_voice_notes` — how you specifically explain hard things (see examples in the template)

3. The more specific you are, the better the output. Generic profile → generic posts. Specific profile → posts that sound like you wrote them.

Note: `profile.json` is gitignored — your personal details never get committed to the repository. Only the template is tracked.

---

## Project File Structure

```
.
├── README.md                         # This file — project overview and architecture
├── CODEBASE.md                       # Full technical reference — read before touching code
├── PROMPTS.md                        # All agent system prompts verbatim — source of truth
├── DESIGN.md                         # Editorial Atelier design system — read before any UI change
├── scripts/
│   └── migrate_hierarchy.py          # One-time migration: backfill hierarchy_store from existing ChromaDB data
├── .gitignore                        # Excludes venv, node_modules, .env, chroma data
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                # Root layout — mounts AppShell (sidebar + main content area)
│   │   ├── globals.css               # Global styles — Tailwind directives, warm cream palette
│   │   ├── page.tsx                  # Screen 1: Feed Memory (/)
│   │   ├── library/
│   │   │   └── page.tsx              # Screen 2: Library (/library)
│   │   ├── create/
│   │   │   └── page.tsx              # Screen 3: Create Post (/create)
│   │   ├── ideas/
│   │   │   └── page.tsx              # Screen 4: Get Ideas (/ideas)
│   │   ├── history/
│   │   │   ├── page.tsx              # Screen 5: History (/history)
│   │   │   └── [id]/
│   │   │       └── page.tsx          # Post detail (/history/[id])
│   │   └── welcome/
│   │       └── page.tsx              # Landing page (/welcome) — own top nav, no sidebar
│   ├── components/
│   │   ├── AppShell.tsx              # Layout wrapper — sidebar for app routes, passthrough for /welcome
│   │   ├── Sidebar.tsx               # Left sidebar — logo, five nav items, user row
│   │   ├── FeedMemory.tsx            # Feed Memory form — all input types, Obsidian vault flow
│   │   └── CreatePost.tsx            # Create Post — 4-state UI, settings drawer, split-screen analysis
│   ├── .env.local                    # Sets NEXT_PUBLIC_API_URL=http://localhost:8000
│   ├── tailwind.config.ts            # Tailwind config scoped to app/ and components/
│   └── package.json                  # Next.js 14 + TypeScript + Tailwind
│
└── backend/
    ├── main.py                       # FastAPI entry point — CORS, lifespan, router registration (~40 lines)
    ├── routers/
    │   ├── ingest.py                 # /ingest, /ingest-file, /scrape-and-ingest, /obsidian/*
    │   ├── generate.py               # /generate, /refine, /generate-visuals
    │   ├── history.py                # /history, /log-post, PATCH/DELETE/restore history
    │   ├── library.py                # /library, DELETE /library/source
    │   ├── ideas.py                  # /suggestions
    │   └── stats.py                  # /stats
    ├── requirements.txt              # All Python dependencies pinned
    ├── .env.example                  # Required env var keys with no values
    ├── agents/
    │   ├── ingestion_agent.py        # Chunks, tags, upserts content into ChromaDB
    │   ├── vision_agent.py           # Sends images to Claude vision for text extraction
    │   ├── visual_agent.py           # Parses [DIAGRAM:]/[IMAGE:] placeholders; generates SVGs
    │   ├── ideation_agent.py         # Multi-query diversity sampling + idea generation
    │   ├── retrieval_agent.py        # Semantic search node in the LangGraph pipeline
    │   ├── draft_agent.py            # Generates initial draft via Claude
    │   ├── humanizer_agent.py        # Rewrites draft to remove AI patterns; exposes refine_draft()
    │   └── scorer_agent.py           # Scores draft 0–100, robust JSON parse with fallback
    ├── pipeline/
    │   ├── state.py                  # TypedDict defining shared LangGraph pipeline state
    │   └── graph.py                  # LangGraph graph — nodes, edges, quality-aware routing
    ├── memory/
    │   ├── vector_store.py           # ChromaDB init, upsert, semantic query, get_all_sources, get_adjacent_chunks; per-user collections namespaced as contendo_{user_id}
    │   ├── hierarchy_store.py        # SQLite hierarchy.db — source_nodes + topic_nodes for hierarchical retrieval
    │   ├── profile_store.py          # profile.json load/save with defaults auto-created
    │   └── feedback_store.py         # SQLite posts + post_versions tables — history, versions, restore
    ├── tools/
    │   ├── scraper_tool.py           # URL scraper via Jina Reader — scrape_url(), clean_scraped_text()
    │   └── obsidian_tool.py          # Obsidian vault reader — read_vault(), get_vault_stats(), clean_obsidian_markdown()
    ├── utils/
    │   ├── chunker.py                # 500-word chunks with 50-word overlap
    │   ├── formatters.py             # Format + tone instruction strings per output type
    │   └── file_extractor.py         # PDF (PyMuPDF), DOCX (python-docx), TXT text extraction
    └── data/
        ├── profile.template.json     # Committed template — copy to profile.json to get started
        └── profile.json              # User voice + style profile (gitignored, auto-created if missing)
```

---

## Production Deployment

### Stack
- **Frontend** → Vercel
- **Backend** → Railway (Docker, persistent volume for data)

---

### 1 — Local Development (unchanged)

```bash
# Backend
cd backend
source venv/bin/activate
uvicorn main:app --reload          # http://localhost:8000

# Frontend (separate terminal)
cd frontend
npm run dev                        # http://localhost:3000
```

No extra env vars needed. `DATA_DIR` defaults to `backend/data/`.

---

### 2 — Backend Deployment to Railway

1. Push this repo to GitHub (or connect Railway to an existing repo).
2. In Railway, create a **New Service → GitHub repo**, set the **Root Directory** to `backend/`.
3. Railway auto-detects the `Dockerfile` — no extra config needed.
4. Set the following environment variables in Railway's dashboard:

| Variable | Value |
|----------|-------|
| `ANTHROPIC_API_KEY` | Your Anthropic key |
| `DATA_DIR` | `/data` |
| `ENVIRONMENT` | `production` |
| `FRONTEND_ORIGIN` | `https://your-app.vercel.app` (exact Vercel URL) |

Railway injects `$PORT` automatically — the `CMD` in the Dockerfile uses it.

> **First cold-start note:** the `all-MiniLM-L6-v2` embedding model (~90 MB) is downloaded from Hugging Face on first use, not baked into the Docker image. This keeps Railway build times fast. The model is cached by `sentence-transformers` inside the container after the first download. Expect the very first request that triggers embedding (any ingest or generate call) to take an extra 20–30 seconds. Subsequent restarts reuse the cache.

---

### 3 — Railway Persistent Volume Setup

1. In Railway, open your backend service → **Volumes** → **Add Volume**.
2. Set the mount path to `/data`.
3. Railway will persist everything written to `/data` across deploys.

> Your data files must be placed at the **top level of the volume** (not in a subdirectory):
> - `/data/chroma_db/` — ChromaDB vector store directory
> - `/data/posts.db` — post history SQLite database
> - `/data/hierarchy.db` — hierarchy store SQLite database
> - `/data/profile.json` — your voice and style profile

---

### 4 — Migrating Existing Local Data to Railway

Do this once before your first production deploy.

**Files to copy from your local machine:**

```
backend/data/chroma_db/        →  /data/chroma_db/
backend/data/posts.db          →  /data/posts.db
backend/data/hierarchy.db      →  /data/hierarchy.db
backend/data/profile.json      →  /data/profile.json
```

**How to copy via Railway CLI:**

```bash
# Install Railway CLI if you haven't already
npm install -g @railway/cli
railway login

# Link to your project
railway link

# Upload using railway run with a temporary data-copy approach:
# 1. Use `railway shell` to open a shell into your running container
# 2. Use `railway volume cp` or scp / rsync via a bastion if available

# Simplest approach: use Railway's web UI volume browser to upload
# files directly, then verify with:
railway run python scripts/check_data.py
```

**Verify the migration:**

```bash
# Locally, verify what you're about to upload:
cd backend
python ../scripts/check_data.py

# After upload, in Railway shell:
DATA_DIR=/data python /app/backend/../scripts/check_data.py
```

Expected output: all 4 files present, Chroma collection shows your chunk count, posts.db shows your post count.

---

### 5 — Frontend Deployment to Vercel

1. Import the GitHub repo into Vercel.
2. Set **Root Directory** to `frontend/`.
3. Set the following environment variable in Vercel's dashboard:

| Variable | Value |
|----------|-------|
| `NEXT_PUBLIC_API_URL` | `https://your-backend.up.railway.app` |

Vercel runs `npm run build` automatically. No other config needed.

---

### 6 — Obsidian Production Limitation

Obsidian vault ingestion reads directly from the local filesystem. It **cannot work** when the backend runs on a remote server (Railway).

- In production (`ENVIRONMENT=production`), the `/obsidian/preview` and `/obsidian/ingest` endpoints return a `400` with a clear explanation.
- The frontend hides the Obsidian tab automatically when `NEXT_PUBLIC_API_URL` points to a non-localhost backend.
- To use Obsidian ingestion: run the backend locally, ingest your vault, then deploy the populated data to Railway.

---

### 7 — Post-Deploy Smoke Test Checklist

After deploying:

- [ ] `GET https://your-backend.up.railway.app/health` returns `{"status": "ok"}`
- [ ] Frontend loads at your Vercel URL
- [ ] **Library** screen shows your existing sources and chunk count
- [ ] **History** screen shows your existing posts
- [ ] **Create Post** → generate a post on a test topic — confirm it completes without error
- [ ] **Get Ideas** → generate a few ideas — confirm they draw from your knowledge base
- [ ] **Feed Memory** → ingest a test article — confirm chunks stored
- [ ] Obsidian tab is absent (hidden) on the production frontend
- [ ] No CORS errors in browser DevTools console

---

## Documentation Guide

Two files exist at the project root specifically for developer and AI-assistant onboarding:

**`CODEBASE.md`** — the complete technical reference for this system. It contains every file's purpose, all agent input/output contracts, all API endpoint shapes, all data schemas, every architectural decision made and why, and an explicit list of what is not yet built. Any developer or AI assistant starting a new session should read this file before touching any code.

**`PROMPTS.md`** — the single source of truth for every agent's behaviour. It contains each agent's system prompt verbatim, the variables injected into each prompt, and the scorer's full rubric. When any prompt needs tuning, update `PROMPTS.md` first, then update the corresponding agent file to match. These two must never be out of sync.

**`DESIGN.md`** — the Editorial Atelier design system specification. Defines the full colour palette (Material Design tokens), typography rules (Noto Serif headlines + Inter body), the No-Line Rule, surface hierarchy, elevation model, and component specs for buttons, inputs, and cards. Mandatory reading before any frontend UI/UX change.
