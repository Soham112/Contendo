# Business block: completed step 10 ($0)

2026-10-16 (America/Los_Angeles) · feat/business-block · aa7f56c plus working changes. No commit, push, deployment, paid generation or judging. Migration 021 was applied to eval and reviewed by Soham; its SQL is unchanged. Production still needs 021 before the backend deploys, after 020. Steps 2–10 complete; stopped before step 11.

## Configuration revision

`Pillar.writable_from_profile` replaces the pillar field formerly named needs_event, with inverted meaning: true means an honest post of this kind can be written from the business profile alone. Exactly the 11 pillars Soham specified are true; every other pillar is false. A request with a request with no pillar behaves as true. In particular neighborhood_spotlight and behind_the_scenes are false: the profile supplies neither neighborhood amenities nor process details. The separate Archetype.needs_event field is unchanged because it describes story structure, not pillar writability.

| Niche | writable_from_profile=true | writable_from_profile=false |
|---|---|---|
| real_estate | buyer_seller_tips | new_listing, just_sold, market_update, neighborhood_spotlight, client_story |
| dentist | oral_health_tips, treatment_explained, common_questions | meet_the_team, practice_news, patient_story |
| restaurant | — | menu_highlight, specials_and_events, behind_the_scenes, meet_the_team, local_community, guest_story |
| salon_spa | service_spotlight, care_tips, trends | offers_and_availability, meet_the_team, client_story |
| home_services | maintenance_tips, seasonal_reminder, service_explained | completed_job, meet_the_team, customer_story |
| fitness_studio | training_tips | class_spotlight, schedule_and_offers, meet_the_coach, studio_community, member_story |
| other | — | — |

## Measurement and baseline integrity

Commands:

```sh
backend/venv/bin/python evals/quality_retrieval.py --name 2026-10-16-relabel-baseline --rescore evals/results/quality_v1/relabel-baseline/runs.jsonl
backend/venv/bin/python -u evals/quality_retrieval.py --name business-block --count-tokens
```

61 cases (52 synthetic verified, 9 private metadata-only), guarded eval project croalztabgzowjkkhkcm. Every run remained on the hybrid retrieval path. Three new-path cases retried (ni1-02, fs-02, bo-03); the final measurements stand. Some background retrieval-stat writes disconnected; no retrieval source was lost to a fallback. Spend measured by UsageLog: $0.000. Token measurements use only messages.count_tokens; no generation/judge call was made.

Saved retrieval is unchanged in the re-scored baseline; only the expected_gate labels were applied. The current full flag-off business prompts were reconstructed from live retrieval for token comparison. **27/27 flag-off ranked label/cosine sequences exactly match the saved relabel baseline**, including repeated consolidation chunks. Thus prompt changes are measured against the same retrieved baseline material, not a new ranking baseline. Raw runs are under evals/results/quality_v1/business-block; private me rows remain under evals/private.

## Retrieval comparison (baseline → business-block)

Recall is Recall@cutoff; precision is Precision@cutoff. Means exclude cases where the criterion does not apply.

| Group | n | Recall | MRR | Precision | Off-topic rate |
|---|---|---|---|---|---|
| verified dev | 32 | 0.812 → 0.812 | 0.740 → 0.740 | 0.542 → 0.542 | 0.102 → 0.127 |
| verified holdout | 20 | 0.917 → 0.917 | 0.875 → 0.875 | 0.712 → 0.712 | 0.077 → 0.077 |
| business dev | 17 | 1.000 → 1.000 | 0.917 → 0.917 | 0.506 → 0.506 | 0.073 → 0.106 |
| business holdout | 10 | 1.000 → 1.000 | 0.900 → 0.900 | 0.750 → 0.750 | 0.036 → 0.036 |

Business gate accuracy includes all 27 business cases, including the 14 without required sources:

| Split | Baseline | Business block |
|---|---|---|
| dev | 9/17 | 16/17 |
| holdout | 5/10 | 8/10 |

