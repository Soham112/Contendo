---
paths:
  - "backend/agents/**"
  - "backend/pipeline/**"
---

# Agent and pipeline rules

- Follow "Engineering standard: no cheap fixes" in CLAUDE.md before proposing any fix.
- Follow "Files and code organisation" in CLAUDE.md before creating a file or helper.
- PROMPTS.md holds every agent prompt verbatim. When a prompt changes, update PROMPTS.md and the agent file together; they must never diverge. Show me prompt diffs before applying them.
- Pipeline order (`backend/pipeline/graph.py`): load_profile → retrieval → plan (length target and perspective, computed once) → draft → critic → humanizer → predictability_audit → (polished only: scorer, loops to humanizer while score < 75 and iterations < 3) → word_count_enforcer → fact_checker (enforced in no-specifics mode; log-only in normal mode, see `config/fact_check.py`) → finalize.
- Pipeline state fields are declared in `backend/pipeline/state.py`. Add new fields there; don't remove existing ones without checking every reader.
- Don't change `max_tokens`, temperature, or which model a call uses unless the task says to.
- Specifics in generated posts (names, numbers, dates, incidents) must come from retrieved chunks or the profile. Never add prompt instructions that invite invented detail.
- Material first, then shape, then voice: sources decide which archetypes are allowed and the perspective (in code); archetype blocks are structure only; the profile reaches writing prompts as voice only (`profile_voice_context`); word lengths come only from `utils.formatters.WORD_RANGES` via `state["length_target"]`; tone is voice only. Never ask a model to count words.
- Calls that need a typed answer use `complete_structured()` with a pydantic schema. On failure return an explicit error or `None`; never a placeholder verdict or score.
