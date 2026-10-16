# Prompt for Claude Code — Contendo generation architecture upgrade

You are working in the Contendo repo. Backend: FastAPI on Python 3.11 (backend/), LangGraph pipeline, Supabase Postgres with pgvector, hybrid pgvector + BM25 retrieval with RRF. Frontend: Next.js 14 App Router (frontend/). The code is the source of truth; CODEBASE.md, PROMPTS.md and DESIGN.md are reference docs that can lag behind it. Do not commit or push: I create branches, commit and push myself. Every phase below is its own branch and PR.

First, save this entire prompt to `docs/GENERATION_ARCHITECTURE.md` so it is the reference spec for every phase. Then start with Phase 0.

---

## 1. Goal

Contendo writes LinkedIn posts (later X and other platforms) in a user's own voice, grounded in what they actually know and have experienced. The goal is to move from:

> Topic + user knowledge → retrieved context → grounded post

to:

> Topic + user knowledge + personal experience + writing identity + content strategy → personalized post

and eventually:

> Personalized post + user edits + publishing performance → a writing system that improves for each user over time.

The system should answer one question per generation: *given what this person wants to talk about, what they actually know and have experienced, how they naturally write, what they have posted recently, and what has worked for them before, what is the strongest authentic way for them to express this idea today?*

Hard constraints:
- **Latency:** p95 end to end ≤ 10 s, target ~5 s. The user sees the first text within ~1–2 s (streaming).
- **Quality:** writing quality and grounding must not fall below today's C-Opus (it won a blind ablation on 10 of 10 goldens on 2026-10-10).
- **Grounding:** never fabricate experiences, numbers, customers or claims. Keep every existing grounding protection.

---

## 2. What exists today (verify each point; flag anything I have wrong)

- Live variant is **C-Opus** (`config/features.py`): load_profile → retrieval → plan → `structure` (archetype choice, SMALL_MODEL = Haiku 4.5) → cited draft (Opus 5.5) → strip → finalise → checks → compress (only when over the word maximum) → recheck. So a normal generation is 2 sequential model calls, 3 when compress runs.
- `llm/models.py`: Opus 5.5 has thinking **on** by default, effort "medium". Thinking tokens are generated before any post text.
- `/generate` does not stream.
- `llm/client.py` records `latency_ms` per model call into traces. Per-step `step_timings` are only wired for variant B, not C.
- `agents/archetype_agent.py` already selects a structure from the evidence and blocks personal-story archetypes when there is no first-person evidence. **Keep this rule.**
- `agents/retrieval_agent.py`: hybrid retrieval (n_results=8) plus entity enrichment (up to 4 more chunks), experience nodes, source context.
- `memory/profile_store.py`: voice lines and up to 10 writing samples. This is a partial writer fingerprint; **extend it, don't duplicate it**.
- `memory/experience_store.py`: experience nodes. **Extend them**, don't build a parallel store.
- Ingestion (`agents/ingestion_agent.py`): chunking, tags, memory-context classification, embeddings, entity extraction and relationships, consolidation, source/topic hierarchy.
- `pipeline/compress.py`: numbers sentences, has the model return replacements for chosen sentences only, and splices them in with checks that nothing else changed. Reuse this machinery for the sentence-level refine feature.
- evals/: ablation, blind read, goldens, judge. Generation traces and versioned post history exist.
- Publishing is via Zernio (`publishing/`).
- Thin data today: `coverage_gate` in `agents/retrieval_agent.py` blocks drafting on low coverage (`low_coverage` returns an empty post plus closest sources and a suggestion). The exceptions are a user's first post (`skipped_first_post`, written from profile and onboarding answers) and no-specifics mode, which is disabled (`NO_SPECIFICS_MODE_ENABLED = False`) because after-the-fact fixes created dangling references.

Scope note: this spec is backend only. UI/UX is redesigned separately, after the backend reliably produces high-quality posts fast. Any frontend change in these phases is the minimum needed to expose a backend feature (streaming, follow-up questions, alternative hooks).

Keep: FastAPI, Supabase/pgvector, LangGraph, source attribution, first-person grounding rules, knowledge hierarchy, traces, post history, the evals framework, and `PIPELINE_VARIANT=A` as the rollback switch. No microservices: this is a modular monolith.

---

## 3. Target architecture

```
                 OFFLINE / ASYNC (ingestion, background jobs, small models OK)
LinkedIn profile + posts (Apify or Zernio) / articles / website / uploads
   → normalize [code] → chunk + embed [embedding model] → classify + extract [small model]
   → CREATOR / BRAND INTELLIGENCE (stored, cached, versioned):
       writing fingerprint · style examples · experience events · beliefs
       · expertise / authority map · business profile · recent strategy history
       · post performance

                 ONLINE / GENERATION (request path)
topic + identity
   → in parallel: cached fingerprint [no LLM] · purpose-split hybrid retrieval [no generative LLM]
                  · recent strategy history [DB] · authority lookup [DB]
   → deterministic context assembly + eligibility rules [code]
   → ONE Opus call: central idea → angle → structure → hook → draft → compression pass
   → stream to the user
   → deterministic checks [code] (grounding, length, repetition, no copying)
   → final post + strategy record stored
```

Principle: **do as much understanding as possible before the user clicks Generate.** Spend the intelligence budget once, on judgment and writing.

