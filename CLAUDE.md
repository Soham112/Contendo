# Contendo

Personal AI content system: learns a user's knowledge base and writes posts in their voice.
Frontend on Vercel (contendo-six.vercel.app), backend on Railway (contendo-production.up.railway.app).

<!-- Keep this file under ~100 lines. Area-specific rules live in .claude/rules/ and load
     only when Claude works in matching paths. Multi-step procedures belong in skills. -->

## Engineering standard: no cheap fixes

A cheap fix makes a failing case pass without addressing why it failed. Don't ship them. Examples from this codebase:
- Adding words to a verb list to catch first-person incidents ("walked", "hiked"…). Language is open-ended; the list will always miss phrasings. Events need a semantic check, not patterns.
- Hard-coding a threshold or special case so one golden passes.
- Loosening a check until a test goes green without knowing why it failed.
- Patching symptoms in a later pipeline step (stripping invented facts in the humanizer) when an earlier step (the critic) creates them.

Before proposing a fix:
1. Find the root cause: which step, prompt, data or assumption produced the failure? Show the evidence (trace, test, log).
2. Match the tool to the problem: closed-vocabulary things (numbers, dates, money, formats) → deterministic code; open-ended meaning (events, claims, topic, voice) → semantic checks or model judgement.
3. Prefer fixing the source over adding a filter downstream.
4. Check that the fix generalises: test it on cases beyond the one that failed, including true negatives.
5. If the only option available right now is a stopgap, say so explicitly, label it "stopgap" in code and in your summary, and propose the proper fix with its cost. Never present a stopgap as the solution.
6. State the trade-offs (accuracy, latency, cost, complexity) when you propose a change.

Every task summary must end with a "Stopgaps introduced" line: "none", or a list with file:line, why it's a stopgap, and the proper fix.

## Stack
- Frontend: Next.js 14 App Router, `frontend/`
- Backend: FastAPI, Python 3.11, `backend/` (venv at `backend/venv/`), Docker on Railway, one uvicorn worker
- Auth: Supabase Auth (Google OAuth). Backend verifies Supabase JWTs in `backend/auth/supabase_jwt.py`
- Data: Supabase Postgres + pgvector for everything (embeddings, profiles, posts, post_versions, hierarchy, entities, experience nodes, usage and analytics events)
- Retrieval: hybrid pgvector cosine + BM25 fused with RRF, in `backend/memory/vector_store.py`
- Embeddings: sentence-transformers all-MiniLM-L6-v2, local
- Orchestration: LangGraph, `backend/pipeline/graph.py`

## Commands
- Backend: `cd backend && source venv/bin/activate && uvicorn main:app --reload` (port 8000)
- Frontend: `cd frontend && npm run dev` (port 3000)
- Frontend type check: `cd frontend && npx tsc --noEmit`
- Frontend build check: `cd frontend && npm run build`
- Backend tests: `cd backend && source venv/bin/activate && pytest` (install once with `pip install -r requirements-dev.txt`)

## Tests
- Tests live in `backend/tests/` and run against fakes set up in `tests/conftest.py`: in-memory Supabase, fake Claude, fake embedder, no network. They never touch real data or spend API credits.
- In a test, queue every Claude response the code path needs with `claude.queue(...)`; an unexpected call fails the test.
- New backend behaviour gets a test. Run `pytest` before reporting a backend task done.
- To find untested edge cases in a change, use the `tester` subagent (`.claude/agents/tester.md`). It writes tests only and reports bugs instead of fixing application code.
- Tests marked `xfail(strict=True)` document known bugs. When a fix makes one pass, pytest reports it as a failure: remove the `xfail` marker (or the `KNOWN_UNPROTECTED` entry) in the same change.

## Finding code
- Search first with Grep or Glob, then Read only the line range you need. Don't read whole long files.
- Known long files, always read by range: `frontend/components/CreatePost.tsx`,
  `frontend/app/first-post/page.tsx`, `frontend/components/FeedMemory.tsx`,
  `backend/memory/vector_store.py`, `backend/agents/retrieval_agent.py`.
- Reference docs, looked up by section when needed, never read in full:
  - `CODEBASE.md`: 1 File registry · 2 Agent contracts · 3 API contract · 4 Data schemas · 5 Known decisions · 6 Not built yet
  - `PROMPTS.md`: every agent prompt verbatim
  - `DESIGN.md`: design system (see `.claude/rules/frontend.md`)

## Rules
- Models: `claude-sonnet-4-6` for generation, `claude-haiku-4-5-20251001` for classification. Never change or add models without explicit instruction.
- All Claude calls go through `complete()` in `backend/llm/client.py` (model constants `SONNET`/`HAIKU`, one shared client, usage logging). Never create an `anthropic.Anthropic` client or write a model string anywhere else; every call passes `user_id` and an `event_type`.
- Every protected endpoint uses `Depends(get_user_id_dep)`. Never use `user_id="default"` in production paths (it's a local-dev fallback only).
- The backend uses the Supabase service-role key, which bypasses RLS. Every query must filter by `user_id` or verify ownership first.
- Async route handlers must not call slow sync code (Claude calls, ingestion) directly; wrap it with `run_in_threadpool`. One blocked request blocks the whole server.
- Endpoints live in `backend/routers/`. `main.py` only does CORS, lifespan, logging, and router registration.
- SQL changes go in `backend/migrations/NNN_description.sql`, numbered after the highest existing file.
- Never edit `.env` files or `backend/data/profile.json`.

## Git
- I create branches, commit, and push myself. Don't run `git commit`, `git push`, or create branches (commit and push are blocked in settings anyway).
- The code is the source of truth. If docs disagree with it, say so.

## When a task is done
- Update the matching sections of CODEBASE.md, and PROMPTS.md if any prompt changed.
- Report: files changed, a short diff summary, anything you were unsure about, and exact commands for me to verify locally.
