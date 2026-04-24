# CLAUDE.md

> This file is read automatically by Claude Code at the start of every 
> session. Do not delete it.

---

## Read These First

Before touching any code, read these four files in order:

1. **CODEBASE.md** — full technical reference. Every file's purpose,
   all API endpoint contracts, all data schemas, every architectural
   decision made and why, and what is not built yet.

2. **PROMPTS.md** — every agent system prompt verbatim. Source of truth
   for agent behaviour. If a prompt needs changing, update PROMPTS.md
   first, then the agent file. They must never be out of sync.

3. **README.md** — architecture diagram, the five screens, agent pipeline
   table, tech stack, setup instructions.

4. **DESIGN.md** — the Editorial Atelier design system. Mandatory reading
   before any UI/UX work. Covers the full palette, typography rules
   (Noto Serif headlines + Inter body), the No-Line Rule, surface
   hierarchy, elevation, and component specs for buttons, inputs, and
   cards. Never deviate from it without explicit instruction.

---

## Project Context

**What this is:** Contendo — a personal content generation system that 
learns a user's knowledge base and writes posts in their voice.

**Stack:**
- Frontend: Next.js 14 (App Router) in frontend/
- Backend: FastAPI (Python 3.11) in backend/
- LLM: Claude API (Anthropic)
- Vector DB: Supabase pgvector (`embeddings` table)
- Post history: Supabase Postgres (`posts` + `post_versions`)
- Embeddings: sentence-transformers (local, no API key)
- Agent orchestration: LangGraph

**Current state:** Fully working locally and deployed to production.
Frontend on Vercel (contendo-six.vercel.app). Backend on Railway
(contendo-production.up.railway.app). Supabase JWT auth added — multi-user,
per-user data isolation. New-user flow at `/first-post` (`/onboarding` is
kept as a legacy redirect). Profile editor at `/settings`. Per-user profiles
are stored in the Supabase `profiles` table (`id` + `data` JSON).
Landing page (`/`) is the
default public entry point. Legacy `/welcome` remains available for backward
compatibility. Signed-in users can still visit `/welcome` via the sidebar
logo link and see auth-aware CTAs ("Open workspace" → `/create`).

---

## Non-Negotiable Rules

**Models:**
- All generation calls use `claude-sonnet-4-6` — never change this
- Archetype inference uses `claude-haiku-4-5-20251001` — fast 
  classification only
- Never introduce a different model without explicit instruction

**Git workflow:**
- Always work on feature branches — never commit directly to main
- Branch naming: `feature/description-of-work`
- Merge to main only when the feature is complete and tested

**Docs discipline:**
- After every change, update CODEBASE.md and PROMPTS.md to match
- README.md needs updating only if architecture or screens change
- DESIGN.md is the source of truth for all UI/UX decisions — read it before any frontend change
- The implementation is always the source of truth if docs conflict

**Auth (Supabase JWT):**
- All protected endpoints use `Depends(get_user_id_dep)` from `backend/auth/clerk.py` — Supabase JWT verification
- In non-production without a token, `user_id` falls back to `"default"` (local dev convenience)
- `SUPABASE_JWT_SECRET` is required in production for HS256 token verification
- Frontend: all API calls go through `useApi()` from `lib/api.ts` — never raw `fetch()`
- New users are redirected to `/first-post` by `useProfileCheck` in AppShell

**Vector storage:**
- Embeddings are stored in Supabase `embeddings` (pgvector) and always scoped by `user_id`
- Use `memory/vector_store.py` helpers for retrieval and upsert logic
- Do not reintroduce ChromaDB collection-based storage

**Backend structure:**
- Endpoints live in backend/routers/ — not in main.py
- main.py is CORS, lifespan, router registration, and logging config
- Each router imports only what it needs

---

## Current Branch Status

Check `git branch` and `git log --oneline -5` to orient yourself 
before starting any task. Always confirm which branch you are on 
before making changes.

<!-- code-review-graph MCP tools -->
## MCP Tools: code-review-graph

MCP GRAPH TOOLS — MANDATORY:
This project has a code-review-graph knowledge graph.

RULE 1 — For targeted fixes on known files:
Read the files directly. Do not use get_review_context.
"Read backend/agents/draft_agent.py and make these changes: ..."

RULE 2 — For feature work where you don't know the files yet:
Use semantic_search_nodes or query_graph to find relevant files first,
then read only those files.
"Use semantic_search_nodes to find where X is handled, 
then read only those files."

RULE 3 — get_review_context is only safe when there is a real git diff.
Never call it with base: "HEAD" on a clean branch — it scans everything
and will exceed token limits. Only use it for uncommitted changes or
a specific commit range.

RULE 4 — Never call get_review_context on more than 2 files at once.
Scope it to specific functions, not entire files.

Prompt template for new features:
Feature: [name]
Context: [1-2 sentences]
Use semantic_search_nodes for "[keyword]" to find relevant files,
then read only those files. Do not call get_review_context.
Changes needed:
1. ...
2. ...
Do not touch any other files.

Rule of thumb:
- Exploration (what calls this? blast radius?) → graph tools
- Reading known files → read directly
- Finding unknown files → semantic_search_nodes first

## HARD RULE — No Grep/Glob for exploration

NEVER use Grep, Glob, or Read to explore or find code.
This wastes tokens and is explicitly prohibited.

The only permitted navigation tools are:
- `semantic_search_nodes` — to find any function, class, or keyword
- `query_graph` — to trace callers, callees, imports
- `get_impact_radius` — before touching any shared file
- `get_architecture_overview` — to orient at session start (replaces reading CODEBASE.md in full)

The ONLY time you may use Read directly is when you already
know the exact file AND line range from graph tool output.

If you are about to write a Grep or Glob call — STOP.
Use `semantic_search_nodes` instead. Every time. No exceptions.

### Key Tools

| Tool | Use when |
|------|----------|
| `detect_changes` | Reviewing code changes — gives risk-scored analysis |
| `get_review_context` | Need source snippets for review — token-efficient |
| `get_impact_radius` | Understanding blast radius of a change |
| `get_affected_flows` | Finding which execution paths are impacted |
| `query_graph` | Tracing callers, callees, imports, tests, dependencies |
| `semantic_search_nodes` | Finding functions/classes by name or keyword |
| `get_architecture_overview` | Understanding high-level codebase structure |
| `refactor_tool` | Planning renames, finding dead code |

### Workflow

1. The graph auto-updates on file changes (via hooks).
2. Use `detect_changes` for code review.
3. Use `get_affected_flows` to understand impact.
4. Use `query_graph` pattern="tests_for" to check coverage.