---

## 4. Model routing

Don't use an LLM because an LLM *can* do the task. If SQL, embeddings, regex, metadata or plain code can answer it reliably, use those.

| Task | Use |
|---|---|
| Parse Apify / Zernio JSON, normalize LinkedIn data, dedupe, metadata filters, word count | Code |
| Embeddings, vector search, keyword/BM25 search | Embedding model + DB |
| Topic classification | Embeddings or small model (offline) |
| Experience, belief, entity, achievement, business-fact extraction | Small model (offline) |
| Writing fingerprint, business profile | Small/medium model (offline, background job) |
| Retrieval reranking | Deterministic first; small model only if evals show a real gain |
| Angle, structure, hook, narrative decisions, writing, compression | Opus, in the one generation call |
| Grounding validation, duplicate/copy detection | Code + source metadata + embeddings |
| Synchronous quality judge | Avoid on the request path unless the evals justify it |

Do **not** chain Haiku → Sonnet → Opus on the request path. Each hop adds latency and an information bottleneck: if an early model misreads the request, Opus writes the wrong post well. Whether today's Haiku structure call earns its time is decided by the Phase 1 experiment, not assumed.

---

## 5. Identities (person and business)

Identity belongs to the account, not to each post. Onboarding asks once: personal, business, or both. A user can have one personal identity and any number of business identities, and picks one at generation time (default: last used).

```json
{
  "identity_id": "...",
  "identity_type": "person | business",
  "voice_profile": {},
  "knowledge_profile": {},
  "experience_profile": {},
  "authority_map": {},
  "content_history": {}
}
```

- **Personal (creator model):** career, projects, experiences, opinions, expertise, achievements, stories, voice, vocabulary, previous posts. Seeded from the LinkedIn profile import.
- **Business (brand model):** company description, products, features, customers, positioning, industry, competitors, founder philosophy, case studies, announcements, product updates, brand voice, previous company posts, website and articles.

The same generation engine serves both; only the identity's data and constraints differ. Example: the topic "AI evaluations" written as a person might be "Building AI products changed how I think about evals…", and written as the business it might be "AI-generated content has a quality-control problem." Never invent customer names, results or claims for a business.

---

## 6. Creator intelligence (offline)

Computed asynchronously on ingestion or profile import, versioned (e.g. `writer_profile_v7`), never recomputed on the request path. Generation must not wait for ingestion work.

### 6.1 Writing fingerprint (extend `profile_store`)
```json
{
  "tone": ["conversational", "technical but accessible", "opinionated"],
  "technical_depth": "medium",
  "sentence_length": "short",
  "paragraph_style": "compact | one-line paragraphs frequent",
  "emoji_frequency": "rare",
  "rhetorical_questions": "rare",
  "vocabulary": {"technical_ok": true, "avoids_corporate_jargon": true, "signature_phrases": []},
  "preferred_openings": ["observation", "personal_experience"],
  "preferred_structures": ["observation_to_insight", "problem_to_solution"],
  "hook_preferences": {"observation": "high", "contrarian": "medium", "confession": "low", "clickbait": "very_low"},
  "cta_style": "minimal | ends with an observation or question",
  "typical_topics": [],
  "style_examples": ["2-3 post ids chosen for stylistic diversity"]
}
```
Compile it into a compact generation profile of **300–600 tokens** for the prompt. Don't inject the full object.

### 6.2 Experience events (extend `experience_store`)
An entity ("ContentoAI") is not an experience. An experience is something that happened:
```json
{
  "experience_id": "exp_123",
  "identity_id": "...",
  "project": "ContentoAI",
  "event": "Encountered inconsistent generation quality",
  "action": "Introduced an evaluation process",
  "outcome": "Could compare outputs reliably",
  "topics": ["AI", "LLM evaluation"],
  "date": "2026-08",
  "source_id": "source_456",
  "verification": "user_authored | user_stated | inferred",
  "confidence": 0.9
}
```
Only `user_authored` or `user_stated` experiences may support first-person claims. Confidence must be calibrated if any decision uses it; otherwise drop the field.

### 6.3 Beliefs / opinions
```json
{"belief_id": "...", "topics": ["AI", "software"], "belief": "...", "strength": "strong | moderate", "source_id": "...", "date": "..."}
```

### 6.4 Authority map
From the profile, posts and projects, record which topics the person has real grounds to speak on (e.g. *AI evals → built ContentoAI → high*; *VC fundraising → no evidence → low*). This constrains strategy:
- **High authority:** experience, opinion, framework, lesson, strong claim.
- **Low authority:** observation, analysis, question, synthesis. Never "Here's what founders get wrong about raising $10M" with no basis in the profile.

### 6.5 Recent strategy history
For each identity, store the angle, hook type, structure, CTA type and opening line of the last ~10 posts. This feeds the repetition penalty and is passed to generation as a tiny summary.

### 6.6 Cold start: users with little or no data
This is a real case, not a rare one: a new user who hasn't connected LinkedIn, uploaded anything or written much, or an established user asking about a topic their knowledge base doesn't cover. The system must still produce a good, honest post, never a fabricated one and never a dead end.

