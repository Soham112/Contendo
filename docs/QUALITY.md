# Contendo quality bar

The yardstick every later step (data layer, retrieval, strategy, latency) is scored against. Written 2026-10-15 from `docs/GENERATION_ARCHITECTURE.md` §5–10 and the step 1 brief. Test set: `evals/goldens/quality_v1/` (cases, sequences, personas) and `evals/fixtures/quality_v1/personas/`.

## How scoring works

- **Three scorers.** *Code*: deterministic, closed vocabulary (numbers, dates, ids, offsets, lengths, n-grams, embeddings). *Judge*: a model answering one pass/fail question per criterion with **a quoted line from the post as evidence** (no 1–10 scales). *Blind read*: Soham ranks or answers the nine questions without knowing which variant wrote the post (`blind.py make/score`).
- **A judge criterion is not trusted until audited.** Before its first use, and after any change to its prompt, run `blind.py audit` on at least 10 of its verdicts. A criterion whose verdicts Soham marks wrong more than 2 times in 10 is reported but not used in any decision.
- **Pass/fail per post.** Any B2 failure fails the post. B3–B4 and B6b are reported as pass rates per criterion; they don't fail a post on their own. B1 is per case; B5 per sequence; B8 is recorded, never pass/fail.
- **Labels are ground truth, with a stated confidence.** Criteria marked *(labels)* compare against the case's labels (`must_use_all`, `must_use_any`, `eligible_angles`, `do_not_claim`, `needs_present`/`needs_missing`, `central_idea`). Labels are reviewed by Soham before any scoring.
- **`must_use_all` vs `must_use_any`.** `must_use_all`: every source is needed for the expected post. `must_use_any`: the post needs one of these, and retrieval gets full credit for finding any one (e.g. "What I learned this year" should pick one lesson, not retrieve every candidate).
- **`label_confidence`.** `verified`: labels written with the full source text (all synthetic fixtures). `metadata_only`: labels proposed from titles, types and ids without reading the content (persona `me`). A `metadata_only` case counts toward retrieval scores (B1) only for source identity, and its angle labels are never a hard fail: a post outside `eligible_angles` is flagged for review, not failed. A failing `metadata_only` case is checked against its label before it is counted against the system.
- **Dev and hold-out.** Develop against `split: dev`. Score `split: holdout` only at the end of a step. A change that improves dev but not hold-out is overfitted and doesn't ship.
- **Production check.** After each step, the aggregate production report (Part D3: library size, own-notes share, low coverage rate, keyword fallback, check issues, edits before save) runs across all real users, so changes are judged on everyone, not only the test set.
- **Latency guardrail.** No change may make time to first word slower than today's production without an explicit decision from Soham.

## B1. Retrieval scorecard (per case, code, labels)

Kept deliberately small. Required evidence is counted in units: each `must_use_all` source is one unit, a `must_use_any` group is one unit. The **cutoff** is the set of sources that reaches the drafter (empty when the coverage gate stops the run). Scorer: `evals/quality_metrics.py`; harness: `evals/quality_retrieval.py`.

| # | Metric | Pass looks like | Data it needs |
|---|---|---|---|
| B1.1 | Required-source Recall@cutoff (also @1, @3, @5 for diagnosis) | every required unit reaches the drafter | case labels; drafter source ids per run |
| B1.2 | MRR of the first required source (first-source rank kept in the per-case debug table) | rank 1 for `names_project` topics, top 3 otherwise | ranked retrieval list |
| B1.3 | Precision@cutoff: share of drafter sources that are required or background | ≥ 0.75 (to tune on the baseline) | `off_topic`, `background` labels |
| B1.4 | Off-topic rate | no off-topic source reaches the drafter | `off_topic` labels |
| B1.5 | Own-source share, for topics that name a project, company or role | at least one own source and own sources ≥ 50% of drafter sources | per-source authorship (fixture `memory_context`; `metadata_only` cases skip it) |
| B1.6 | Evidence Recall@cutoff (**not built yet**) | the context passed to the drafter contains the labelled fact or idea, not only the right source | fact/evidence labels per case (step 3). Candidate scorer: DeepEval `ContextualRecall` (LLM-judged attribution of expected statements to the context), audited before use |
| B1.7 | Coverage-gate accuracy | the gate stops exactly the cases labelled coverage none and never stops coverage full | `coverage` label, gate decision |
| B1.8 | Hybrid-search reliability | the hybrid path ran (no silent fallback) and BM25 indexed the whole library; retries recorded | **not in production traces**; the harness observes it from the eval side. Production needs a trace field (`bm25_ran`, corpus size, library size, retrieval path) |