Dev off-topic rate increases from 0.102 to 0.127 because its mean excludes cases with no drafter source: bo-02, nb-01, nb-05 and nb-06 previously had only the neutral profile note and contributed zero; now they have no retrieved material. The denominator falls from 20 to 16. Every case’s individual off-topic finding/rate is unchanged; clean-case counts stay 25/32 dev and 17/20 hold-out. Precision and recall already exclude those neutral/no-required cases, so their means do not shift. The nine private me cases retain Recall 0.938, MRR 0.792, Precision 0.613 and off-topic 0.071.

## All 27 labels and observed gates

With required source labels, expected_gate is pass. Without them, it is profile_only when writable_from_profile is true or there is no pillar, otherwise low_coverage. nb-04 now expects low_coverage. re-05 and fs-06 remain low_coverage for Soham’s review.

| Case | Split | Pillar | writable_from_profile | expected_gate | Observed |
|---|---|---|---|---|---|
| re-01 | dev | new_listing | false | pass | pass |
| re-02 | dev | new_listing | false | pass | pass |
| re-03 | dev | just_sold | false | pass | pass |
| re-04 | dev | market_update | false | pass | pass |
| re-05 | holdout | market_update | false | low_coverage | pass |
| re-06 | dev | neighborhood_spotlight | false | pass | pass |
| re-07 | dev | buyer_seller_tips | true | pass | pass |
| re-08 | dev | client_story | false | low_coverage | low_coverage |
| fs-01 | holdout | class_spotlight | false | pass | pass |
| fs-02 | holdout | training_tips | true | pass | pass |
| fs-03 | holdout | schedule_and_offers | false | pass | pass |
| fs-04 | holdout | meet_the_coach | false | pass | pass |
| fs-05 | holdout | studio_community | false | pass | pass |
| fs-06 | holdout | member_story | false | low_coverage | pass |
| fs-07 | holdout | — | true (no pillar) | profile_only | profile_only |
| bo-01 | dev | — | true (no pillar) | pass | pass |
| bo-02 | dev | — | true (no pillar) | profile_only | profile_only |
| bo-03 | holdout | — | true (no pillar) | profile_only | profile_only |
| bo-04 | dev | — | true (no pillar) | profile_only | profile_only |
| bo-05 | dev | — | true (no pillar) | profile_only | profile_only |
| bo-06 | dev | — | true (no pillar) | profile_only | pass |
| nb-01 | dev | menu_highlight | false | low_coverage | low_coverage |
| nb-02 | dev | menu_highlight | false | pass | pass |
| nb-03 | holdout | specials_and_events | false | low_coverage | low_coverage |
| nb-04 | dev | behind_the_scenes | false | low_coverage | low_coverage |
| nb-05 | dev | meet_the_team | false | low_coverage | low_coverage |
| nb-06 | dev | guest_story | false | low_coverage | low_coverage |

## Every business gate mismatch

**re-05**: Expected low_coverage; observed pass. The gate only asks whether any raw cosine or normalized BM25 clears 0.30. A listing clears it at 0.5990; national price news also just clears it at 0.3008. This does not establish the requested Ashby/mortgage-rate evidence. The real Kelso Vale Q3 data note exists but was not retrieved. This is a threshold/semantic-coverage mismatch; label unchanged for Soham to review.

**fs-06**: Expected low_coverage; observed pass. Timetable cosine 0.4519, coach profile 0.3682, protein article 0.3164 and competitor opening 0.3018 clear the floor. None is a member’s first-year strength-training story. The live library has no such story. Writability is checked only when numeric coverage fails, so it cannot reject these unrelated passing sources. Label unchanged.

**bo-06**: Expected profile_only; observed pass. Topic: Getting your bike ready for winter. Spring service prices (bo-s01) has cosine 0.3183, so raw coverage passes before the no-pillar fallback. The case has no required retrieval source and prohibits inventing a winter offer or price. The spring price list is real stored material but is not a winter offer; this is a coarse gate/label disagreement, not a missing-block failure.

No other business case differs from expected_gate. The gate remains the existing numeric coverage gate; this task does not add a semantic topic/evidence classifier or word lists to make these cases pass.

## re-05: retrieved chunks and library evidence

Topic: What higher mortgage rates mean for buyers in Ashby. All cosines below are real stored-vector cosine values. Ranks show the original baseline and the new run; the profile is excluded from the latter.