**Data tiers (computed per identity and per request):**
| Tier | What exists | Behavior |
|---|---|---|
| 0 | Account only, no onboarding answers | Ask the onboarding essentials first (role, what they work on, who they write for, 1–3 topics) |
| 1 | Onboarding answers / profile, no sources | Draft from profile + follow-up answers |
| 2 | Some sources, but low coverage for this topic | Follow-up questions for this topic, then draft |
| 3 | Rich sources, covered topic | Normal path |

**Adaptive follow-up questions instead of blocking.** When the coverage gate says `low_coverage`, don't return an empty post. Return 2–3 short questions specific to the topic, answerable by typing or voice, e.g. "What's your own take on this?", "Has something happened to you or your team related to this?", "Is there one specific example, number or result you're comfortable sharing?" Each is optional, and the user can skip all of them.
- The user's answers are saved as `user_stated` memories (beliefs and experience events with `verification: user_stated`), so they become citeable sources for cited drafting and grow the knowledge base for future posts. This is the proper fix for why no-specifics mode was disabled: the post cites real stored statements instead of being repaired afterwards. Decide in Phase 0 whether no-specifics mode can be retired in favor of this or should be rebuilt on top of it.
- Generating the questions: prefer a small set of question templates per eligible angle, filled with the topic (no model call). Use one small-model call only if the evals show templates produce noticeably worse questions; this path is interactive anyway, so it's off the 5-second budget.

**Angle restrictions when data is thin.** With no first-person evidence, only observation, opinion (if the user stated one), question, analysis and synthesis are eligible; the eligibility gate already enforces this. If the user skips every question, write an observation/analysis post from general knowledge in their stated role's voice, with no first-person claims and no invented specifics, and say so in the response so the frontend can show "Answer a question to make this more personal."

**Voice with little data.** Until there are enough posts for a fingerprint, use a starter voice built from onboarding: let the user paste 1–3 things they've written (any post, email or note) or pick from a few tone options. Mark the fingerprint as `provisional` and rebuild it automatically as posts are accepted, edited and published.

**LinkedIn import as the fastest way out of cold start.** Offer the import (Apify or Zernio) at onboarding and again when a user hits Tier 1–2, since it moves most users from Tier 1 to Tier 3 in one step.

Add cold-start cases to the eval set (Tier 1 and Tier 2 users, with and without answered questions) and check that no first-person claim appears without a stored source.

---

## 7. Retrieval (online, no generative LLM)

Separate retrieval by purpose. Run the queries concurrently (`asyncio.gather` or equivalent), not one after another.

