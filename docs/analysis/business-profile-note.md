# How the business profile note reaches a post

Analysis and design only, 2026-10-16, code at `aa7f56c` (main). Nothing was changed. Measurements: the quality_v1 run `2026-10-16-exact-vector` (local results files), the eval project (read-only, through the evals env guard), and Anthropic's free token-counting endpoint for `claude-opus-5-5` (the D-Opus-low drafter). No generation calls, $0.

## Headline

- The note reaches the draft in 8 of the 26 business cases that need it (31%). In the other 18 the draft has the business's name and kind of business (from the voice block, marked "never a source of content") and nothing else: no area, services, differentiators, customer or offers.
- It is small: 84-189 tokens for the eval personas, 237 for a realistic salon profile, 762 at the form's maximum (Claude tokens).
- Recommended: option A, always give it to the draft as a fixed business block outside retrieval, exclude it from retrieval, and give it its own citation id. That also fixes a known issue the stated product decision assumes is already true: today the note unlocks story structures.

## Facts checked

| Claim | Verdict | Evidence |
|---|---|---|
| Built by `profile_note()`, stored by `_save_profile_to_memory()` through `ingest_content()`, `source_type` business_profile, `memory_context` work, authorship user_stated, one row replaced per save | Correct | `utils/business_notes.py:42-52`; `routers/account.py:122-148` (`replace_source_id=existing`, `authorship_set_by="rule"`); tone is left out of the note on purpose (`business_notes.py:43`) |
| `business_context()` gives only niche, tone and pillar; facts reach a post only through the note | Correct, with one addition | `business_notes.py:74-91`, used at `pipeline/graph.py:40`. Addition: `_ensure_voice_profile` (`account.py:108-120`) puts the business name and niche label into the voice profile (`Name`, `Role`), shown in the voice block (`memory/profile_store.py:116-118`) under "never a source of content, stories or facts" (`agents/draft_prompt.py:95`). It is written once, when the profile is first created, so a renamed business keeps its old name there. `location` (service area) is saved but no prompt reads it |
| `BUSINESS_PROFILE` frame, in `SELF_FRAMES` | Correct | `utils/frames.py:26`, `:107-108`; frame text `:174-178`: "facts... may be stated as written. Never add a listing, sale, price, client, review, award or result that it does not state." |
| Recorded decision: the note is never event evidence for story structures | **Not recorded and not enforced** | No doc states it as a decision. The code does the opposite: `allowed_archetypes` unlocks story structures when any retrieved chunk is self-authored (`agents/archetype_agent.py:78-87`, `:114`), and `BUSINESS_PROFILE` is self-authored, so the note alone unlocks them. `docs/ARCHITECTURE.md` lists this as an open known issue. The closest written rule is QUALITY.md B6b "Business voice": "no invented first-person stories" |
| D-Opus-low default, ~2.3k token target, time-to-first-word guard | Correct | `config/features.py:25-29`; GENERATION_ARCHITECTURE.md §10.1; ARCHITECTURE.md records today's prompt at ~18.4k tokens |
| More than one source of truth for tone; onboarding's first post lacks real tone and pillar | Correct, both | Section 5 |

## 1. The path today

**Write.** `PUT /account/segment` → `_save_profile_to_memory` (`account.py:122`) → `profile_note()` (one `Label: value` line per filled field: kind of business, name, area, website, what we do, differentiators, customer, offers) → `ingest_content(source_type="business_profile", memory_context="work", replace_source_id=existing)`. One chunk (the note is far under 500 words), embedded and stored in `embeddings`, plus tags (Sonnet), entities (Haiku), a source summary (Haiku). Saving again replaces it in place.

**Retrieval.** Like any chunk:
- vector: exact per-user cosine (migration 013) of the note against `f"{topic}. {context}"` (`retrieval_agent.py:331`);
- BM25: the note's words in the in-memory index (`vector_store.py:275`);
- RRF merge (`vector_store.py:419`), then kept only if its cosine reaches 0.30 or its normalised BM25 reaches 0.30 (`config/retrieval.py:14-15`);
- entity enrichment can add it when a query names one of its entities;
- coverage gate (`retrieval_agent.py:56`): pass when the best chunk reaches either floor; otherwise `low_coverage` (empty post), or `skipped_first_post` when the user has no posted topics (`graph.py:47`), in which case the post is written anyway.