| Baseline rank | Chunk / source | Cosine | Business-block rank |
|---|---|---|---|
| 1 | re-bp — Business profile | 0.3998 | excluded |
| 2 | re-s08 — UK house prices fall 1.2% nationally | 0.3008 | 3 |
| 3 | re-s01 — Listing: 14 Mill Lane, Ashby | 0.5990 | 1 |
| 4 | consolidation — [Consolidated knowledge: ashby] | 0.5074 | 2 |
| 5 | re-s03 — Sold: Church Row cottage | 0.4641 | 4 |
| 6 | re-s05 — Living in Ashby | 0.4519 | 5 |
| 7 | consolidation — [Consolidated knowledge: kelso] | 0.3526 | 6 |

**The live re library does contain market data:** re-s04, Kelso Vale market figures, Q3 2026 (personal_note/work), reports own sales plus Land Registry data: average sold price £352,000, +3.1% year over year; 41 days to an offer versus 48; three-bedroom homes half of sales. It is in the live library of 12 chunks/sources, but is absent from both re-05 retrieved lists. It supports Kelso Vale Q3, not Ashby-specific figures for the current month or a mortgage-rate number. re-s08 is national context, not a local statistic. Do not change the expected_gate until Soham decides whether this request should proceed with that limited context.

## fs-06: retrieved chunks and library evidence

Topic: A member’s first year of strength training.

| Baseline rank | Chunk / source | Cosine | Business-block rank |
|---|---|---|---|
| 1 | fs-bp — Business profile | 0.4586 | excluded |
| 2 | fs-s05 — PulseFit opens new Harlow Quay gym with free first month | 0.3018 | 2 |
| 3 | fs-s04 — Protein timing: what the research says | 0.3164 | 1 |
| 4 | fs-s01 — Autumn timetable | 0.4519 | 3 |
| 5 | fs-s02 — Coach profile: Ana | 0.3682 | 4 |

**The live fs library has no individual member story.** Its six chunks/sources are the business profile, Autumn timetable, Coach profile: Ana, Row-a-thon for the food bank, Protein timing: what the research says, and the PulseFit opening article. Ana is a coach biography; the row-a-thon is a group fundraiser (32 members, 100 km, £1,240), not a member’s first year or an individual strength-training result. Expected_gate remains low_coverage.

The guarded source audit is saved in evals/results/quality_v1/business-block/library_audit.json (synthetic re/fs rows only).

## Full live prompt-token change per business case

Default D-Opus-low prompts are rendered from each live retrieval state, including all voice, source, structure, style, context and citation blocks. Before uses the verified flag-off baseline; after uses the business block. These free endpoint counts include message framing and are full prompt counts, not just the inserted block. For a low_coverage outcome, the rendered prompt is hypothetical: the live pipeline stops before drafting. The last column accounts for that by counting zero draft input tokens on a stopped case. No draft request was sent by this measurement.

| Case | Before tokens | After tokens | Rendered delta | Gate before → after | Gate-aware delta |
|---|---|---|---|---|---|
| re-01 | 6,012 | 6,316 | +304 | pass → pass | +304 |
| re-02 | 5,453 | 5,757 | +304 | pass → pass | +304 |
| re-03 | 4,943 | 5,247 | +304 | pass → pass | +304 |
| re-04 | 6,161 | 6,140 | -21 | pass → pass | -21 |
| re-05 | 6,167 | 6,146 | -21 | pass → pass | -21 |
| re-06 | 6,156 | 6,135 | -21 | pass → pass | -21 |
| re-07 | 5,346 | 5,650 | +304 | pass → pass | +304 |
| re-08 | 3,494 | 3,438 | -56 | low_coverage → low_coverage | +0 |
| fs-01 | 4,705 | 4,942 | +237 | pass → pass | +237 |
| fs-02 | 3,858 | 4,095 | +237 | pass → pass | +237 |
| fs-03 | 4,552 | 4,789 | +237 | pass → pass | +237 |
| fs-04 | 4,434 | 4,671 | +237 | pass → pass | +237 |
| fs-05 | 4,481 | 4,718 | +237 | pass → pass | +237 |
| fs-06 | 5,434 | 5,402 | -32 | pass → pass | -32 |
| fs-07 | 3,355 | 3,212 | -143 | low_coverage → profile_only | +3,212 |
| bo-01 | 4,317 | 4,524 | +207 | pass → pass | +207 |
| bo-02 | 4,349 | 3,194 | -1,155 | pass → profile_only | -1,155 |
| bo-03 | 3,360 | 3,187 | -173 | low_coverage → profile_only | +3,187 |
| bo-04 | 3,366 | 3,193 | -173 | low_coverage → profile_only | +3,193 |
| bo-05 | 3,361 | 3,188 | -173 | low_coverage → profile_only | +3,188 |
| bo-06 | 4,434 | 4,641 | +207 | pass → pass | +207 |
| nb-01 | 4,636 | 3,381 | -1,255 | pass → low_coverage | -4,636 |
| nb-02 | 4,475 | 4,672 | +197 | pass → pass | +197 |
| nb-03 | 3,541 | 3,378 | -163 | skipped_first_post → low_coverage | -3,541 |
| nb-04 | 3,555 | 3,392 | -163 | skipped_first_post → low_coverage | -3,555 |
| nb-05 | 4,639 | 3,384 | -1,255 | pass → low_coverage | -4,639 |
| nb-06 | 4,651 | 3,396 | -1,255 | pass → low_coverage | -4,651 |

