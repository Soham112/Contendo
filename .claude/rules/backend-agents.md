---
paths:
  - "backend/agents/**"
  - "backend/pipeline/**"
---

# Agent and pipeline rules

- PROMPTS.md holds every agent prompt verbatim. When a prompt changes, update PROMPTS.md and the agent file together; they must never diverge. Show me prompt diffs before applying them.
- Pipeline order (`backend/pipeline/graph.py`): load_profile → retrieval → draft → critic → humanizer → predictability_audit → (polished only: scorer, loops to humanizer while score < 75 and iterations < 3) → word_count_enforcer → finalize.
- Pipeline state fields are declared in `backend/pipeline/state.py`. Add new fields there; don't remove existing ones without checking every reader.
- Don't change `max_tokens`, temperature, or which model a call uses unless the task says to.
- Specifics in generated posts (names, numbers, dates, incidents) must come from retrieved chunks or the profile. Never add prompt instructions that invite invented detail.