**In the prompt (when retrieved).** The draft prompt is one user message (`draft_agent.py:175-178`), in this order: intro, voice, format, **sources**, topic (with the BUSINESS POST block at its end, `draft_prompt.py:102-108`), structure, source rules, style, citations, output. The note appears inside `<sources>` in rank order as `<source id="S#" kind="BUSINESS PROFILE" type="business_profile" tags="…">…</source>`, and the BUSINESS PROFILE rule joins the source rules. Retrieved, it also makes `is_self_authored` true, which offers the story structures (above).

**Size** (Claude tokens for `claude-opus-5-5`; MiniLM word-pieces for the embedder):

| Profile | Characters | Claude tokens | as a `<source>` element | MiniLM tokens |
|---|---|---|---|---|
| bo (eval) | 292 | 103 | 190 | 63 |
| fs (eval) | 375 | 122 | 209 | 72 |
| nb (eval) | 210 | 84 | 168 | 44 |
| re (eval) | 560 | 189 | 265 | 120 |
| realistic salon (written for this analysis, through `profile_note`) | 667 | 237 | 290 | 150 |
| every field at the form maximum (`account.py:31-37`) | 2,186 | 762 | 815 | 486 |

At the form maximum the note is longer than the embedder's 254-token window, so its second half is never embedded (see `chunking-3.4.md`).

## 2. Measured impact

27 business cases (re, fs, bo, nb); 26 expect the note (`must_use_all`). Rank is the note's place among the chunks that passed the relevance floor; k is how many passed.

| Case | Split | Pillar | Note rank | k | Gate | Top cosine |
|---|---|---|---|---|---|---|
| re-01 | dev | new_listing | – | 6 | pass | 0.49 |
| re-02 | dev | new_listing | – | 5 | pass | 0.69 |
| re-03 | dev | just_sold | – | 4 | pass | 0.61 |
| re-04 | dev | market_update | 2 | 6 | pass | 0.61 |
| re-05 | holdout | market_update | 1 | 6 | pass | 0.60 |
| re-06 | dev | neighborhood_spotlight | 4 | 6 | pass | 0.70 |
| re-07 | dev | buyer_seller_tips | – | 5 | pass | 0.63 |
| re-08 | dev | client_story | – | 0 | low_coverage | 0.26 |
| fs-01 | holdout | class_spotlight | – | 2 | pass | 0.29 |
| fs-02 | holdout | training_tips | (not expected) | 1 | pass | 0.63 |
| fs-03 | holdout | schedule_and_offers | – | 1 | pass | 0.35 |
| fs-04 | holdout | meet_the_coach | – | 1 | pass | 0.62 |
| fs-05 | holdout | studio_community | – | 1 | pass | 0.33 |
| fs-06 | holdout | member_story | 1 | 5 | pass | 0.46 |
| fs-07 | holdout | – | – | 0 | low_coverage | 0.21 |
| bo-01 | dev | – | – | 1 | pass | 0.62 |
| bo-02 | dev | – | 1 | 1 | pass | 0.56 |
| bo-03 | holdout | – | – | 0 | low_coverage | 0.25 |
| bo-04 | dev | – | – | 0 | low_coverage | 0.20 |
| bo-05 | dev | – | – | 0 | low_coverage | 0.24 |
| bo-06 | dev | – | – | 1 | pass | 0.32 |
| nb-01 | dev | menu_highlight | 1 | 1 | pass | 0.33 |
| nb-02 | dev | menu_highlight | – | 1 | pass | 0.75 |
| nb-03 | holdout | specials_and_events | – | 0 | skipped_first_post | 0.16 |
| nb-04 | dev | behind_the_scenes | – | 0 | skipped_first_post | 0.12 |
| nb-05 | dev | meet_the_team | 1 | 1 | pass | 0.34 |
| nb-06 | dev | guest_story | 1 | 1 | pass | 0.34 |

Of the 26 that need it: in the top k 8; missed with the gate passing on other sources 11 (the post is drafted with no business facts); missed with `low_coverage` 5 (no post at all); missed with `skipped_first_post` 2.

nb-03 and nb-04 skip because persona nb (a new business) has no posted topics, so `first_post` is true (`graph.py:47`) and the gate lets a post through with nothing retrieved (`retrieval_agent.py:71-72`). Those posts are written from the topic and context alone, which is exactly when a new business most needs its own facts.

Note the 5 `low_coverage` cases: with the note always present, a post about the business could be written; whether the gate should allow it is decision 2 below.

## 3. Options

The fixed block in A and B renders the note's text, not a summary: "BUSINESS FACTS (stated by the business; may be stated as written; never evidence that something happened)" followed by the note, with a citation id the drafter must use for these facts (for example `[[B]]`, alongside `[[S#]]`, `[[R]]`, `[[V]]`).