Not used, by decision: MAP (little beyond MRR here), generic cosine averages (can look good while retrieval is semantically wrong), nDCG@K until relevance is graded (must-use > background > irrelevant). DeepEval 4.2.7 has no label-based rank metrics; its `ContextualPrecision` is an LLM-judged average precision and its `ContextualRecall` is LLM-judged evidence attribution.

## B2. Hard rules (code; any failure fails the post)

| # | Criterion | Scored by | Pass looks like | Data it needs |
|---|---|---|---|---|
| 7 | No fabricated personal experience | code (citations + source verification) + judge for uncited first-person prose | every first-person claim cites a source whose verification is `user_authored` or `user_stated` | per-source **verification status** (doesn't exist); experience events linked to sources (doesn't exist; `experience_nodes` are roles) |
| 8 | No fabricated numbers, dates, names, customers or results | code for closed vocabulary (numbers, money, dates, durations: existing `specific_not_in_cited_source`); judge for names, customers and results (open-ended) with the quoted span and the cited source | every specific appears in a cited source or the request; nothing in `do_not_claim` | citation spans (exist); source text by id (exists) |
| 9 | No article attributed to the user unless authored | judge (quote + cited source's authorship) | an external source is never presented as the user's writing or work | per-source authorship (`user_authored` vs external); today inferred from `memory_context`/`source_type`, wrong for real data (see known issues) |
| 10 | Length | code | 100–150 words requested; fail above 200 (`LINKEDIN_RANGE`, `LINKEDIN_MAX_WORDS`) | final post |
| 11 | Not a repeat of a recent post | code: embedding cosine vs the persona's last N posts; threshold set on the baseline (record distribution first) | max similarity below threshold | recent posts with embeddings (posts exist; post embeddings don't) |
| 12 | No copying of retrieved text or own history | code: longest shared word n-gram vs retrieved chunks and past posts; fail at ≥ 8 consecutive words (to confirm on the baseline), and an identical first line to any past post | no reused sentence or hook | past posts (exist), retrieved chunk text (exists) |
| 13 | No invented business or customer claims (business identity) | judge (quote + profile note + sources) | every claim about the business, its customers, results, reviews or offers is in the profile note, a source or the request | business profile note (exists, `source_type business_profile`) |

## B3. Strategy (judge, against labels)

| # | Criterion | Pass looks like | Data it needs |
|---|---|---|---|
| 14 | Angle is evidence-supported | judge names the post's angle (quote); it's in `eligible_angles`; no first-person angle without first-person evidence | angle taxonomy (spec §8.1); per-case evidence labels; later: experience events with verification |
| 15 | Authority respected | high: experience, opinion, framework, lesson, strong claims allowed; low: observation, analysis, question, synthesis only; no "what X get wrong" without a profile basis | **authority map** per identity and topic (doesn't exist); labels hold it for now |
| 16 | Hook matches the angle and the post | judge names the hook type (quote) and confirms the body delivers it | hook taxonomy (spec §8.2) |
| 17 | Structure fits the material | judge records the structure used (spec §8.3) and flags "general" where a specific structure fit | structure library; today's 8 archetypes (`utils/formatters.py ARCHETYPES`) differ from the spec's 6 |
| 18 | Personal experience used when it strengthens the idea | if a required own source (`must_use_all` or `must_use_any`) exists, the post's central evidence is that source, not a secondary article | labels; authorship per source |
| 19 | CTA chosen by objective | CTA type ∈ {discussion, reflection, share, follow, resource, product, none}; no stock bait ("What do you think? Comment below!"); matches the persona's CTA style | case `objective`; **CTA style** in the writing fingerprint (doesn't exist; `profiles.writing_rules` is free text) |