| Purpose | Question it answers | Typical count |
|---|---|---|
| Knowledge | What does this person know or believe about the topic? | 2–3 |
| Experience | What actually happened to them that's relevant? | 1–2 |
| Beliefs | What's their opinion on this? | 0–2 |
| Style | Which posts best show how they write, regardless of topic? | 2 (from the fingerprint's style examples; cached) |
| Recent history | What angles and hooks did they use lately? | summary only |

Retrieval returns one bounded context object, never a flat list of all chunks:
```json
{
  "knowledge": ["Relevant fact 1", "Relevant fact 2"],
  "experiences": ["Relevant verified experience"],
  "beliefs": ["Relevant stated opinion"],
  "style_examples": ["Representative post"],
  "writer_fingerprint": {}
}
```
Each item keeps its source id so cited drafting still works. The most important change is relevance by purpose, not retrieving more content.

Database round trips: retrieval today can make several sequential DB calls (hybrid query, entity id lookup, entity-linked chunk fetch, experience nodes, source context). Phase 0 reports the time for each. Run independent ones concurrently, fetch what's needed in as few queries as possible, and serve the fingerprint and style examples from cache.

Ranking per candidate (start deterministic; the weights are hypotheses to tune with evals):
```
retrieval_score = semantic_similarity + keyword_match + topic_match
                + recency + personal_relevance + source_quality
```
Metadata on every chunk: `type` (knowledge | experience | opinion | post), `topics`, `source`, `date`, `engagement`, `personal`, `user_authored`. For a personal post, a real experience should usually outrank an informationally similar article.

Flow: vector + lexical → top ~20 → deterministic rank → top 4–6 into the prompt. Keep the existing entity enrichment only if it measurably improves results, and keep the total context bounded.

### 7.1 How many chunks go into the prompt (decide by measurement, not by guess)
Today `retrieval_node` asks `query_similar_hybrid` for `n_results=8`, then `_enrich_with_entity_chunks` adds up to `max_additional=4` entity-linked chunks, so up to **12 chunks** can reach the drafter (after the `RELEVANCE_THRESHOLD = 0.30` filter in `config/retrieval.py`). The 4–6 target above is a hypothesis. Settle it with an experiment on the goldens, holding everything else fixed:

| Setting | Values to test |
|---|---|
| Hybrid candidates passed to the drafter | 4, 6, 8 (today), 12 |
| Entity enrichment | off, +2, +4 (today) |
| Purpose quotas | none (today) vs knowledge 2–3 + experience 1–2 + belief 0–2 + style 2 |
| Relevance floor | 0.30 (today) vs a higher floor for the extra chunks beyond the top 3 |

Measure for each: grounding failures from the existing checks, whether the post used the most relevant experience, blind-read ranking, input tokens, retrieval_ms and draft_ms. Report how many retrieved chunks the draft actually cites (citation markers make this measurable): if posts typically cite 2–3 of 12 chunks, the other chunks cost latency and attention for nothing.

Also report chunk size and overlap from ingestion, and whether an experience or opinion tends to be split across chunks; if so, that's an ingestion fix (chunk by meaning/event), not something to compensate for by retrieving more chunks.

Selection rule: the smallest setting whose grounding and blind ranking are not worse than today. Put the chosen numbers in `config/retrieval.py` as named constants with a comment recording the eval run that chose them, like the existing thresholds.

### 7.2 Keyword index requirements (from quality_v1 case re-05, 2026-10-16)
Evidence: re-05 (persona `re`, "What higher mortgage rates mean for buyers in Ashby"). With two consolidation briefs in the library, the needed source `re-bp` ranked 1; without them, 4. Its own scores barely moved (cosine 0.3998 both; BM25 1.68 → 1.62). The briefs mention "ashby", taking it to 6 of 12 rows, where BM25 Okapi's IDF is exactly 0, so `re-s01`, `re-s03`, `re-s05` scored 0 on keywords; without the briefs "ashby" weighs 0.368 and `re-s01` rises above `re-bp` in RRF. Recomputed scores match the recorded runs exactly (`evals/baselines/2026-10-16-consolidation-ablation.md`).

1. **The keyword index holds only real source chunks, never derived rows** (consolidation briefs, summaries, anything generated from the library). Derived rows change every term's document frequency, so they re-rank the user's real sources without adding any.
2. **Use an IDF that stays positive.** BM25 Okapi as implemented by `rank_bm25` computes ln((N − n + 0.5)/(n + 0.5)): exactly 0 for a word in half the library, and for a word in more than half it substitutes 0.25 × the library's average IDF (so a word in 7 of 12 rows outweighs one in 6 of 12). In small libraries the user's own recurring terms (their town, company, project names) get little or no keyword weight, which works against their own notes. When keyword search moves into Postgres, use the Lucene form, log(1 + (N − n + 0.5)/(n + 0.5)), which is positive and decreasing in n. The coverage-gate and relevance thresholds (`config/retrieval.py`) were tuned on today's scores: re-measure them on quality_v1 with the new IDF before switching, not after.

---

## 8. Strategy selection

Three separate decisions, all made inside the one Opus call:
1. **Angle:** what perspective the post takes.
2. **Structure:** how the information is ordered.
3. **Hook strategy:** how the post opens.

The hook comes after the angle and must represent the actual post. (Topic: AI coding. Evidence: the user disliked AI coding tools, then adopted Claude Code daily. Angle: changed my mind. Structure: old belief → event → new belief → lesson. Hook: confession/reversal — "I was wrong about AI coding tools." Not a separately chosen contrarian hook like "AI coding is making engineers worse.") The post's angle can be observational while its hook is contrarian.

### 8.1 Angle taxonomy
personal_story · contrarian_opinion · mistake_lesson · confession · unexpected_result · observation · how_to · framework · case_study · before_after · prediction · myth_busting · analysis · list · failure_to_realization · changed_my_mind

### 8.2 Hook taxonomy (with examples of the pattern, not text to reuse)
- contrarian: "Most startups don't need AI."
- confession: "I made a stupid mistake building my first AI product."
- mistake: "I wasted 3 months building the wrong feature."
- unexpected_result: "We removed our most popular feature. Retention went up."
- curiosity: "One change doubled our response rate."
- specific_result: "17 users taught me more than 6 months of research."
- observation: "I've noticed something strange about AI startups."
- question: "Why do so many AI products feel the same?"
- story: "Last Tuesday, a user sent me a message."
- direct_value: "Here's the framework I use to evaluate LLM outputs."

### 8.3 Structure library
- hook → problem → failed attempt → realization → lesson → CTA
- claim → evidence → explanation → implication
- observation → examples → pattern → takeaway
- old belief → event → new belief → lesson
- context → problem → attempts → tension → discovery → lesson
- hook → tension/context → value/payoff → CTA (default; AIDA: attention → interest → desire → action)

Store taxonomies and structures as config data (e.g. `config/strategy.py` or a YAML file), not inline in prompts, so they can be tuned without code changes.

### 8.4 Eligibility gate (code, before the call — a hard rule, not a score)
The available evidence determines which angles are eligible:

| Available material | Eligible / favored angles |
|---|---|
| Verified personal experience | story, mistake, lesson, confession, changed_my_mind |
| Failure | mistake, failure_to_realization |
| Surprising metric (user-provided) | unexpected_result, specific_result hook |
| Strong opposing belief | contrarian |
| Detailed expertise | how_to, framework |
| Process | framework |
| Company/project result | case_study |
| Strong opinion | opinion, contrarian |
| Weak context, low authority | observation, analysis, question |

No first-person angle without first-person evidence. Engagement potential can never outweigh this.

### 8.5 Ranking among eligible angles (inside the call, guided)
Starting hypothesis, not empirically established values:
```
strategy_score = 0.30*evidence_fit + 0.20*topic_fit + 0.15*voice_fit
               + 0.15*objective_fit + 0.10*historical_performance + 0.10*novelty
               - repetition_penalty
```
- `repetition_penalty`: from recent strategy history. If the last posts were mistake, story, mistake, contrarian, story, penalize mistake and story. This gives feed-level diversity, not only per-post quality.
- `historical_performance`: 0 until the learning loop has data (Phase 7).
- Later, when there's enough usage data, parts of this can move from the LLM into a learned ranker.

### 8.6 CTA selection
Choose by objective: discussion ("What's been your experience?") · reflection · share ("Send this to someone building their first startup") · follow · resource · product · **none** (end on the strongest insight). Never append generic engagement bait automatically. Respect the fingerprint's CTA style.

---

## 9. Writing rules

Three levels. Don't put 150 rules in one prompt; give structured context plus these.

### Level 1 — Hard rules (code enforces; never suggestions)
1. No fabricated personal experiences.
2. No fabricated numbers, dates, names, customers or results. If the user hasn't supplied specifics, leave them out or ask for them.
3. Never attribute an article to the user unless they authored it.
4. Stay within the requested length.
5. Don't repeat a recent post (embedding similarity against recent posts above a threshold → flag).
6. Don't copy retrieved text: no reused sentences or reproduced hooks from the user's own history (n-gram overlap check).
7. No invented business or customer claims.

### Level 2 — Strategy constraints (Opus reasons over these)
8. Choose an angle supported by the available evidence.
9. Choose a hook appropriate to that angle.
10. Prefer a personal experience when it really strengthens the idea.
11. Avoid hook/angle patterns used heavily in recent posts.
12. Match the identity's established voice.
13. Respect the authority map.

### Level 3 — Writing principles (guide the prose)
14. **One idea.** One post = one primary idea. Before writing, state the one thing the reader should remember in a sentence.
15. **Strong hook.** The first 1–2 lines must earn attention: curiosity, contradiction, specificity, relatability, tension, surprise or a clear benefit. It has to land before LinkedIn's "…see more" cut-off. No generic introductions ("AI is changing the way companies operate").
16. **Open loop.** When it fits, create an unanswered question early and resolve it later. A curiosity gap is good; an unfulfilled one is clickbait.
17. **Every paragraph earns the next.** This is the core of Contendo's writing, as important as the hook. Treat the post as a retention chain: hook → read line 2 → read line 3 → click "…see more" → keep reading → reach the payoff → take the action. If any link is boring, the chain breaks. Line 2 has to pay off or deepen the hook immediately; the lines just before the "…see more" cut-off must give a reason to click; after the cut, every paragraph must create a reason to read the next one (a question raised, tension, a promised answer, a concrete detail). For each paragraph, ask why the reader would continue. If there's no strong answer, rewrite it.
18. **Tension.** For stories, don't reveal the lesson immediately; let the reader experience the problem before the solution.
19. **Payoff.** The body must fulfil the hook's promise.
20. **Pattern interruption** only when the body genuinely supports the claim. Never manufacture controversy for engagement.
21. **Specific beats generic,** using only specifics the user provided ("8 months and $12,000 building a product 17 people used" beats "I worked hard for a long time").
22. **Simple language.** Common, concrete words, short sentences, active voice, conversational phrasing. use > utilize, help > facilitate, show > demonstrate, start > commence. No jargon or corporate speak. The goal is that the idea is easy to understand, not that the writer sounds clever.
23. **Say more with less.** Compression pass: for each sentence, keep it only if it adds new information, advances the story or argument, increases curiosity, gives evidence or value, or serves the CTA.
24. **Visual writing.** 1–3 sentences per paragraph, intentional whitespace, no walls of text, but don't mechanically put every sentence on its own line (that's the stereotypical AI LinkedIn look).
25. **Authenticity.** Preserve the author's opinions, experiences and vocabulary. Don't convert every post into generic "LinkedIn influencer" language.
26. **Separate message from presentation.** The same core idea can be told as a story, contrarian take, list, case study, mistake, framework and so on.
27. **Voice transfer, not self-plagiarism.** Use retrieved posts to learn rhythm, tone, formatting and opinions, and to preserve facts, never to reuse wording.

