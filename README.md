# Contendo

A personal content generation system that learns your knowledge base and writes in your voice. You feed it articles, YouTube videos, images, and notes — it stores them as semantic memory. When you want to publish, it retrieves the most relevant knowledge, drafts content in your style, humanizes it, scores it, and hands you a final editable post.

Built for a single user. No auth, no bloat — just a fast loop from raw knowledge to publishable content.

---

## Architecture

```mermaid
flowchart TD
    subgraph UI["Frontend (Next.js 14) — 4 Screens"]
        S1["Screen 1: Feed Memory\n(Article / URL / File / YouTube / Image / Note / Obsidian)"]
        S2["Screen 2: Library\n(Source cards, stats, filter/sort)"]
        S3["Screen 3: Create Post\n(Topic / Format / Tone / Ideas / Refine)"]
        S4["Screen 4: History\n(Versioned posts, restore, delete, diagrams)"]
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
        N3["3. draft_node\nClaude generates initial draft"]
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

    S1 --> R1
    S1 --> R1b
    S1 --> R8
    S2 --> R5
    S3 --> R2
    S3 --> R2b
    S3 --> R3
    S3 --> R6
    S3 --> R7
    S4 --> R4

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

## The Four Screens

**Screen 1 — Feed Memory (`/`):** The user selects an input type (Article/Text, URL, File, YouTube, Image/Diagram, Note, or Obsidian vault) and adds their content. For **URL**, the backend scrapes the page via Jina Reader and stores it automatically. For **File**, PDF, DOCX, and TXT uploads (up to 10 MB) are accepted — text is extracted server-side. For **Image/Diagram**, Claude vision extracts the knowledge as text first. For **Obsidian**, the user enters their local vault folder path; a preview step shows how many notes and words will be ingested before committing. The YouTube tab shows a textarea for manual paste — auto-fetching was removed after YouTube blocked bot-based transcript retrieval. For all types, content is chunked into 500-word overlapping segments, embedded locally with `sentence-transformers`, and upserted into ChromaDB. The response shows how many chunks were stored and what tags were auto-extracted.

**Screen 2 — Library (`/library`):** Shows everything the user has fed into memory, grouped by source (one card per ingest call, not per chunk). A stats bar shows total sources, total chunks, and unique tag count. Source cards display the type badge (Article/Note/Image/YouTube), title derived from the first 80 characters of the content, date added, chunk count, and tag pills. Filterable by source type, sortable newest/oldest. This gives the user full visibility into what knowledge the system has before generating a post.

**Screen 3 — Create Post (`/create`):** The user enters a topic, picks a format (LinkedIn Post, Medium Article, or Thread), sets a tone (Casual, Technical, or Storytelling), and optionally adds context. "Get Ideas" runs multi-query diversity sampling across the full knowledge base and returns up to 15 content suggestions — filterable by topic — that persist in the session until dismissed. The backend runs the full LangGraph pipeline — retrieving relevant knowledge, drafting in the user's voice, humanizing, and scoring. Default quality is **standard** (one humanizer pass, one scorer pass); **polished** mode runs up to three humanizer iterations with automatic retry if the score is below 75. The final post appears in an editable textarea alongside an authenticity score (0–100) and specific feedback. "Refine draft" sends targeted instructions to the humanizer for a focused one-pass fix without rerunning the full pipeline. "Generate visuals" parses `[DIAGRAM:]` and `[IMAGE:]` placeholders and generates SVGs via Claude. Posts are **auto-saved** to history immediately after generation — no manual save step required. Session state (post, score, visuals, ideas) persists in sessionStorage so navigating away and back restores the last session.

**Screen 4 — History (`/history`):** All auto-saved posts, newest first. Each card shows topic, format/tone badges, authenticity score, and date. Every generation creates version 1; every refinement creates the next version. Version pills in the card header show the score for each version (color-coded green/amber/red) with the best version starred. Clicking a pill switches the expanded view to that version's content. Any version can be restored to Create Post with one click. Cards can be deleted with a confirmation step. If SVG diagrams were saved alongside the post, they are rendered inline in the expanded view with an "Open as PNG" button.

---

## Agent Pipeline

| Step | Agent | Job |
|------|-------|-----|
| 1 | `load_profile_node` | Reads `profile.json`, injects user voice and style into state. Also loads all previously posted topics from SQLite to prevent repeated angles. |
| 2 | `retrieval_node` | Queries ChromaDB for the 8 most semantically relevant chunks; filters out anything below 0.3 cosine similarity |
| 3 | `draft_node` | Calls Claude to produce an initial draft using the user profile, retrieved chunks, format-specific instructions, and mandatory visual placeholder rules |
| 4 | `humanizer_node` | Calls Claude to strip AI writing patterns, vary sentence structure, and inject the user's authentic voice. Also exposes `refine_draft()` for targeted post-generation edits via `/refine` |
| 5 | `scorer_node` | Calls Claude to score the draft 0–100 across 5 dimensions; uses 3-attempt JSON parse to handle markdown-wrapped responses |
| 6 | Conditional | **draft** mode: skip humanizer and scorer entirely, return raw draft. **standard** mode (default): always finalize after one pass. **polished** mode: retry humanizer if score < 75 and iterations < 3. |

---

## Tech Stack

| Layer | Tool | Why |
|-------|------|-----|
| Frontend | Next.js 14 (App Router) | File-based routing, RSC-ready, deploys instantly to Vercel |
| Styling | TailwindCSS | Utility-first, zero config, great with Next.js |
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
├── .gitignore                        # Excludes venv, node_modules, .env, chroma data
│
├── frontend/
│   ├── app/
│   │   ├── layout.tsx                # Root layout — nav bar for all four screens
│   │   ├── globals.css               # Global styles — Tailwind directives, light theme
│   │   ├── page.tsx                  # Screen 1: Feed Memory (/)
│   │   ├── library/
│   │   │   └── page.tsx              # Screen 2: Library (/library)
│   │   ├── create/
│   │   │   └── page.tsx              # Screen 3: Create Post (/create)
│   │   └── history/
│   │       └── page.tsx              # Screen 4: History (/history)
│   ├── components/
│   │   ├── FeedMemory.tsx            # Feed Memory form — all input types, Obsidian vault flow
│   │   └── CreatePost.tsx            # Create Post — topic, format, tone, ideas, visuals, refine, output
│   ├── .env.local                    # Sets NEXT_PUBLIC_API_URL=http://localhost:8000
│   ├── tailwind.config.ts            # Tailwind config scoped to app/ and components/
│   └── package.json                  # Next.js 14 + TypeScript + Tailwind
│
└── backend/
    ├── main.py                       # FastAPI app — all API routes + CORS config
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
    │   ├── vector_store.py           # ChromaDB init, upsert, semantic query, get_all_sources
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

## Documentation Guide

Two files exist at the project root specifically for developer and AI-assistant onboarding:

**`CODEBASE.md`** — the complete technical reference for this system. It contains every file's purpose, all agent input/output contracts, all API endpoint shapes, all data schemas, every architectural decision made and why, and an explicit list of what is not yet built. Any developer or AI assistant starting a new session should read this file before touching any code.

**`PROMPTS.md`** — the single source of truth for every agent's behaviour. It contains each agent's system prompt verbatim, the variables injected into each prompt, and the scorer's full rubric. When any prompt needs tuning, update `PROMPTS.md` first, then update the corresponding agent file to match. These two must never be out of sync.