## B4. Writing principles (judge unless marked code)

| # | Criterion | Pass looks like | Data it needs |
|---|---|---|---|
| 20 | One idea | judge states the central idea in one sentence; it matches the case's `central_idea` | label |
| 21 | Focus | the central idea comes from required material (`must_use_all` or `must_use_any`), not a secondary source | labels + citations |
| 22 | Strong hook | lines 1–2 use curiosity, contradiction, specificity, relatability, tension, surprise or a clear benefit; no generic opener. *Code:* the hook ends before the "…see more" cut-off | **cut-off constant doesn't exist in config**; to add after measuring LinkedIn's current desktop and mobile truncation |
| 23 | Retention chain | line 2 pays off or deepens the hook; the lines before the cut give a reason to click; each later paragraph gives a reason to read the next. Judge returns the first paragraph where the chain breaks, or none | post only |
| 24 | Open loop resolved | every curiosity gap the opening creates is answered (quote the gap and the answer) | post only |
| 25 | Tension in stories | for story angles, the lesson isn't stated before the problem | post + angle (from 14) |
| 26 | Payoff | the body fulfils the hook's promise | post only |
| 27 | Pattern interruption earned | a contrarian or surprising claim is supported in the body; no manufactured controversy | post + sources |
| 28 | Specific over generic | concrete details used where sources have them, and only from sources (with rule 8) | sources |
| 29 | Simple language | common, concrete words; short sentences; active voice; no jargon. Judge quotes offending phrases | post only |
| 30 | Compression | judge lists every sentence that adds no information, argument, curiosity, evidence or CTA value; pass at 0 | post only |
| 31 | Visual writing *(code)* | every paragraph 1–3 sentences; no paragraph over ~60 words; ≤ 70% of paragraphs single-sentence | post only (sentence splitter exists for citation spans) |
| 32 | Sounds like the person | judge compares to profile and 2–3 writing samples: voice, vocabulary, opinions match; not generic influencer or AI style | **writing fingerprint** (doesn't exist); today `profiles.data` voice fields and `writing_samples` (3 of 8 users) |
| 33 | Voice transfer, not self-plagiarism | rhythm and tone resemble past posts; wording doesn't (with rule 12) | past posts |

## B5. Sequence quality (per persona, 6–8 posts in a row, `sequences.json`)

| # | Criterion | Scored by | Pass looks like | Data it needs |
|---|---|---|---|---|
| 34 | Angle and hook variety | judge labels each post's angle and hook (from 14 and 16); code counts | no angle or hook type in more than ~40% of the sequence; no two openings with the same pattern (judge) or same first 5 words (code) | **strategy history** per post: angle, hook, structure, CTA, opening line (doesn't exist; `posts.archetype` has structure for 7 of 138 posts) |
| 35 | Topic angles don't repeat recent posts | code (rule 11 similarity) + judge for "same angle on same topic" | no repeat of a seed or earlier post's angle on the same topic | recent posts and their strategy |

## B6. Cold start (per tier)