### Final quality questions (in the generation prompt as a self-check)
Would the target reader stop scrolling? Is the central idea immediately clear? Does the opening create curiosity? Does every paragraph earn the next? Is anything redundant? Is the language too complicated? Does the payoff satisfy the hook? Does it sound like the author rather than an AI? Is the CTA natural?

Put these rules in `CONTENT_WRITING_RULES.md` (referenced by PROMPTS.md), and keep the prompt text compact.

---

## 10. The generation call

### 10.1 Context budget (target ~2,300 input tokens, not 15–30k)
| Part | Tokens |
|---|---|
| System writing rules (Level 2 + 3, compact) | ~800 |
| Writer/brand profile (compiled fingerprint) | ~300 |
| Relevant experiences | ~400 |
| Relevant knowledge + 2 style examples | ~600 |
| Recent strategy summary + eligible angles + DO NOT CLAIM list | ~100–200 |
| User request | ~100 |

### 10.2 Prompt contents
IDENTITY · TOPIC · OBJECTIVE · AUTHOR PROFILE · RELEVANT KNOWLEDGE · RELEVANT EXPERIENCES · BELIEFS · STYLE REFERENCES · RECENT CONTENT (angles and hooks used) · ELIGIBLE ANGLES (from the code gate) · DO NOT CLAIM · TASK: determine the central idea; choose the strongest evidence-supported angle, structure and hook; draft several hooks internally and pick the strongest; write; run the compression pass; don't expose the planning.