Across 27 business cases: rendered full prompts **−3,047 tokens** in total; gate-aware draftable input **−6,480 tokens**. The fixed block counts remain re 314, fs 247, bo 227, nb 207 input tokens including message framing. Added material can increase total input on cases that previously missed the note; removed note/source wrappers, story offers and redundant grounding rules can reduce it elsewhere.

## Code checks and verification

- Block presence from the live measurement: **27/27 business, 0/34 individual**. Individual fixture prompts were also byte-compared against aa7f56c for A, cited B/C and D in the preceding implementation; the field rename does not change individual prompt text.
- Backend: **1823 passed** with `venv/bin/python -m pytest -p no:rerunfailures -o addopts='' -q` from backend. Tester added exact-metadata, gate and new source-required pillar coverage.
- Evals: **136 passed** in the full suite excluding evals/tests/test_guard.py, including the paired-prompt measurement test. That file remains untouched as requested.
- `BUSINESS_BLOCK_ENABLED=0` still restores the original retrieval, archetypes and gate. Rollback retrieval was exercised for every business case as part of this measurement. No new migration was needed.
- Code, tests, CODEBASE.md, PROMPTS.md, docs/QUALITY.md, docs/ARCHITECTURE.md and the business analysis reflect writable_from_profile. Step 11 was not run.

## Files changed

- `CODEBASE.md`
- `PROMPTS.md`
- `backend/agents/archetype_agent.py`
- `backend/agents/draft_prompt.py`
- `backend/agents/refine_agent.py`
- `backend/agents/refine_cited_agent.py`
- `backend/agents/refine_prompt.py`
- `backend/agents/retrieval_agent.py`
- `backend/config/features.py`
- `backend/config/niches.py`
- `backend/memory/profile_store.py`
- `backend/memory/vector_store.py`
- `backend/migrations/021_business_profile_retrieval.sql`
- `backend/pipeline/checks.py`
- `backend/pipeline/graph.py`
- `backend/pipeline/state.py`
- `backend/tests/fakes/supabase.py`
- `backend/tests/test_business_block.py`
- `backend/tests/test_business_posts.py`
- `backend/tests/test_refine_cited.py`
- `backend/utils/business_notes.py`
- `backend/utils/citations.py`
- `backend/utils/specifics.py`
- `docs/ARCHITECTURE.md`
- `docs/QUALITY.md`
- `docs/analysis/business-profile-note.md`
- `evals/baselines/2026-10-16-business-block.md`
- `evals/baselines/2026-10-16-relabel-baseline.md`
- `evals/goldens/quality_v1/cases.jsonl`
- `evals/guard.py`
- `evals/quality_fixtures.py`
- `evals/quality_metrics.py`
- `evals/quality_retrieval.py`
- `evals/tests/test_quality.py`

Files created in the original implementation: migration 021 (DB exclusion RPC), test_business_block.py (coverage), this measurement report. This revision created only ignored measurement/audit artifacts; scratch scripts stay outside the repo and are removed. No new stopgap was introduced.

