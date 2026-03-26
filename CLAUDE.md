# CLAUDE.md

> This file is read automatically by Claude Code at the start of every 
> session. Do not delete it.

---

## Read These First

Before touching any code, read these three files in order:

1. **CODEBASE.md** — full technical reference. Every file's purpose, 
   all API endpoint contracts, all data schemas, every architectural 
   decision made and why, and what is not built yet.

2. **PROMPTS.md** — every agent system prompt verbatim. Source of truth 
   for agent behaviour. If a prompt needs changing, update PROMPTS.md 
   first, then the agent file. They must never be out of sync.

3. **README.md** — architecture diagram, the five screens, agent pipeline 
   table, tech stack, setup instructions.

---

## Project Context

**What this is:** Contendo — a personal content generation system that 
learns a user's knowledge base and writes posts in their voice.

**Stack:**
- Frontend: Next.js 14 (App Router) in frontend/
- Backend: FastAPI (Python 3.11) in backend/
- LLM: Claude API (Anthropic)
- Vector DB: ChromaDB (local, persistent)
- Post history: SQLite
- Embeddings: sentence-transformers (local, no API key)
- Agent orchestration: LangGraph

**Current state:** Fully working locally. Not yet deployed. 
Single user. No auth layer yet.

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
- The implementation is always the source of truth if docs conflict

**Auth placeholder:**
- `user_id="default"` is hardcoded everywhere in main.py routers
- Do not change this until Clerk auth is explicitly added
- When Clerk is added, replace "default" with the JWT-extracted 
  user ID at each call site — no other files need to change

**ChromaDB:**
- Collections are namespaced as `contendo_{user_id}`
- Default collection is `contendo_default`
- Never use the old `contendo` collection name

**Backend structure:**
- Endpoints live in backend/routers/ — not in main.py
- main.py is CORS, lifespan, and router registration only (~40 lines)
- Each router imports only what it needs

---

## What Is Not Built Yet

These are explicitly out of scope until planned:
- User authentication (Clerk)
- Profile editing screen (profile.json is edited manually for now)
- Vercel + Railway deployment config
- LinkedIn / resume / GitHub onboarding flow
- Archetype override UI in Create Post
- Obsidian integration post-deployment

Do not build these unless explicitly asked.

---

## Current Branch Status

Check `git branch` and `git log --oneline -5` to orient yourself 
before starting any task. Always confirm which branch you are on 
before making changes.