Keep the existing citation markers and the cited-drafting grounding approach.

### 10.3 Output contract
```json
{
  "strategy": {
    "central_idea": "...",
    "angle": "mistake_lesson",
    "structure": "context_problem_attempts_tension_discovery_lesson",
    "hook_strategy": "confession",
    "cta_strategy": "reflection | none | ...",
    "evidence_ids": ["source_1", "exp_3"],
    "reason": "one sentence"
  },
  "post": "... (with citation markers, stripped before display)",
  "alternative_hooks": ["...", "...", "..."]
}
```
Decide in Phase 2 whether the strategy block comes first (small, then the post streams) or is returned via a separate field, so streaming isn't delayed. Store the strategy with the post (it feeds recent history and the learning loop). Show the alternative hooks in the editor as one-click swaps.

### 10.4 Two paths
- **Fast path (default):** retrieval → one generation call → deterministic checks → post. Must meet the latency target.
- **High-quality path (on request, e.g. "refine more"):** strategy → strong drafting → review → optional revision (variant B machinery).

---

## 11. Latency budget

| Component | Target |
|---|---|
| API / auth | 50–100 ms |
| Profile cache | 10–30 ms |
| Vector + lexical retrieval (parallel) | 50–200 ms |
| Other DB queries | 30–100 ms |
| Prompt construction | < 20 ms |
| Generation (streamed) | 1.5–3.5 s, first token < 1–1.5 s |
| Deterministic checks | 100–500 ms |
| **Total** | **~2–5 s** |

Measure p50 and p95, not averages. A model that sometimes finishes in 4 s and often takes 18 s is a bad default. Watch Opus thinking tokens: they count against time-to-first-token.

---

## 12. Evaluation

Extend the existing evals (`evals/`) rather than building new ones.
- Eval cases cover several identity types (person with rich history, person with thin history, business):
```json
{"topic": "AI evaluations", "identity": "profile_123",
 "expected": {"preserve_voice": true, "avoid_fabrication": true, "use_relevant_experience": true, "avoid_repeated_hook": true}}
```
- Dimensions: **authenticity** (sounds like the author), **grounding** (claims supported), **hook quality** (relevant interest), **substance/payoff** (real value, hook fulfilled), **readability/compression** (concise, easy).
- **Sequence diversity:** generate 5–10 posts in a row for the same identity and check angle/hook variety. Ten individually good posts that sound identical is a failure.
- Selection rule for any pipeline change: the fastest configuration whose blind ranking and grounding are not worse than current C-Opus.

---

## 13. Learning loop (later)

Store per published post: topic, angle, hook type, structure, length, CTA type, posting time → impressions, likes, comments, reposts, saves, profile visits, followers gained (via Zernio / official data only; never scrape LinkedIn). Compute performance relative to that user's own median. Over time this fills `historical_performance` (e.g. "for this user, personal stories run 1.7× their median, lists 0.7×").

Before engagement data exists, use edit signals: how often the user rewrites the hook, deletes the CTA, changes the structure, swaps to an alternative hook, or rejects a draft. Treat these as noisy preferences, not definitive quality measures.

---

## 14. Module layout (modular monolith; adapt to existing folders rather than moving working code)

```
ingestion/      linkedin import (Apify/Zernio), articles, documents
intelligence/   voice/fingerprint, belief extractor, experience extractor, authority map, business profile, profile builder
retrieval/      knowledge, experience, style retrieval, ranker
strategy/       angles, hooks, structures, CTA config, eligibility gate, repetition
generation/     prompt builder, generator, streaming
evaluation/     hook, authenticity, repetition, grounding checks
analytics/      post performance, edit signals, personalization
```

---

## 15. Phases (one branch and PR each; stop after each for my review)

**Phase 0 — Baseline and report (no feature code).**
- From existing traces (`memory/trace_store.py`, `pipeline/trace.py`, `latency_ms` in `llm/client.py`), report real C-Opus numbers: per-call latency for structure, draft and compress; tokens including thinking; how often compress runs; total time p50/p95; sample size.
- Propose instrumentation (implement it after I approve the report): `profile_load_ms`, `retrieval_ms` (including enrichment), `structure_ms`, `draft_ms` + time to first token, `compress_ms`, `checks_ms`, `total_ms`, model ids, effort/thinking settings, token counts. Reuse the trace row and the `_timed` pattern from `pipeline/single_writer.py`.
- Identify what is NOT measured today (e.g. per-step wall time for variant C, profile load, retrieval and each DB call in it).
- Gap map: for every section of this spec, what exists (file and function), what's missing, and whether it touches the request path or only ingestion. Flag contradictions with the code.
- Streaming feasibility: explain how the cited draft is produced and post-processed (citation markers, strip, finalise, checks), whether it can be streamed given that post-processing, and a safe design (e.g. stream the text with markers hidden, then send the final checked version) including what the user sees if the final version differs from the streamed one.
- Design the Phase 1 experiment in detail and estimate its API cost; don't run it yet.
- A branch-by-branch plan for all phases, smallest first, each branch one PR, listing the tests each needs. Adjust the phase order if the measurements argue for it, and say why.
- Output: one report with the numbers, gap map, streaming design, experiment design with cost, and branch plan. Then stop and wait for my approval before writing feature code (the instrumentation change is the only code in Phase 0, and only after I approve the report).