## Step 11: frontend contract and paid before/after check (2026-10-16)

Completed at **$2.491464**, under the $5 cap. The eval database has migration 021; default D-Opus-low was run once per business case per arm with the flag off/on, respecting real coverage gates. **54 valid case-arms, 43 drafts (22 before, 21 after), 11 gate stops**. One transient re-07/before retrieval failure made no paid call and was retried; all final source-id sequences match step 10. No commits, pushes, frontend changes or application changes.

**A — contract finding:** successful profile_only drafts serialize as status=ok and display/autosave normally for /generate and /generate/stream. Both APIs preserve the new pillar-needs advice in suggestion. The frontend drops it: generateOutcome has no suggestion field; CreatePost stores only closest sources/opinion flag; ConfigureForm/LowCoverageNotice show hard-coded generic copy. Onboarding’s generateErrorMessage also substitutes generic text. GenerateResult omits suggestion although api.ts declares it. Thus the specific instruction about what to add never displays. Detailed paths: [frontend contract audit](../results/quality_v1/business-block-gen/frontend-contract.md). No frontend fix was made. Existing checks: 31 frontend outcome/stream/onboarding tests and 74 backend stream/business tests passed.

**B — quality on the same 17 drafted pairs (dev 10, hold-out 7):**

| Criterion | Dev before → after | Hold-out before → after |
|---|---|---|
| 13, source-audited | 9/10 (90%) → 5/10 (50%) | 3/7 (42.9%) → 4/7 (57.1%) |
| B6b, all applicable per-post fields | 8/10 (80%) → 5/10 (50%) | 3/7 (42.9%) → 3/7 (42.9%) |

The rates use Sonnet-assisted judgments followed by source-by-source adjudication. Raw replies, Boolean/rationale contradictions and every correction remain available. Missing needs honestly omitted were not scored as fabricated. The source audit flags unsupported practices, guarantees, event logistics and extra temporal/majority claims; it allows current views and generic advice. B6b sequence quality is scored separately per persona. These are single drafts, not significance-tested population estimates.

**Changed gates:** nb-01/03/04/05/06 now stop low_coverage (no after draft); fs-07 and bo-02/03/04/05 are profile_only. After profile_only: fs-07/bo-03 stay grounded; bo-02 promises no week-long queue/downtime, bo-04 invents brake-inspection scope, and bo-05 invents staffing/booking/no-handoff guarantees. Wheelwright repeatedly restates the same services and mechanic/van/same-week facts: promotional/repetitive, without hard selling.

**Close read:** re-05 invents no new local market figure; before adds unverified "recently" to an undated real sale note. fs-06 invents no named member or first-year result, but before asserts an unstated simple-teaching practice and after upgrades a typical-customer description to an actual majority. Both miss the member-story pillar. bo-06’s prices are explicitly dated spring 2026 and sourced in both arms; they are stale for the winter topic, but no new winter price/offer was invented. Exact quotations and markers are in the report.

**B citations:** all **29** final after B spans checked against the actual block: **25 supported, 4 not fully supported** (bo-04 e-bike inspection scope; fs-03 every-session coach coverage; fs-06 actual majority of coached customers; re-04 majority of clients being moving families). All spans and exact profile evidence are in the B audit.

**Instrumentation:** paired median visible first word **3.671s → 3.695s**; actual paired input **85,277 → 87,039 (+1,762)**. Across all drafted cases, actual input **106,299 → 99,819 (−6,480)** because gates change the population. TTFW is pipeline start to first settled visible post prose, excluding HTTP/auth/browser time. The shared LinkedIn format still says "No call-to-action", conflicting with the business-CTA criterion; no prompt was changed here.

Saved under [business-block-gen](../results/quality_v1/business-block-gen/report.md): drafts, prompts/responses, complete traces, raw/audited scores, all unsupported-claim quotations, every B citation/evidence, sequence reviews, timing/token CSV, spend ledger and reconciliation. The scoped usage_events check found **96 calls totalling $2.491464**, matching the ledger. See [full report](../results/quality_v1/business-block-gen/report.md) and [scoring method](../results/quality_v1/business-block-gen/audit-method.md). The results directory is ignored by git; the baseline section is tracked. Stopped after the requested check.