| # | Criterion | Scored by | Pass looks like | Data it needs |
|---|---|---|---|---|
| 36 | Tier 0–1: honest posts | code (citations) + judge | no first-person claim without a stored source; observation or analysis angle | data tier per request (not computed today); onboarding answers |
| 37 | Tier 2: low coverage | code | **today:** record what happens (`low_coverage` empty post; rate and closest sources). **Target, scored once built:** 2–3 topic-specific follow-up questions; answers stored as `user_stated` memories and cited | `user_stated` memory type (doesn't exist) |

## B6b. Business posts (segment = business)

| Criterion | Scored by | Pass looks like | Data it needs |
|---|---|---|---|
| Pillar fulfilled | judge | the post does what the pillar is for (`config/niches.py` `about`) | `accounts.business_niche`, request `pillar` (exist) |
| Needs only from the author *(hard rule)* | code for closed-vocabulary needs (price, dates, times, figures); judge for the rest (area, features, offers, people) | every `needs` fact in the post is in the profile note, a source or the request; every `needs_missing` fact is absent or asked for | pillar `needs` (exist); labels `needs_present`/`needs_missing` |
| Business voice | judge | written as the business ("we"), in the chosen tone; no invented first-person stories, customers, results, reviews or offers | `business_profile.tone`, `tone_notes` (exist) |
| Business CTA | judge | fits the pillar and the customer (book a viewing, call, visit, reserve); not a generic engagement question | pillar |
| Local and specific | judge | uses service area and differentiators when relevant, not generic industry copy | profile note (exists) |
| Pillar variety in sequences | code (pillar counts) + judge (openings, offers) | rotates pillars; no repeated opening or offer | strategy history incl. pillar (doesn't exist) |

## B7. Blind read (every post)

Soham answers yes/no for each, blind to variant: Would the target reader stop scrolling? Is the central idea immediately clear? Does the opening create curiosity? Does every paragraph earn the next? Is anything redundant? Is the language too complicated? Does the payoff satisfy the hook? Does it sound like the author rather than an AI? Is the CTA natural? The judge's B3–B4 verdicts are audited against these answers.

## B8. Operational (code, recorded, not pass/fail)

Time to first word, total time, thinking tokens, input tokens by prompt part (sources, past topics, rules, profile, structures), cost per post. Already in traces: `node_outputs.step_timings`, `retrieval_timings`, `run_seconds`; `llm_calls` (effort, thinking, cache tokens, `first_text_ms`). Missing: input tokens **by prompt part** (today measured by a one-off script).

## Data each criterion needs, and whether it exists

Production counts are from read-only queries on 2026-10-15 (8 users with profiles, 7 with sources, 250 chunks in total).

| Data | Needed by | Exists today (file / table) | Populated in production |
|---|---|---|---|
| Drafter source ids and ranks per run | B1.1–B1.5, 18, 21 | `generation_traces.retrieved`, `node_outputs.source_index` | 32 traces, 4 users |
| Whether keyword search ran and over how many chunks | B1.8 | no (log warning only) | – |
| Per-chunk authorship (own vs external) | 3, 7, 9, 18 | inferred: `embeddings.memory_context` + `source_type` → `utils/frames.py` | memory_context set on 22 of 250 chunks (9%); the rest fall back to `source_type`. At least 2 real mislabels in Soham's library |
| Verification status (`user_authored` / `user_stated` / `inferred`) | 7, 14, 36, 37 | no | – |
| Experience events (what happened, linked to a source) | 7, 14, 18 | no; `experience_nodes` holds roles, not events | `experience_nodes`: 11 rows, 1 user |
| Beliefs / opinions with source | 14, 15, 27 | partly: `profiles.data.opinions` (free text, no source) | 8 of 8 profiles have opinions |
| Authority map | 15 | no | – |
| Writing fingerprint (incl. CTA style, hook preferences) | 19, 32, 33 | partly: `profiles.data` voice fields, `writing_samples` | writing_samples in 3 of 8 profiles |
| Past posts | 11, 12, 33, 35 | `posts.content` | 138 posts, 8 users |
| Post embeddings for repeat check | 11, 35 | no | – |
| Strategy history (angle, hook, structure, CTA, opening, pillar) | 34, 35, pillar variety | partly: `posts.archetype` (structure only) | 7 of 138 posts |
| Edits before save | D3 report | partly: `post_versions` (`generated`, `refined`) | 162 versions; 21 posts have more than one. A manual edit in the editor before save isn't stored as its own version, so "how much it changed" needs `posts.content` vs the first `generated` version |
| Data tier per request | 36, 37 | no (coverage gate decision only: `node_outputs.coverage_gate`) | – |
| `user_stated` memories from follow-up answers | 37 | no | – |
| Business account (niche, profile, tone) | 13, B6b | `accounts` | 2 rows; 1 business (salon_spa) |
| Business profile note | 13, B6b | `embeddings` with `source_type business_profile` | 1 user |
| Pillar per post | B6b | request only (`routers/generate.py`); `node_outputs.business` in the trace | not stored on `posts` |
| Source and topic hierarchy (summaries) | not needed by any criterion; affects retrieval context | `source_nodes`, `topic_nodes` | **0 rows** in production |
| "…see more" cut-off | 22 | no config constant | – |
| Case labels | B1, B3, B6, B6b | `evals/goldens/quality_v1/cases.jsonl`; persona `me` in gitignored `evals/private/quality_v1/` | 61 cases, 9 persona states; 52 `verified`, 9 `metadata_only` |

## Where the spec and this bar disagree (to resolve)

1. **Angle names.** The eligibility table (spec §8.4) and authority rules (§6.4, criterion 15) use names that aren't in the 16-angle taxonomy: story, mistake, lesson, opinion, question, synthesis. Labels use the taxonomy names only (story → personal_story, mistake → mistake_lesson, opinion → contrarian_opinion). Question and synthesis have no taxonomy angle; `question` exists only as a hook. Decide: add `question` and `synthesis` angles, or map them to `observation`/`analysis`.
2. **Business posts have no angle.** A new_listing or just_sold post is an announcement; no taxonomy angle fits. Labels use a proposed `announcement` angle. Decide whether business pillars get their own angle set.
3. **Structures.** Today's 8 archetypes (`incident_report`, `list_that_isnt`, …) differ from the spec's 6 structures. Criterion 17 records both until step 5 settles one library.
4. **Identity model.** Spec §5: one account can have a personal identity and several business identities. Code: one `segment` per account. The test set follows the code; dual identity isn't testable yet.
5. **Tier 1 for individuals.** Spec: "onboarding answers, no sources". Code: individual onboarding stores the first-post story as a `personal_note`, so a real Tier‑1 user has one own source. Persona `ni1` follows the code.
6. **Business onboarding always creates a source.** Business name, area and services are required, so every business user has the profile note; a business Tier 0 doesn't exist.

## Business block and gate labels (2026-10-16)

Business profile notes are fixed account context, outside retrieval. Every business case has `business_block: true`; `<persona>-bp` is never required for retrieval and is neutral for precision/off-topic. All 27 business cases require `expected_gate` in `{pass, profile_only, low_coverage}`. Required retrieval sources imply `pass`; otherwise the pillar's explicit `writable_from_profile` implies `profile_only` when true or absent and `low_coverage` when false. These are expected outcomes, independent of the retrieval result, so passing on irrelevant material remains a gate error. The 14 cases without required sources are evaluated as gates and excluded from recall/MRR means.

`quality_retrieval.py` reports business dev and hold-out gate accuracy separately, including partial-coverage cases. Re-score saved retrieval with `--name 2026-10-16-relabel-baseline --rescore evals/results/quality_v1/relabel-baseline/runs.jsonl`; compare only with that relabel baseline. `--count-tokens` measures prompts using the free token endpoint. Code checks require the fixed block in 27/27 business case prompts and 0/34 individual prompts. Backend tests cover individual prompt byte equality, flag rollback, all three DB retrieval filters, own-source story eligibility, gate/first-post behavior, B grounding, rename and trace-backed refine. See `evals/baselines/2026-10-16-business-block.md` for labels and measurement status.

`writable_from_profile=true` is limited to buyer_seller_tips, oral_health_tips, treatment_explained, common_questions, service_spotlight, care_tips, trends, maintenance_tips, seasonal_reminder, service_explained and training_tips. Every other pillar is false: naming an area alone cannot supply neighborhood details, and a profile cannot supply behind-the-scenes process details. `nb-04` therefore expects low_coverage. `re-05` and `fs-06` retain low_coverage pending author review of the retrieved sources; passing a numeric relevance threshold does not prove the topic's required evidence exists.

Full prompt counts are rendered from live retrieval using the default D-Opus-low prompt. `--count-tokens` also re-runs the original flag-off retrieval path for business cases and records its full prompt, gate and rankings; verify these against saved baseline rankings before attributing changes. Counts are free and include message framing. A low_coverage gate would send no draft request: reports distinguish rendered-prompt deltas from gate-aware draftable-token deltas.