**Phase 1 — Latency experiment.** On the same goldens and the same retrieved context, compare: (a) current C-Opus; (b) structure decision folded into the Opus call with the eligibility gate kept in code; (c) (b) with thinking reduced/off or lower effort; (d) Sonnet 5.5 as the drafter in the one-call setup. Measure p50/p95, time to first token, cost per post, grounding failures, blind ranking. Estimate API cost before running. Make the winner the default.

**Phase 2 — Streaming.** Stream the draft to the frontend with citation markers hidden, then send the final checked version. Define what the user sees if checks change the text. Update `routers/generate.py` and the frontend.

**Phase 3 — Retrieval by purpose + parallel queries.** Run the chunk-count experiment (section 7.1) first; then knowledge / experience / beliefs / style split with the measured counts, metadata ranking, concurrent queries.

**Phase 4 — Writing fingerprint + style examples.** Background job extending `profile_store`; compiled 300–600-token profile; 2–3 diverse style examples.

**Phase 5 — Strategy object + writing rules.** Taxonomies and structures as config; eligibility gate in code; angle/structure/hook/CTA in the output contract; recent strategy history and repetition penalty; `CONTENT_WRITING_RULES.md`; alternative hooks in the editor.

**Phase 5b — Cold start.** Data tiers; follow-up questions replacing the `low_coverage` dead end; answers stored as `user_stated` citeable memories; provisional starter voice from onboarding; decision on retiring or rebuilding no-specifics mode; cold-start eval cases.

**Phase 6 — Identities, LinkedIn import, experience events, authority map.** Person/business identities chosen once at onboarding; LinkedIn import via Apify or Zernio seeding the personal identity; structured experience events and beliefs (extending `experience_store`); authority map constraining strategy; business brand model.

**Phase 7 — Evals and learning loop.** Multi-identity eval set, sequence-diversity test, edit-signal tracking, then post-performance tracking relative to each user's median.

---

## 16. Rules for every phase

- No stopgap shortcuts (hardcoded keyword or verb lists, timeouts that silently return a worse post, skipping grounding checks to save time). If something is unavoidably a stopgap, label it and propose the proper fix.
- Don't weaken grounding (cited drafting, checks, first-person evidence rules) to gain speed.
- No new synchronous model calls on the request path without eval evidence that they're worth their latency.
- Keep `PIPELINE_VARIANT=A` working as the rollback switch.
- Tests in `backend/tests/` with the in-memory fakes; known bugs as `xfail(strict=True)`.
- After each phase: update CODEBASE.md, and PROMPTS.md if a prompt changed. Summarize what changed, which files, any TODOs for me, and any new environment variables or API keys.
- Start with Phase 0. Report, then stop and wait for my approval.

---

## 17. Decisions log (added after Phase 0)

**2026-10-15: remove the model grounding check from the request path.** Overrides "keep every existing grounding protection" (§1, §16) for the `enforce_grounding` step only (`pipeline/grounding.py`: one Sonnet 4.6 check, up to two Opus repairs, each re-checked). Evidence: the 7 production C-Opus posts of 2026-10-14/15.
- 6 of 7 posts were flagged; 11 of 28 flags said in their own reason that the text was supported; the rest were wording nitpicks or false positives (diagram layout, opinions).
- At most 2 flags were plausibly real, and neither was an invented number, name or event.
- Cost: median 27.6 s per post, and 3 good posts ended `needs_review` on false positives.
- Kept: every deterministic check in `pipeline/checks.py` (citations, specifics not in the cited source, event verification, length) and the cited-drafting rules.
- The remaining risk (a general lesson rewritten as a first-person claim) is fixed at the source: the drafter's authorship rules now, and verified experience events (§6.2, Phase 6) later.
- The check may come back only as an on-request "refine more" path (§10.4), never on the default path.
- Implemented 2026-10-15 on `feat/fast-path`, for generation and for publishing approval. Approval keeps the exact-text lock, any flags an older post stored, and the user's explicit approval; no model checks the text.