| | (A) Fixed context, excluded from retrieval | (B) Fixed context and retrievable | (C) Retrieval only, better ranking |
|---|---|---|---|
| Prompt tokens per business post | +84-237 typical (up to 762) on every post; today ~200 only on the 31% where it is retrieved. ~1% of today's ~18.4k prompt; 4-10% of the 2.3k target | as A, plus the same text again as a source whenever retrieved (the duplicate costs tokens and can win a source slot) | unchanged |
| Time to first word | a few hundred more input tokens: small next to today's ~18k, not measured. Caching: Opus 5.5 caches prefixes of 512+ tokens (reads 0.05×, writes 1.25× for 5 min). The draft prompt is one user message whose per-user stable part is intro + voice; putting the business block right after voice extends that prefix, but a user's posts are usually more than 5 minutes apart, so a cache would help only regenerate and refine bursts. Not a reason to choose A | as A | unchanged; option-specific ranking work (below) may add a query |
| BUSINESS_PROFILE frame | the block carries the frame's rule; the note is no longer a retrieved chunk, so `frame_rules` and the sources block lose it | rule in both places | unchanged |
| "Never event evidence" | enforced by construction: the block is not a source, so it can't be the note an EVENT names, and it no longer counts in `is_self_authored`, so it stops unlocking story structures (fixes the known issue) | not enforced unless `BUSINESS_PROFILE` leaves `SELF_FRAMES`; when retrieved it still unlocks stories | not enforced unless `BUSINESS_PROFILE` leaves `SELF_FRAMES` |
| Coverage gate | counts retrieved sources only, so the note no longer passes the gate by itself; decide whether a business post with only its profile may be drafted (decision 2) | ambiguous: retrieved note still passes the gate on its own | unchanged: 5 empty posts in quality_v1 stay |
| Fabrication risk | lower: area, services and offers are always there, so the model has no reason to invent them; story unlock removed. New risk: the profile in every post (repetitive, salesy), covered by B6b "Pillar variety" and "Local and specific (when relevant)" | as A, plus double exposure | unchanged: 18 of 26 posts have no business facts |
| Individual users | no block (`business_context` is None), prompt byte-identical: test it | same | none |
| Rollback | a flag: off restores retrieval of the stored note (rows untouched, only filtered) | flag | revert the ranking change |
| Work | render the block and its citation id; exclude `source_type business_profile` from the vector RPC, BM25 corpus and entity enrichment; teach the citation and specifics checks that `[[B]]` facts are grounded; story offer counts retrieved own notes only | as A without the exclusion, plus de-duplication | see below |

What "better ranking" in C could be, and why each falls short: prepending a title or heading does not make a list of business facts resemble a topical query (best cosines 0.01-0.30 today); a per-segment boost for `business_profile` that always ranks it in is option A done through retrieval, with retrieval's limits (it still competes for a slot and the floor); query expansion with the business's name and area helps only topics that mention them.

Recommendation: A. It is the only option that guarantees the facts are present, it makes the "never event evidence" rule true by construction, and its cost is a few hundred tokens.

## 4. Eval consequences

Today the note is labelled as a needed source (`must_use_all`) in 26 cases, so B1 recall counts it. Under each option:

- **A.** Remove `<persona>-bp` from `must_use_all` / `must_use_any` in the 26 cases and record instead `business_block: true` on business cases. B1 then measures real retrieval only. Add a code check, run with the retrieval harness from the prompt or trace: the business block is present for every business case and absent for every individual case (expected 27/27 and 0/34). The relabel raises B1 recall mechanically (16 misses disappear): record it as a relabel baseline before comparing any change against it. Gate accuracy changes for the 5 `low_coverage` business cases depending on decision 2.
- **B.** Labels unchanged (the note is still retrievable), plus the same presence check; recall still mixes retrieval with a block that is always there, so it overstates nothing new but stays hard to read.
- **C.** Labels unchanged; recall on `*-bp` is the target metric.

Mapping to QUALITY.md:
- Criterion 13 "No invented business or customer claims": its judge reads "quote + profile note + sources"; under A it reads the business block (always present), so a claim is judged against what the drafter actually had.
- B6b "Needs only from the author": `needs_present` facts that live in the profile become available in every case; `needs_missing` stays the same check.
- B6b "Business voice": add a code check that no story structure is chosen with the business block as its only own material (falls out of A).
- B6b "Local and specific": becomes meaningful for the 18 cases where the facts were missing.
- B6b "Pillar variety in sequences": watch for the profile repeated in every post.
- Assumption 6 ("every business user has the profile note"): unchanged.

## 5. Tone and onboarding

Where business tone is written and read:

| Where | What |
|---|---|
| `routers/account.py:38-39, 51-55` | written: `business_profile.tone` (one of 5 keys in `config/niches.py:169-175`) and `tone_notes` |
| `utils/business_notes.py:82-88` → `draft_prompt.py:113-114` | read: "BUSINESS POST: … Write it in this tone: {label}. {tone_notes}" |
| `frontend/components/CreatePost.tsx:56`, `create/ConfigureForm.tsx:82` | the Create page shows every user, business users included, the individual tone selector (casual / technical / storytelling, default casual) |
| `routers/generate.py:45` → `pipeline/graph.py:225, 278` → `utils/formatters.py:411-419` | read: the request tone becomes "Format and tone instructions: Tone: …"; an unknown key falls back to casual silently (`_normalise(tone, "casual")`) |
| `routers/onboarding.py:73-75` | the business first post passes the business tone key (e.g. `friendly`) as the request tone |

So every business post carries two tone instructions: the request tone (casual unless the user changes the selector) in the format block, and the business tone in the BUSINESS POST block. The onboarding first post is worse: `friendly` is not a key of `_TONE`, so it silently becomes "casual and conversational" next to "Friendly and approachable". It also passes no pillar (`GenerateRequest` without `pillar`, so no pillar block), and a business user's story is not ingested (only individuals' is, `onboarding.py:63-71`), so it reaches the draft only as context.

Same branch or separate: separate (`fix/business-tone-onboarding`), after A. Tone is voice, in different files (formatters, Create page, onboarding), with its own fix (one tone for business posts: the account's, with the request selector hidden or mapped for business users); option A already gives the onboarding first post its business facts, so the onboarding branch then only adds the pillar and decides whether the business story is stored as a `user_stated` note.

## Decisions for Soham

1. **How the note reaches the draft.** A (fixed block, excluded from retrieval) / B (both) / C (retrieval only). Default: A. Reason: the only option that always delivers the facts and makes the "never event evidence" rule true by construction, for a few hundred tokens.
2. **Gate for a business post with no retrieved source.** Fail as today (`low_coverage`) / let it through as a "profile only" post with a short length target, recorded in the trace. Default: let it through for business users. Reason: the business's own stated facts are honest material for a short post; 5 eval cases are empty posts today.
3. **Citation for business facts.** A new `[[B]]` marker / treat the block as source `S0`. Default: `[[B]]`. Reason: keeps it out of the sources block, so it can't become event evidence or count as a retrieved source.
4. **Relabel quality_v1.** Move the note from `must_use_all` to a `business_block` flag in the same branch and record the relabel baseline. Default: yes, same branch. Reason: otherwise recall would count a source retrieval no longer handles.
5. **Tone and onboarding.** Fix with A / separate branch after A. Default: separate. Reason: different files and a voice question; A already fixes the missing facts on the first post.

## Decisions taken and implementation (2026-10-16, feat/business-block)

Option A selected: fresh account facts after voice, outside retrieval, cited `[[B]]`. Stored profile notes stay in Library but are excluded in Postgres before vector/BM25/entity selection. Migration 021 precedes backend deployment (020 → 021). `BUSINESS_BLOCK_ENABLED=0` restores the prior read path and prompts. Story structures depend only on retrieved own sources.

Profile-only is allowed for no pillar or writable_from_profile=true with the existing short first-post length range; false remains low_coverage even for a first post and asks for the pillar's needs. All 36 pillars have explicit writable_from_profile. Soham revised the field name/meaning and narrowed the true set to 11 evergreen pillars; neighborhood_spotlight and behind_the_scenes are false because the profile alone does not provide their details. Every business golden now has expected_gate, including the 14 with no required retrieval source. The relabel baseline was re-scored with retrieval unchanged.

Account identity is applied per request and omitted from business draft/refine voice blocks, rather than rewriting stored voice data. This covers existing renamed businesses immediately, preserves style settings, and keeps rollback reversible. Refine retains the generation trace's facts. Tone and onboarding are separate work.

See `evals/baselines/2026-10-16-business-block.md` for all pillar values, all 27 labels, free token counts, and measurement status. Migration 021 is applied to eval and reviewed by Soham; step 10 is complete at $0. Business gate accuracy is 16/17 dev and 8/10 hold-out; three numeric-coverage/label disagreements remain (re-05, fs-06, bo-06), documented for review without changing those labels. Live full prompt counts and the source audit are in the report. No paid generation or judging (step 11) has run.