**2026-10-15: the backend sets a LinkedIn post's length.** The create screen no longer offers a length.
- A post stays under 200 words (`LINKEDIN_MAX_WORDS`, the user's rule). That is the hard limit; compress runs only past it.
- The drafter is asked for 100–150 words, because drafts overshot the asked maximum by up to ~7% and compress ran on 5 of 7 posts (5–22 s each).
- Pipeline A, the rollback, keeps the requested length.

**2026-10-15: LinkedIn only, across the platform.** No screen offers or shows Medium or threads (create, ideas, history, onboarding, settings, preview, mark-as-published). `/generate` and onboarding always write a LinkedIn post, and ideas are LinkedIn post ideas. Medium and threads return once LinkedIn posts are right; the backend keeps their dormant code for that and for the evals.

**2026-10-15: line-by-line post construction (for Phase 5, §8–9).** Each post is built from explicit line roles chosen per post, not from one fixed template:
- the central idea, stated first;
- a hook chosen for the angle;
- line 2 pays off or deepens the hook;
- the lines before LinkedIn's "…see more" earn the click;
- every later paragraph earns the next;
- a contrarian turn only when the evidence holds a real opposing belief.

Code supplies the eligible angles, hooks and structures. Opus chooses and writes in the same single call, and the choice is stored with the post for repetition control and evals. Evidence for the need: 6 of 7 production posts used the same structure (`teach_me_something`).

**2026-10-15: D-Opus-low is the default (Phase 1, evals ablation "phase1").** One Opus 5.5 call writes the post and chooses its structure among the types the code allows (`allowed_archetypes`, unchanged); no separate Haiku structure call; draft effort `low`. Opus 5.5 rejects thinking disabled at every effort, so effort was the only lever. Branch `feat/one-call-default`; `config.features.DEFAULT_PIPELINE_VARIANT`.
- Setup: C-Opus (today) vs D-Opus (structure folded into the Opus call, effort medium) vs D-Opus-low, on the full ablation's 10 blind-read goldens, one run each, interleaved golden by golden in a seeded random arm order. Every golden's three runs drafted from identical inputs (fingerprints of the retrieved chunks, sources block, profile and plan matched on 10 of 10). $1.90 spent of a $3.50 cap.
- Caveat on inputs: the eval project's source and topic nodes are empty, so every arm drafted from plain chunks without source summaries (as every earlier eval did); production prompts carry more context.
- Rule 1 (eligible: unsupported_specifics pass count at most 1 below C-Opus's, deterministic check issues not above C-Opus's): both D arms eligible. Passes 10 / 10 / 10 of 10 (C-Opus, D-Opus, D-Opus-low); check issues 9 / 5 / 8.
- Rule 2 (speed: p50 at least 15% lower and p95 not higher than C-Opus's 14.9 / 46.9 s): D-Opus-low qualifies at 7.0 / 18.2 s; D-Opus does not (p50 14.3 s, 4% lower). Time to first text p50 / p95: 8.6 / 28.3, 8.4 / 10.7, 1.2 / 3.2 s. Thinking tokens p50: 772, 704, 0. Cost per post $0.051, $0.049, $0.034.
- Rule 3 (blind read; C-Opus kept if ranked above the candidate in 7 or more of 10): C-Opus was above D-Opus-low in 3 of 10, so D-Opus-low becomes the default. Mean rank D-Opus-low 1.70, D-Opus 2.10, C-Opus 2.20; D-Opus-low ranked first in 6 of 10, above D-Opus in 6 of 10.
- Structure choice: the drafter chose `general` in 3 of 10 posts (D-Opus 4), where C's Haiku call chose none; no D post named a type outside the allowed set.
- Rollbacks: `PIPELINE_VARIANT=C-Opus` (the previous default) and `PIPELINE_VARIANT=A`; tests run each.
- Still above the latency target: p95 18.2 s against p95 ≤ 10 s. Time to first text (1.2 s p50) makes streaming (Phase 2) the next step for perceived latency; founder-04 (slowest golden for every arm: 46.9 / 32.3 / 18.2 s) is investigated after it.

**Production check, fixed 2026-10-15 before any production data exists.**
- After deploy, compare the first 7 days or the first 50 real D-Opus-low generations, whichever comes first, against the last 50 C-Opus production generations (both from `generation_traces`): p50 and p95 wall time (`run_seconds`), time to first text (`llm_calls[].first_text_ms` of the generate call; C-Opus traces made before this branch have none, so that comparison starts from D-Opus-low's own figures), deterministic check issues per post (`checks_final.counts`), and the share of truncated or refused outcomes (`draft_truncated`, `draft_refused`).
- Roll back to C-Opus (`PIPELINE_VARIANT=C-Opus`) if deterministic check issues per post rise by more than 50% over C-Opus's production rate, or truncated or refused outcomes occur in more than 2% of generations.
- The comparison is reported to Soham either way.

**Known quality item for Phase 5 (not patched now).** In the phase1 blind read D-Opus-low ended founder-09 with a stock engagement question ("So which one are you, honestly?"). The CTA rule (choose the CTA by the post's objective; never append engagement bait, §8.6) addresses it. The prompt is not patched for this one case.

**2026-10-14: Phase 2 streaming (`feat/generate-stream`).** `POST /generate/stream` (SSE over fetch) runs `/generate`'s exact steps and sends the first draft as it is written, then the same response `/generate` returns. The Create page uses it; `/generate` is unchanged.
- Streamed: the single-writer first draft only (`draft_agent.listen_to_draft` → `complete(on_text=...)`), filtered by `utils/draft_preview.py` (only `<post>`, markers hidden, unsettled text held back). Fixes, redrafts, compress and pipeline A stream nothing.
- What the author sees: the preview, read-only, labelled as a preview to be checked. On `final` the checked post replaces it with no diff highlight: with the model grounding check gone (above), the only changes after the draft are finalise's normalisation (spacing, punctuation, marker removal) and compress past 200 words. A highlight of changed sentences (Phase 0 report §5.4) is left until a step that rewrites sentences comes back (the "refine more" path). On a non-ok status the preview is dropped and the message shown; on `error` the existing error text.
- The strategy-block order question (§10.3) is for Phase 5, when the output contract gains a strategy part: it must come before `<post>` so the preview starts as soon as the post does, which is how `<structure>` already works.
- Not measured yet: time to first visible text in production through Railway's proxy. The trace's `first_text_ms` is the model's; the user's adds retrieval (3–6 s) and any proxy buffering.
