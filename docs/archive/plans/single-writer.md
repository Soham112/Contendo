# Plan: feat/single-writer

Approved by Soham on 2026-10-09. This file is the reference for steps 2–9. The code is the source of truth: if this file and the code disagree, say so.

**Decision (Soham, 2026-10-10): C-Opus is the production default and pipeline A is retired.** See "Decision and result" at the end of section 11.

**Decision (Soham, 2026-10-10, `fix/shorten-not-trim`): an over-length post is compressed, never trimmed by deletion.** This replaces decision 3 and every later description of the trim in this file. See "Compress replaces the trim" at the end of section 6.

**Status:** steps 1–9 are built and the full ablation selected C-Opus. The independent-review fixes are built in scratch pending Soham's "apply"; no production migration has been run.

## How we work on this branch

- One step at a time. Claude Code builds each step in a scratch copy outside the repo, shows the diff and the `pytest` results, and applies it only when Soham says "apply".
- After a step is applied, Claude Code stops. Soham makes a WIP commit before the next step starts.
- Claude Code never commits, pushes or creates branches.
- Never read a `.env` file, query production or any database, or print a secret (at most the first 6 and last 4 characters).
- Evals run only when Soham says so. The smoke set is listed and confirmed before it runs.
- Every step summary ends with "Files created" and "Stopgaps introduced".
- No cheap fixes (see CLAUDE.md):
  - no keyword, verb or topic lists to infer meaning
  - no substring matching on names
  - no regex on model prose to guess intent
  - no silent fallbacks and no swallowed exceptions
  - no duplicated rules or tables
  - no magic numbers without a named constant and a reason
  - any stopgap is labelled `STOPGAP:` in code with the proper fix named

## Why this branch exists

Only the drafter sees the sources, but several models write or direct rewrites after it. Every behavioural rule (perspective, no invented specifics, length, style) is copied into three or four prompts, and the copies drift.

Recorded regressions caused by the rewrite chain:
- The critic wrote example sentences ("At Data Axle, I watched a model tank…", "2am") that the humanizer pasted in.
- The humanizer produced 33 invented specifics in one run.
- The critic asked for "missing" story sections and told the writer to "use the self-authored chunks" and "add the specific numbers", pulling content from unrelated chunks.
- The humanizer kept a link the critic had flagged.
- Invented analogies and the author's own practice were credited to "the article".
- A burnout post (founder-06) used an investor-intros event, because the archetype step picked the event before drafting.

## Decisions (Soham, 2026-10-09)

1. **Review model:** Sonnet. Measure it on the review regression set; if Haiku is also cheap to run on that set, report both.
2. **Redraft input:** the redraft never sees the reviewer's free-text `why`. It gets only the issue type, the span text, the fixed instruction for that type, the source ids and the verbatim evidence.
3. **Trim:** deletes whole spans. Code deletes and re-measures. *Superseded 2026-10-10: compress, section 6.*
4. **Pipeline A:** gets `finalise` and final validation in record-only mode. A's behaviour does not change.
5. **Quality under B:** `quality="draft"` behaves like C (no review, no redraft). `quality="polished"` behaves the same as standard B (no scorer, no rewrite loop). Record in CODEBASE.md that the Create page does not send `quality`. Quality modes are decided in `chore/cleanup`.
6. **Under-length:** never triggers a redraft, for any target. It is recorded in the trace as `under_length` with counts. Only over-length triggers a redraft (then trim). Asking the drafter to lengthen a post brings back padding and invented detail.
7. **Selection refine (step 9):** uses the `source_index` stored in the trace to map S-ids to chunks. Never rebuild ids from retrieval order.
8. **Smoke set:** must include at least one golden whose sources are external only (perspective `learned`), plus pm-05, founder-06 and ds-09. Claude Code lists the final set before running.
9. **Step 9 scope:** refine alignment and the frontend notice only. Deleting the unused pipeline-A code happens on a separate branch (`chore/remove-pipeline-a`) after the ablation decision, not on this one.

Later, not on this branch:
- **`fix/retrieval-failure-status` is the first branch after this merge**: distinguish retrieval failures from empty memory/low coverage and replace topic/source excerpt logs with request IDs, categories and counts. Inherited behaviour is labelled only on this branch.
- **`feat/citations-ui`** (added 2026-10-10): show the author the per-sentence citations and the deterministic check results that C-Opus already records in the trace (`checks_final`, `citations`), so the author decides what to change. Until then the checks are record-only by decision (`pipeline/checks.py`, `checks_node`).
- **Selection refine for posts with no source index** (pipeline A's and older posts): today they keep the earlier writer (Sonnet 4.6, frame-formatted sources, the specifics guard). Proposed, not built: when pipeline A's code is removed, give them the cited writer too, with a source index built from the trace's stored chunks (they have no citations to disagree with), and delete the earlier writer. Needs Soham's OK.
- **`chore/deps-lock`**: the pydantic pin (2.10.3) is below what `deepeval` and current Supabase packages need.
- **Retrieval failures reported as low coverage**: in the full ablation a Supabase disconnect during retrieval gated ds-09 on variant C as if the memory did not cover the topic. A retrieval error should be an error.
- **Flaky test**: `tests/test_api_safety.py::test_repeated_unknown_kids_do_not_refetch_within_cooldown` fails about once in a dozen runs (`InvalidKeyError('Coords should be 32 bytes for curve P-256')` from the test's generated key).
- Pipeline A still measures length with `count_words` (every token, placeholder lines included). Switch it to `prose_word_count`, or remove it with A on `chore/remove-pipeline-a`.
- **`fix/ingest-attribution` follows `fix/retrieval-failure-status`** (decided 2026-10-10). Fourth occurrence of the author's own notes stored with an external frame: founder-08, founder-04, ds-04, and pm-06, where the 6b live check produced "an article on product discovery suggests…" for the author's own practice. The review cannot catch it, because the source index says the note is external.
- **`feat/ask-author`** (recorded 2026-10-10): when B removes unsupported reactions or motives, ask the user to supply them instead of inventing them. The data is already kept: `review.removed` in the trace and in the response's `review` lists what was removed, by kind (`feeling_or_reaction`, `motive`, `fact_or_event`, `generalisation`) with the removed text. No UI on this branch.
- Fold the archetype choice into the drafter and drop the Haiku call.
- Pipeline A's `format_chunks_by_frame` still defaults a missing `source_type` to "article" (the single-writer sources block shows `unknown`). Fix it or delete it with pipeline A on `chore/remove-pipeline-a`.
- `STYLE_RULES` keeps the humanizer's wording ("patterns to eliminate", "a point the draft already makes") and its realistic example phrases, because pipeline A's prompts are frozen. Reword it for a writer, with placeholder examples, when A is removed. The same goes for the shared blocks that say "chunk" and carry A's examples (no-notes rule, visual placeholder rules). Decided 2026-10-09: one copy until then.
- For `feat/archetype-set`: the `teach_me_something` structure asks for an analogy, so the drafter invents one (pm-09's tournament analogy in the step 3 live check). Proper fix: no archetype structure may require an element the sources don't supply. All variants share the archetype structures, so this does not bias the ablation.
- When A is removed, reword `STYLE_RULES` so it describes patterns instead of quoting example phrases ("In today's...", "game-changing", "data-driven"). Quoted examples invite a phrase list and can be copied.
- Existing cheap fixes, labelled `STOPGAP:` in code on 2026-10-09 (comments only), each with its proper fix:
  - `utils/specifics.py`, currency suffixes and "time" phrases: open-ended lists. Proper fix: structured extraction of money, dates and durations (an entity recogniser, or the structured review), not longer lists.
  - `utils/frames.py`, `infer_seniority_level`: seniority from keywords matched as substrings of the role. Proper fix: `years_of_experience`, or an explicit seniority field at onboarding.
  - `utils/frames.py`, `chunk_frame`: "in the author's field" by substring overlap of topics and tags. Proper fix: decide it at ingest, semantically, and store it (`fix/ingest-attribution`).
  - `agents/humanizer_agent.py`, `_EXAMPLE_RE`: a regex on model prose. Removed with pipeline A (`chore/remove-pipeline-a`).
- The shared format and history blocks contain em dashes in the prompt text itself ("Do NOT use bullet points with dashes — use line breaks instead", "Topics you have already written about — do not repeat these angles"). Reword with A's removal.

---

## 1. Current pipeline as coded (variant A)

Graph in `backend/pipeline/graph.py`:

`load_profile → retrieval → plan → draft → critic → humanizer → predictability_audit → (scorer loop, polished only) → word_count_enforcer → fact_checker → finalize`

| Step | File | Model | Reads | Writes |
|---|---|---|---|---|
| load_profile | `pipeline/graph.py` | none | profile, posted topics | `profile`, `first_post` |
| retrieval | `agents/retrieval_agent.py` | none | topic + context | bundle, confidence, coverage gate |
| plan | `pipeline/graph.py` | none | chunks' authorship | `length_target`, `perspective` |
| archetype (inside `draft_node`) | `agents/archetype_agent.py` | Haiku, structured | own notes in full; external sources by type and tags | archetype, `event_note`, `event_quote` |
| draft | `agents/draft_agent.py` | Sonnet ×1–2 | sources, voice profile, archetype, perspective | draft |
| critic | `agents/critic_agent.py` | Haiku, structured | draft, labelled chunks, voice profile | five verdicts, each with a free-text `fix` |
| humanizer | `agents/humanizer_agent.py` | Sonnet ×1–2 | draft, critic fixes, voice profile; no sources | full rewrite |
| audit | `agents/predictability_audit_agent.py` | Haiku, Sonnet, Haiku (up to 5 calls) | post only | one sentence rewritten, then a whole-post rhythm rewrite |
| enforcer | `agents/word_count_enforcer_agent.py` | Haiku ×0–2 | post only | trim or expand |
| fact_checker | `agents/fact_check_agent.py` | none in normal mode | none | marks `pending` |
| finalize | `pipeline/graph.py` | none | draft | em-dash normalisation |
| background fact check | `agents/fact_check_agent.py` | Haiku | final post, all sources | flags in the trace |

Measured on the 2026-10-08 baseline (`evals/baselines/2026-10-08-standard.md`): 7.4–7.9 Claude calls per post, 35.7–42.2 s, about $0.039–0.043.

Facts that differ from the original brief:
- **Writers:** up to six steps write: drafter, humanizer, audit step 2, audit step 3, enforcer, and the fact-check rewrite.
- **Hidden second draft:** the drafter retries once on a specifics-guard violation, then deletes the offending sentences (`remove_sentences`).
- **Enforcer:** it expands as well as trims (`may_expand`), swallows every exception, and never checks that its output met the target.
- **Fact-check rewrites:** they only run in no-specifics mode, which is off (`NO_SPECIFICS_MODE_ENABLED = False`). In production the only content change after the length gate is em-dash normalisation.
- **The 100 → 101 bug is real:** `word—word` is one whitespace token and becomes `word, word`, which is two.
- **Archetype:** it is not a graph node; it is a Haiku call inside `draft_node`.
- **Quality modes:** `draft` skips critic, humanizer, audit and enforcer. `polished` adds a scorer and up to three humanizer loops. The Create page never sends `quality` (it is only an optional field in `frontend/lib/api.ts`).
- **Source ids:** the sources block shows frame, type and tags only, so there is nothing for a citation to point at.
- **Silent failures:** the critic, audit and enforcer all catch exceptions and carry on.
- **Retrieval:** `retrieval_node` has silent fallbacks and `print` calls. Out of scope for this branch.

## 2. Target pipeline (variants B and C)

**B (as built in step 6c):** `load_profile → retrieval → plan → structure → draft → strip → finalise → checks → review → decide → code fixes → [targeted fix | full redraft → strip → finalise → checks] → review of what a model wrote → trim (if over) → finalise → checks → outcome → end`. At most one drafter call after the first draft.

**C:** `load_profile → retrieval → plan → archetype → draft → finalise → trim → finalise → end`

| Step | Model | Reads | Writes |
|---|---|---|---|
| archetype | Haiku, structured | as today | structure key only, from the source-gated allowed set; no event fields |
| draft | Sonnet ×1 | delimited sources with ids, perspective rule, archetype structure, voice-only profile, style rules, length rule | post with citation markers, plus an event header for story types |
| finalise | code | marked text | clean text, spans, normalised punctuation, validation record |
| deterministic checks (B) | code | spans, source index, length target | issues |
| review (B) | Sonnet, one structured call | numbered spans with their cited source text, topic, context, perspective | issues only |
| redraft (B, at most once) | Sonnet ×1 | the same prompt plus the issue list | new marked post |
| compress (was trim until 2026-10-10) | draft model, one call, only when over the maximum | sources block, numbered sentences with markers | shorter replacements per sentence; code validates and splices them |

Rules:
- Only the drafter writes. Everything after the draft checks and never writes.
- The style rules now in the humanizer prompt (anti-AI phrasing, rhythm, no em dashes, voice) move into one constant that the draft prompt uses. They are not duplicated.
- The drafter's guard retry and sentence removal do not run in B or C. Checks plus the single redraft replace them.
- C uses the same draft prompt as B, so B against C isolates the value of checks and redraft.
- These stay in the shared nodes and must keep working: the perspective decision, the source-gated archetype set, the `general` fallback, the voice-only profile, and writing samples as style only (never a source).
- Typical B is 3 calls. Worst case is 5 (archetype, draft, review, redraft, review) plus a trim.

Quality under B (decision 5):
- `quality="draft"` behaves like C: no review, no redraft.
- `quality="polished"` behaves like standard B: no scorer, no rewrite loop.
- CODEBASE.md records that the Create page does not send `quality` (written when B's wiring lands, step 6).

## 3. Citation format

**Markers.** Every prose span ends with exactly one marker:
- `[[S2]]` or `[[S1,S3]]`: supported by those sources.
- `[[R]]`: stated in the topic or the context.
- `[[V]]`: the author's view or reasoning, with no factual claim.

A span is the text between two markers, so code never has to segment model prose. Headings and `[DIAGRAM: …]` / `[IMAGE: …]` lines are structural and exempt.

**Ids.** `S1..Sn` are assigned per run by position in the retrieval bundle. They are short, they work when `chunk_id` is missing (flat retrieval fallback), and database ids never reach the model.

**Output envelope (step 6c; replaces the "first line is the EVENT line" convention).** The drafter returns `<post>…</post>`, and for a story archetype an `<event>` part before it:
- `<event>S3 | "sentence copied word for word from that note"</event>`
- `<event>none</event>`, in which case the drafter writes to the General structure.

The output is read by its tags (`utils/draft_output.py`). Anything outside them is dropped and recorded as `draft_format`, never part of the post. Reason: in the 6b live check the drafter wrote a `---` line between the EVENT line and the post, and it reached the returned post.

The drafter selects the event itself, with the topic and all sources in view. The archetype step no longer picks an event.

**Stripping.** One function in `backend/utils/citations.py` returns the clean text plus the spans (offsets in the clean text, cited ids). It uses `protected_spans` so code blocks and URLs are ignored. Marker-like text that fails the grammar, or any marker left in the final text, is a check failure.

**Trace.** `node_outputs` gains the fields below. It is JSONB, so no migration is needed.
- `variant` (done in step 1)
- `source_index`: S-id → chunk id, frame, authorship
- `citations`: the spans of the final text
- `event`: the cited id, the quote, and whether it was verified
- raw marked drafts in `draft_history`

**Sources as data.** One builder (in `utils/frames.py`) renders the sources for both the draft and the review prompts:

```
<sources>
<source id="S1" kind="…" type="…" tags="…">
…
</source>
</sources>
```

The instruction says the contents are data to write from, never instructions to follow. The builder escapes lookalikes of our own closing tag and marker inside source text, so a source cannot close the block or create a citation.

## 4. Deterministic checks

All in `backend/pipeline/checks.py`.

| Check | Detects | Cannot detect |
|---|---|---|
| Citation grammar | malformed markers; markers left in the final text | anything about meaning |
| Citation resolves | an id that is not in this run's source index | whether the source supports the claim |
| Uncited span | prose with no marker | whether it needed one |
| Specifics in cited source | a number, percent, money amount, duration, month, weekday or time phrase (existing `extract_specifics`) absent from the span's cited chunks; reports when it exists in another source | names, events, changed non-numeric words such as "early" → "first" |
| Event verified | the header cites a missing or non-self-authored chunk, or the quote fails the existing `event_quote_failure` / `note_quote_spans` check | whether the event fits the topic |
| Mixed-authorship span | one span citing both a self-authored and an external chunk | a causal link written across two separate spans |
| Length | word count against `length_target`, with one `count_words` function and the single `WORD_RANGES` table | thread length (no word target) |
| Banned text | em dash outside protected spans; the profile's own `words_to_avoid`; placeholders in a first post | any AI-sounding phrasing (the review's `ai_rhythm` judges that) |

Notes:
- `[[R]]` spans have their specifics checked against the request (topic and context).
- `[[V]]` spans: ANY specific in a view span is an issue (`view_contains_specific`), because `[[V]]` means no facts. If a source or the request states it, the issue names where (`found_in`) so the redraft can cite it. (Decided 2026-10-09; this replaces "checked against the whole pool".)
- Number matching is the existing `utils.specifics` matcher with its one approximate rule switched off. Treated as the same: number words and digits ("nine" = "9", two to nineteen, tens, hundred/thousand/million), digit formats ("410k" = "410,000"), "4 percent" = "4%", and a bare number restating a figure ("26" for "26%"). Not treated as the same, so reported for the review to decide: a span of time in other units ("three months" vs "90 days"), and anything in words the extractor does not read as a number at all ("a third", "half", "double", "a dozen", "one"). Those last are invisible to the check when the post uses them; when the post has the digits and the source the words, it is flagged.
- Known limits of the matcher: a bare number matches any figure of that value in the cited source, whatever it counts ("41 meetings" passes against "41 percent"); "1" in a post is flagged when the source says "one".
- `event_quote_failure` moves from `agents/archetype_agent.py` to `utils/sentences.py`, so A and B share one implementation.
- **No banned-phrase list** (decided 2026-10-09). A global list only catches what someone listed and grows without limit. AI-sounding phrasing is judged only by the step 6 review (`ai_rhythm`), whose definition describes the patterns (stock openers, filler transitions, motivational framing, evenly balanced sentences, formulaic lists of three) and never lists phrases. The deterministic `banned_text` check keeps the em dash, the profile's own `words_to_avoid`, and placeholders in a first post.
- **Not deterministic:** "first-person event citing an external chunk". Code knows a chunk's authorship but not whether a span narrates an event. A pronoun list would be a cheap fix, so it is not used. Code checks the event header and mixed-authorship spans; the review judges the rest (`external_as_own`).

Length outcomes:
- **Over the maximum:** an issue. It triggers the one redraft, then trim if still over.
- **Under the minimum:** never an issue and never triggers a redraft, for any target (decision 6). Recorded in the trace as `under_length` with the count and the target.

## 5. Structured review

File: `backend/agents/review_agent.py`. Model: Sonnet, through `complete_structured` (decision 1).

**Design as of step 6a-4 (2026-10-09): observations from the model, verdicts in code.** History: the issue-list designs (6a, 6a-2) let the model argue its own findings away; the first observation design (6a-3) was stable but three fields were unreliable (`stated_as` followed the `[V]` citation, `detail_differs` invented differences, `supported_by` ignored additions) and a full-post review took about 30 s. 6a-4 fixes those structurally and is the last, time-boxed iteration: if it misses the bar there is no 6a-5 on prompt wording; the decision is made from the results.

**The reviewer never sees the citations.** The post is shown as numbered sentences only. `wrong_citation` is decided in code from the draft's citation and what the model found.

One compact record for EVERY numbered sentence. Four fields are always given; the rest only when they apply:

```python
class SentenceRecord(BaseModel):
    sentence: int
    content: Literal["fact_or_event", "feeling_or_reaction", "motive", "generalisation", "opinion",
                     "advice_or_question", "analogy_or_comparison", "disclaimer", "other"]
    stated_as: Literal["fact", "authors_view"]
    presented_as: Literal["author_did_or_experienced", "a_source_says", "authors_view", "neutral"]
    supported_by: list[str] = []                 # sources (and/or "request") that state the sentence, apart from unsupported_part
    evidence: str | None = None                  # verbatim from a supported_by source
    unsupported_part: str | None = None          # the exact words of the sentence that nothing states
    detail_change: DetailChange | None = None    # {source_words, post_words}, both verbatim
    link: Link | None = None                     # {sources, stated_by}; present only when the sentence links facts
    off_topic: bool = False

class Review(BaseModel):
    sentences: list[SentenceRecord]
    ai_rhythm: list[RhythmNote]                  # [{sentence, why}], defined by describing patterns
```

Code accepts the two quoting fields only when they check out:
- `detail_change`: `source_words` is a verbatim word-boundary span of a `supported_by` source, `post_words` is a verbatim word-boundary span of the sentence, and the two differ after normalising case, whitespace, number words against digits, and contractions against full forms (`utils/wording.py`; closed sets fixed by English). Otherwise it is dropped and recorded as `invalid_detail`.
- `unsupported_part`: a verbatim word-boundary span of the sentence. Otherwise dropped and recorded as `invalid_unsupported_part`.
- Known limit: a synonym passes the `detail_change` check ("maintains" against "updates" is a difference of wording). Only the prompt asks the model not to report one.

Code derives the seven issue types (`pipeline/review_rules.py`). No model verdicts, no reading of free text. Five of them act in B and two are record-only (see the dated decision below).

| Type | Rule |
|---|---|
| `not_in_sources` | `content` in {fact_or_event, feeling_or_reaction, motive}, or generalisation with `stated_as` fact, and `supported_by` empty; or `unsupported_part` present and `stated_as` fact |
| `wrong_citation` | `supported_by` non-empty, the content is not the author's own, and the sentence's citation (from the draft) is `[V]`, none, or cites something not in `supported_by` |
| `changed_detail` | a `detail_change` that passed its checks |
| `wrong_attribution` | `presented_as` author_did_or_experienced and every supporting source is external (from `source_index` authorship); or a_source_says and every supporting source is self-authored; or a_source_says and no source supports it |
| `cross_source_link` | `link` present, its `sources` spans more than one source, `stated_by` empty |
| `off_topic` | `off_topic` true |
| `ai_rhythm` | from the post-level list |

- A disclaimer, an opinion, advice or a question, and an analogy offered as the author's own framing produce no `not_in_sources`, `wrong_citation` or `wrong_attribution`.
- The prompt gives the reviewer the author's name and role (nothing else from the profile), so the author's own company name is not treated as unsupported.

**Parallel review.** The numbered sentences are split into contiguous groups (`SENTENCES_PER_GROUP` = 4, `MAX_REVIEW_GROUPS` = 6; `_TOKENS_PER_RECORD` = 150) and one call per group runs concurrently. Every call sees the full sources block, topic, perspective, event line and the whole numbered post, and records only its assigned sentences and reports `ai_rhythm` only for them. Code merges the answers. Any group failing or truncating makes the whole review `not_reviewed`; coverage (every sentence exactly once across groups) is checked after the merge. The per-group token budget comes from its sentence count and a named per-record constant.

**No prompt caching.** A cache entry is readable only once the first response has begun, so calls that start together all pay full price; and the draft call's prompt has a different order and text, so there is no shared prefix to reuse from it. A pre-warm call could cut the repeated input cost, at the price of a serial round trip inside a 10 s budget; it was not measured and is not built.

Validation:
- Every sentence present exactly once; a missing, repeated or unknown number means `not_reviewed`.
- Ids must exist in the source index; evidence must be verbatim, on word boundaries, in a `supported_by` source. Otherwise the record is invalid: it is reported and no issue is derived from it.

Result: `{outcome: clean|issues|not_reviewed, issues, invalid, records, groups, model, input_tokens, output_tokens}`.

**Results of the 6a-4 live check (2026-10-09), and what was decided.** No more review tuning.
- Cases: seven of eight pass (the conformal case fails 0/3 on a reworded phrase reported as a changed detail). Drafts: all three known problems caught. Wall time: 10.4 s and 11.2 s with groups of five and six sentences; about $0.06 to $0.08 per full-post review.
- Measured: 55 to 63 output tokens a second; 105 output tokens per sentence on average, 143 in the heaviest group. From this: `SENTENCES_PER_GROUP` = 4 and `_TOKENS_PER_RECORD` = 150.
- **Decision (2026-10-09): `changed_detail` and `ai_rhythm` are RECORD-ONLY in B.** They are derived and stored in the trace, and they never trigger a redraft. Evidence from the 6a-4 run: `changed_detail` was right on 3 of 12, arguable on 3, and wrong on 6 (synonyms, rewordings, punctuation); `ai_rhythm` was 9 of the 18 issues on the two drafts, mostly judgement calls.
- **Acting types in B** (these trigger the one redraft): `not_in_sources`, `wrong_citation`, `wrong_attribution`, `cross_source_link`, `off_topic`. The redraft's fixed instruction table (step 6b) is keyed by these five, plus the deterministic check types.
- Revisit after the ablation, with a stronger review model.

**Development set and test set.** `evals/fixtures/review_cases.jsonl` is the DEVELOPMENT set for the review. No new cases are added to it for tuning. The ablation's labelled posts (the judge audit and the blind read) become the held-out test set and are never used for tuning.

Bar for 6a-4: all eight cases pass in at least 2 of 3 runs; all three known problems are caught on the saved drafts ("That part stings a little, still.", "All nine felt necessary when we built them.", "Most product teams skip straight from..."); a full-post review takes at most 10 s wall time.

Topic fit of a story's event is `off_topic`, judged semantically from the topic and the cited note (the founder-06 case). Never by keyword matching.

**Fact checking.** The structured review replaces the background fact checker under B. During the ablation the old background check keeps running on all three variants as a measuring instrument only, labelled "low precision, not decisive". Its 2026-10-08 run flagged 41 sentences on 18 of 20 posts.

**Review regression cases** (go in `evals/fixtures/review_cases.jsonl`, run against the real prompt; pytest only uses fakes):

Must NOT be flagged:
- "Average revenue per account fell 4 percent." Source: "Results: conversion improved from 13 to 16 percent; average revenue per account fell 4 percent; shared logins…"
- "At my first company we never did the maths." Source: "Why it matters to me: at my first company we never did the maths and raised in a panic."
- "What didn't help: productivity apps." Source: "What did not help: productivity apps."
- A sentence beginning "One thing worth flagging separately, because it is not something we implemented…" about conformal prediction, with learning notes describing conformal prediction theory. The post disclaims implementing it, so it is not an invented event.

MUST be flagged:
- "My first board meetings at Saltmarsh Labs were me presenting slides for an hour." Source: "Early meetings were me presenting slides for an hour." ("early" changed to "first".)

Also add the recorded regressions from "Why this branch exists" (critic and humanizer inventions, the founder-06 off-topic event).

From the step 3 live check (variant C; eval traces `4baf807f-2600-45e9-b2a3-f53f3b949238` for pm-01 and `761234eb-4afc-4038-aef6-aa2a38413076` for pm-09). MUST be flagged; add them to `evals/fixtures/review_cases.jsonl` when that file is created in step 7, and use them when building the review in step 6:
- pm-01: "That part stings a little, still." (`invented_reaction`; cited to S1, which states no such reaction)
- pm-01: "All nine felt necessary when we built them." (`unsupported_by_citation`)
- pm-09: "Most product teams skip straight from..." (`unsupported_generalisation`)
- pm-09: "Watch for the moment your team says 'let's just build it.'" (unsupported or invented)

## 6. Redraft and failure behaviour

- **Trigger:** an acting issue: any deterministic check issue (over-length counts), or a review issue of type `not_in_sources`, `wrong_citation`, `wrong_attribution`, `cross_source_link` or `off_topic`. `changed_detail` and `ai_rhythm` are record-only (section 5, decision of 2026-10-09). Under-length never acts (decision 6). When the review is `not_reviewed`, the deterministic issues still act.
- **Targeted fixes instead of a whole-post redraft (step 6c, decided 2026-10-10).** Reason, from the 6b live check: the whole-post redraft changed sentences nobody flagged (pm-01), reworded a sentence it was told to leave out (pm-09), and cost a full draft call plus a re-review. In order:
  1. **Code fixes, no model.** A whole sentence that nothing states (`not_in_sources` with no `unsupported_part`) is deleted, with the trim's sentence-deletion code. A `wrong_citation` gets its marker replaced with the supporting ids from the review record; the words do not change. Each is recorded in the trace (`review.fixes.code`: type, sentence, before, after). The post is then checked again in code.
  2. **Routing rule** (`pipeline.fixes.choose_route`), on what is left: an issue about the whole post (`event_unverified`, or `over_length` that the deletions did not fix) → the one full redraft, which gets every remaining issue; otherwise, a sentence still has an issue → the targeted fix; otherwise no model call. Never both, never a third draft: the graph has no edge between the two paths or back to a drafter call.
  3. **Targeted fix (one drafter call).** For `not_in_sources` with an `unsupported_part`, `wrong_attribution`, `cross_source_link`, `off_topic`, and the check types that need new wording (`uncited_span` the review found no source for, `specific_not_in_cited_source`, `view_contains_specific`, `mixed_authorship_span`, `banned_text`, `citation_unknown_id`, a leftover marker). The drafter sees the draft prompt, the post as numbered sentences with markers, and the problems; it returns `<fix sentence="N">…</fix>` or `<fix sentence="N" delete="true"/>` inside `<fixes>`. Code accepts a fix only for a flagged sentence, given once, with valid markers, and splices it in. Unflagged sentences cannot change. An invalid fix leaves its sentence and its issue, recorded.
  4. **Full redraft** as in 6b, on the post as the code fixes left it: General structure for `event_unverified`; trim still runs after it when the post is over.
- **Problems shown to the model (decision 2):** one entry per issue: the type's fixed instruction and labelled quoted material (source ids, `evidence`, `unsupported_part`, the specific and `found_in`, counts computed in code). One table, `pipeline.redraft.REDRAFT_RULES`; a type with no row must be in `RECORD_ONLY` or the run fails. No model-written prose reaches the drafter. The table is in PROMPTS.md.
- **Event failure:** code sets the structure to `general` for the full redraft and records `downgraded_from`.
- **Never a third draft.**
- **Second review:** after code fixes or a targeted fix, only the sentences a model replaced are reviewed; every other sentence keeps its first-review record (also one whose marker alone changed: the reviewer never sees citations), and the issues are derived again in code. After a full redraft, sentences are matched by text and citation as in 6b. The trace records `reused` and `reviewed`.
- **Removed content (for `feat/ask-author`):** `review.removed` lists what was taken out because nothing states it, by the kind the review gave the sentence, with the text.
- **Feelings and motives are facts (step 6d, decided 2026-10-10).** The CITATION RULES block gains: "A feeling, reaction, memory, past belief or motive of the author or of anyone else is a fact about that person. Cite the source that states it. If no source states it, leave it out. Never mark it [[V]]." Reason, from the 6b and 6c live checks: the drafter wrote unsupported reactions as `[[V]]` ("That part stung a little, honestly."), the review flagged each as `not_in_sources`, and code then deleted them, leaving a thinner post. **This applies to C too**: C uses the same draft prompt, so B against C still isolates the value of the checks, the review and the fixes. Pipeline A's prompts are unchanged.
- **A whole sentence named as the unsupported part (6d):** when the review gives `unsupported_part` equal to the sentence (`utils.wording.same_sentence`: case, spacing, punctuation at the ends), code deletes it like any other whole-sentence `not_in_sources`. The pm-09 case: "There's a framework that tries to stop that."
- **No repair of the sentence after a deletion (decided 2026-10-10, step 6e).** Step 6d sent the sentence after each run of code-deleted sentences to the targeted fix as an `after_deletion` repair. It is removed. Evidence, the 6d live check (traces `cdaae72c-5282-4f9d-a600-3ba2f84eb04c` for pm-01 and `55fe6f1d-7be6-41da-8cf8-91cf56e05cdb` for pm-09): none of the five neighbours on pm-01 needed repair, and the model rewrote four of them, adding unsupported words ("So we cut.", "and the numbers confirmed it"), duplicating a sentence, and creating a new dangling reference ("That sentence came up…"); the outcome went from `fixed` to `issues_remain`. Occasional orphans after code deletions are accepted and will be measured in the blind read. Kept from 6d: the feelings citation rule, code deletion when the unsupported part is the whole sentence, and "a replacement identical to the sentence counts as unchanged".
- **Length is the post's prose in B and C (step 6e).** `utils.citations.prose_word_count` counts the words of the post's spans, so headings, `[DIAGRAM: …]` and `[IMAGE: …]` lines and code blocks are not counted. It is used for the validation record, `over_length` and `under_length`, and the trim. Reason: in the 6d live check pm-09's draft was 239 words including a 52-word DIAGRAM line against a maximum of 180; that line alone sent the post into the full redraft and the trim, which cut real sentences and kept the placeholder. Pipeline A keeps `count_words` (every token), so A's behaviour and snapshot are unchanged; the ablation's length figures for A and for B/C are therefore measured differently for posts with placeholders or headings.
- **Code fixes run again after a full redraft's review (step 6e).** The same two fixes (delete a sentence nothing states, replace a wrong marker), on the redraft, recorded in `review.fixes_after_redraft`. Reason: in the 6d live check the redraft reverted a marker code had corrected. No model call is added (the review's issues are derived again from the records it already holds) and there is never a third draft.
- **`off_topic` (recorded 2026-10-10):** it raised one likely false positive in the 6c live check, a closing question to the reader in pm-09 ("What's the version of this problem you're solving for right now?"). It stays acting. Watch its rate in the ablation.
- As built, to confirm: an acting issue about no one sentence that is not structural (a word to avoid in a heading, a placeholder line in a first post) cannot be reached by a targeted fix and is not grounds for a full redraft; it stays on the post and is reported (`review.fixes.unplaced`).
- As built, to confirm: a draft with no `<post>` tag at all is not thrown away; everything outside `<event>` is taken as the post and `draft_format` records `post_tag_missing`.
- **Outcome**, recorded in the trace and returned. It describes the post that is returned (decided 2026-10-10); "issue" means acting issue:
  - `clean`: no issue on the first draft (no redraft).
  - `fixed`: issues on the first draft, none on the returned post.
  - `issues_remain`: issues on the returned post. The post is returned with them listed.
  - `not_reviewed`: some sentence of the returned post has no valid review record: its review failed, or that sentence's record failed validation. Never treated as clean or fixed. A first review that failed does not make the outcome `not_reviewed` when a deterministic issue caused a redraft and the second review covered every sentence; the outcome is then that review's. The trace names the sentences (`review.unreviewed`). A sentence without a valid record is sent again on the second review, never reused.
  - "The returned post" is the post after any trim: a redraft still over length and then trimmed to fit is `fixed`, and an issue (or a missing record) on a sentence the trim deleted does not count. `review.second` in the trace holds the redraft's issues before the trim.
  - **A redraft cut off at its output limit does not discard the first draft** (decided 2026-10-10). The first draft is returned, trimmed first if over length, with the outcome its own issues give (normally `issues_remain`); the trace records `review.redraft_truncated`. `draft_truncated` (no post) is only for a cut-off first draft.
- **Trim (decision 3; superseded 2026-10-10 by compress, below):** ran only when the post was over the maximum. One Haiku structured call picks the indices of spans to delete; code deletes them and re-measures. If it is still over, the trace records `trim_failed` with the counts. Nothing ever expands. A first post (70–100 words) is trimmed if over and never expanded.
- **Compress replaces the trim (decided 2026-10-10, `fix/shorten-not-trim`).** Evidence: production trace `fb714878-24d2-43ba-a518-887e1fc149a8`. The draft said "The opposing case sounds reasonable." … [the opposing argument] … "I don't buy it."; to remove 13 words the ranked-deletion trim deleted both framing sentences and "Now the fair part.", so the returned post recommended the position its author argued against. Reason: deleting sentences cannot preserve meaning (short framing sentences are exactly the ones a ranking finds cheapest), and a whole-post rewrite re-generates text non-deterministically, which is what this branch removed (the pm-01 and pm-09 redrafts, above). Compression is bounded by code checks instead:
  1. **One call**, for every single-writer variant (C, C-Opus, B, B-Opus), only when the finalised post is over its maximum by `prose_word_count`: the run's draft model at the draft's effort and budget (`agents/compress_agent.py`, prompt in `agents/compress_prompt.py`). It sees the delimited sources block with the data-not-instructions rule, the post as numbered sentences with their lengths and markers, the limit and the excess, and returns one shorter replacement per sentence it changes. One logical compress call per post; identical transport retries per the shared client policy are allowed; never a second compression of the same post.
  2. **Code validates each replacement** (`pipeline/compress.py`) and keeps the original sentence, recording the reason, unless: the number is one of the post's sentences and is given once; the replacement is not empty and not a deletion; it is one sentence; it carries exactly the sentence's marker; it begins with the sentence's list marker when the sentence has one (`list_marker_lost`, added 2026-10-10 after review); it has fewer words; and `extract_specifics(replacement)` is a subset of `extract_specifics(sentence)`. After each proposed acceptance, code re-segments the full candidate with the same splitter and rejects changed sentence counts or positions (`changes_sentence_boundaries`). Code splices the accepted ones; every other character of the post is unchanged and no sentence is deleted, merged, added or moved.
  3. Then finalise and the deterministic checks again, as after any change. The trace records `compress_result` (`words_before`, `words_after`, `outcome`, `accepted`, `rejected` with reasons, `stop_reason`, `model`), and usage is logged with the exact model id.
  4. **Failures are explicit.** A refused, cut-off, empty or malformed reply: outcome `compress_failed` with the reason, and the unshortened post is returned. Still over after the accepted replacements: outcome `still_over`, and the shorter post is returned. Either way `final_validation` and `checks_final` say `over_length`.
  5. `agents/trim_agent.py` is unwired from every variant and left in place, labelled unused, until `chore/remove-pipeline-a`.
  - **STOPGAPS, labelled in `pipeline/compress.py`:** structural checks do not verify semantic equivalence, so stance, names and events can change; money amounts omit currency identity. Proper fixes: per-replacement semantic verification in `eval/faithfulness-judge`, and structured money extraction (amount + currency) in planned specifics work.
  - One logical compress call per post; identical transport retries per the shared client policy are allowed; never a second compression of the same post. SDK response-validation errors return the unshortened post with `compress_failed`, reason `response_invalid`; unexpected exceptions propagate.
  - Known limits, accepted: `extract_specifics` sees numbers, dates and time references, not names, so nothing in code stops a replacement from adding a name (the prompt forbids it and the marker cannot change); "one sentence" is the segmenter's judgement; under B a sentence compress shortened keeps the review record of its longer wording and is not reviewed again; the call costs a draft-model call where the trim cost a Haiku call.
- **Final validation:** `finalise` runs after every content-changing step, including em-dash normalisation. The returned string is the last validated string.
- **Pipeline A (decision 4):** `finalise` and final validation run on A in record-only mode, so the ablation can report A's length violations. A's output and behaviour do not change.
- **What the user sees:** status stays `ok`. `GenerateResponse` gains `review: {outcome, issues: [{type, sentence_text}]}`, acting types only (built in step 6b; `null` when no review ran). On `issues_remain` the Create page shows a notice in the style of `LowCoverageNotice`: "N sentences couldn't be checked against your sources", listing them. Nothing is silently removed.

## 7. Ablation harness

Three variants, selected by one configuration value, not by copying code (a fourth, B-Opus, is B with a different drafter model; see "Models and the model ablation" below):
- **A:** current pipeline (draft → critic → humanizer → audit → enforcer)
- **B:** single writer (draft → checks → at most one redraft → trim)
- **C:** draft only (draft → trim)

**Configuration (done in step 1):**
- `PIPELINE_VARIANT` env var, read by `pipeline_variant()` in `backend/config/features.py`. Unset or empty means the default, which was A during the ablation and is C-Opus since 2026-10-10.
- Matching is exact: `A`, `B` or `C`. Anything else raises `PipelineConfigError`, and the server refuses to start.
- `run_pipeline(..., variant=None)` lets evals override it. It is not a `/generate` request field.
- Production: the variable is unset, so it runs the default (C-Opus since 2026-10-10). Set `PIPELINE_VARIANT=A` on Railway to roll back.

**Runner:** `run.py --variant A|B|C` writes the variant to `meta.json` and the run id.

**Report:** `report.py --variants <runA> <runB> <runC>` writes `ablation.md` with, per variant:
- invented specifics: `unsupported_specifics` from the Sonnet judge
- topic adherence: answer relevancy
- wall time p50 and p90
- cost and Claude calls per post
- redraft rate, review outcomes, trim failures, final length violations
- fact-check flag counts, labelled "low precision, not decisive"

**Judge audit:** `evals/blind.py audit` writes 10 sampled `unsupported_specifics` findings (lowest scores first, then random) with the post, the sources and the judge's reasoning. Soham marks each correct or not. Below 8 of 10, the report labels the metric unreliable.

**Blind read:** `blind.py make` picks 10 goldens and writes `read.md`. Each golden shows its four posts (A, B, C, B-Opus) in seeded shuffled order as W, X, Y and Z, with `ranking[<golden>]:` and `note[<golden>]:` lines to fill in (as built in step 7). The key goes to `key.json`. `blind.py score` joins them and prints preferences per variant.

**Decision metrics:** invented specifics, topic adherence, latency, cost per post, and Soham's blind read for voice.

### Models and the model ablation (added 2026-10-09; implement in step 7)

Soham's explicit instruction to add models (CLAUDE.md otherwise forbids changing or adding them).

1. **Models per role, one place.** Config values, not scattered strings:
   - `DRAFT_MODEL`: the drafter and the redraft.
   - `REVIEW_MODEL`: the structured review.
   - `SMALL_MODEL`: structure choice and trim.
   - Pipeline A keeps its current models (`SONNET`, `HAIKU` in `llm/client.py`) unchanged.
2. **Variant B-Opus.** B with `DRAFT_MODEL` = Claude Opus 5.5 and everything else as B. Reported alongside A, B and C in `ablation.md`, and included in the blind read: 4 posts per golden, shuffled.
3. **Small-model check, smoke set only.** A B run with `SMALL_MODEL` = Claude Haiku 5.5 against the current Haiku 4.5, reported separately, to check that structure choice and trim quality hold before switching.
4. **Draft token budget per model family.** `TOKENS_PER_WORD` becomes one named constant per model family, each measured from the ablation's drafts for that model (output tokens ÷ words of the marked draft), with the measurement as its stated reason. Claude 4.7 and later models use a newer tokenizer that produces up to about 35% more tokens for the same text.
5. **Model ids: look them up, don't guess.** Confirm the exact id strings for Opus 5.5, Sonnet 5.5 and Haiku 5.5 against the Anthropic docs (or the Models API) before using them. For reference only, the claude-api skill's cached table (2026-10-06) lists `claude-opus-5-5`, `claude-sonnet-5-5` and `claude-haiku-5-5`, with no date suffix.
6. **One pricing table, and cost per post per variant from it.** One module holds the prices, keyed by exact model id, with the prices taken from the Anthropic pricing page and the date they were checked. `backend/memory/usage_store.py` and the eval code both import it; neither keeps its own numbers. In step 7, report which value was right for the model actually in use (see the disagreement below): production cost tracking may be undercounting Haiku.

Things step 7 has to handle, from the same reference (confirm each against the docs before building on it):
- **Thinking is always on for Opus 5.5** and cannot be disabled; depth is set with `output_config.effort`, whose default on Opus 5.5 is `medium`. Thinking tokens count against `max_tokens`, so the draft budget for Opus 5.5 needs room for them, not only for the post.
- **The reply starts with thinking blocks.** `cited_draft_node` reads `message.content[0].text`; with thinking on, the first block is not text. Read the text blocks by type.
- **Forced tool choice returns a 400 on Opus 5.5 and Sonnet 5.5.** `complete_structured` forces the tool. It is not used by the drafter, so B-Opus is unaffected, but `REVIEW_MODEL` or `SMALL_MODEL` on a 5.5 model would need `tool_choice: auto` with `strict: true`, or structured outputs. Check Haiku 5.5 before the small-model run.
- **A `refusal` stop reason** is possible on the 5.5 models; treat it like `draft_truncated`: an explicit status, never a post.
- **`complete()` rejects unknown models** (`_USAGE_LABELS`), and `memory/usage_store.py` prices by label. Both need the new models.
- **Two price tables disagree today.** `evals/eval_config.py` prices Haiku at $1 / $5 per million tokens; `backend/memory/usage_store.py` prices it at $0.25 / $1.25, for the same model (`claude-haiku-4-5-20251001`). Item 6 replaces both with the one shared table.
- Cached list prices for the estimate (per million tokens, input / output): Opus 5.5 $4 / $20, Sonnet 5.5 $2 / $10, Haiku 5.5 $0.10 / $0.50, Sonnet 4.6 $3 / $15, Haiku 4.5 $1 / $5. Confirm before the run.

## 8. Cost and time

Of 27 goldens, 7 are gated before drafting, so 20 posts per variant. B and C figures are estimates.

| | Per post | 20 posts | Wall time per post |
|---|---|---|---|
| A (measured) | ~$0.04 | ~$0.85 | 36–42 s |
| B (estimate, Sonnet review) | ~$0.035 clean, ~$0.07 with redraft | ~$1.00 | ~17 s clean, ~32 s with redraft |
| C (estimate) | ~$0.02 | ~$0.45 | ~13 s |

- **Calls:** A about 150 pipeline calls, B about 60–100, C about 40–45, plus 60 background fact checks (about $0.25).
- **Judging:** 60 posts at roughly $0.04 (Haiku, four metrics) plus roughly $0.03 (Sonnet `unsupported_specifics`) is about $4.
- **Full run:** about $7–9 and about an hour.
- **If variants land close:** run a second repetition (about double the cost). One sample per golden is noisy.
- B's clear win is latency. It may not be cheaper than A if the redraft rate is high.

**Smoke run** (6 goldens × 3 variants, Sonnet `unsupported_specifics` only; about $1.50 and 15 minutes).

Proposed set, to be confirmed with Soham before running (decision 8):

| Golden | Why |
|---|---|
| pm-05 | required; mixed, sparse, concise |
| founder-06 | required; the off-topic event case |
| ds-09 | required; mixed, one external article ("the article" credit case) |
| pm-09 | external only (`expected_perspective: learned`), concise |
| founder-09 | external only (`expected_perspective: learned`), standard |
| ds-01 | rich, mixed, 4 of 8 chunks self-authored: cross-source and story-event checks |

Gap: no experience-only golden is in this set (candidates: pm-01, founder-05). Goldens never exercise first posts, because evals seed posts; only pytest covers the 70–100 target.

## 9. Files

**Change**
- `backend/pipeline/graph.py`, `pipeline/state.py`, `pipeline/trace.py`
- `backend/agents/draft_agent.py`, `agents/archetype_agent.py`, `agents/word_count_enforcer_agent.py` (adds trim-by-deletion)
- `backend/utils/formatters.py` (style rules and banned table), `utils/frames.py` (delimited sources builder), `utils/sentences.py`
- `backend/config/features.py`, `backend/routers/generate.py`
- `evals/run.py`, `evals/reporting.py`, `evals/report.py`
- `CODEBASE.md`, `PROMPTS.md`

**Create**
- `backend/utils/citations.py`: marker grammar, strip, spans.
- `backend/pipeline/checks.py`: deterministic checks.
- `backend/agents/review_agent.py`: structured review.
- `backend/agents/draft_prompt.py`: prompt assembly. `draft_agent.py` is 254 lines and would pass 400 with the citation, style and redraft blocks.
- `evals/blind.py`, `evals/fixtures/review_cases.jsonl`, `evals/review_cases.py`.
- Test files for section 10.
- `frontend/components/ReviewNotice.tsx` (step 9).

**Unused under B** (deleted on `chore/remove-pipeline-a` after the ablation decision, never on this branch; A must keep running unchanged):
- `agents/critic_agent.py`, `agents/humanizer_agent.py`, `agents/predictability_audit_agent.py`
- `agents/fact_check_agent.py`, `config/fact_check.py`
- the enforcer's expand path, the scorer retry loop, the archetype event fields
- the guard retry helpers in `utils/specifics.py` (`retry_note`, `guard_entry`, `remove_sentences`)

Keep source files under about 400 lines and functions under about 80.

## 10. Tests

Tests check behaviour, not prompt wording.

- **Citations:** strip returns clean text and correct spans; markers inside code are untouched; malformed and leftover markers fail.
- **Checks:**
  - A number in the cited chunk passes ("fell 4 percent").
  - A number only in another chunk is flagged and names that chunk.
  - An unknown id and an uncited span are flagged.
  - A mixed-authorship span is flagged.
  - An event quote that is not verbatim, or that cites an external chunk, is flagged.
- **Review plumbing:** an out-of-range span, an unknown id and non-verbatim evidence are recorded as invalid and never reach the redraft; a failed call gives `not_reviewed`.
- **Pipeline B:**
  - Clean draft: 3 calls.
  - Issues, then clean: exactly one redraft, outcome `fixed`.
  - Issues twice: no third draft, outcome `issues_remain` in the trace and the response.
  - The redraft prompt contains no `why` text.
  - `quality="draft"` runs no review and no redraft; `quality="polished"` runs no scorer.
- **Pipeline C:** no review call and no redraft.
- **Length:**
  - A 100-word first post containing `word—word` is validated after normalisation.
  - Over-length is trimmed by deletion.
  - Still over records `trim_failed`.
  - Under-length adds no call, triggers no redraft, and is recorded as `under_length`.
  - The returned post equals the last validated text.
- **Variants (done in step 1):** default is A; an unknown value refuses to start; the trace records the variant. Still to add: A's Claude call sequence is unchanged once B and C diverge.
- **Injection:** a source containing a fake closing tag or marker cannot create a citation or close the block.
- **Existing suites** for perspective, archetype gating, the `general` fallback and writing samples keep passing unmodified under A.

## 11. Order of work

Each step ends with a diff and a `pytest` run.

1. **Done.** Variant config and `build_graph(variant)`; B and C wired as A for now.
   - `config/features.py`: `PIPELINE_VARIANTS`, `pipeline_variant()`, `validate_pipeline_variant()`, `PipelineConfigError`.
   - `pipeline/graph.py`: `_wire_rewrite_chain`, the `_AFTER_DRAFT` table, `PIPELINES` (one compiled graph per variant), `run_pipeline(variant=None)`.
   - `variant` is in the state and in `node_outputs`.
   - `main.py` logs the variant at startup; `tests/conftest.py` clears `PIPELINE_VARIANT`.
   - 19 new tests in `tests/test_pipeline_routing.py`; 594 pass.
2. **Done.** `utils/citations.py` (markers, `strip_citations`, `leftover_markers`, `escape_markers`, `source_id`) and `build_sources_block` in `utils/frames.py` (index entries are `{position, chunk_id, frame, authorship}`; a missing `source_type` is shown as `unknown`).
3. **Done.** Draft prompt split and the single-writer drafter.
   - `agents/draft_prompt.py`: `build_prompt` (A, unchanged text) and `build_cited_prompt` (B and C), from shared blocks.
   - `STYLE_RULES` in `utils/formatters.py`: the one copy, read by A's humanizer and the cited prompt.
   - `agents/draft_agent.py`: `structure_node`, `cited_draft_node` (one call, no guard retry).
   - `agents/archetype_agent.py`: `choose_structure` (key only).
   - `utils/citations.py`: `parse_event_header`.
   - `pipeline/graph.py`: `_AFTER_PLAN`; B and C run structure → draft → strip → end (`strip_draft_node`).
   - Trace: `source_index`, `event`, `citations`, `citation_failures`; the marked draft is the `draft` entry in `draft_history`.
   - `tests/test_pipeline_a_snapshot.py` freezes A's archetype, draft, critic and humanizer requests against main.
   - Citation rule as written in the prompt: every sentence ends with one marker, and every line of prose ends with a marker.
4. **Done.** `finalise`, trim by deletion, truncated drafts, record-only validation on A.
   - `pipeline/finalise.py`: `finalise`, `finalise_marked`, `validation_record`, and the nodes `strip_draft_node` (EVENT line), `finalise_draft_node` (markers), `finalise_trimmed_node`, `truncated_node`.
   - B and C: draft → strip → finalise → trim (only when over the maximum) → finalise → end. Under-length is `final_validation.length == "under_length"` with `under_by`; it triggers no call.
   - `trim_node` (now in `agents/trim_agent.py`; `structure_node` is in `agents/archetype_agent.py`): one Haiku structured call returns span numbers; `utils.citations.delete_spans` deletes. `trim_result` records outcome, reason, counts and the deleted spans. `still_over` keeps the shorter post; any unusable answer leaves the post untrimmed.
   - A draft with `stop_reason == "max_tokens"` sets `draft_truncated`; `run_pipeline` returns `status: "draft_truncated"`, `post: ""` and a message. The Create page does not handle this status yet (step 9).
   - Draft budget: `draft_max_tokens(target)` = max words × `TOKENS_PER_WORD` (1.9) × `DRAFT_TOKEN_MARGIN` (1.25), never below 2000. Medium long-form (1800 words) gets 4275, under the 16,000 non-streaming ceiling (`llm.client.MAX_NON_STREAMING_OUTPUT_TOKENS`); Sonnet 4.6's own cap is 128,000.
   - Pipeline A: `finalize_node` stores `final_validation`, record only. Snapshot test still passes.
   - **Step 4b, done.** Trim works in sentences: `utils.sentences.split_spans` cuts each span into sentences (pysbd; code and URLs never split; a sentence inherits its span's citation), the trim call returns sentence numbers, and a span's kept sentences stay one span. `multi_sentence_spans` (spans holding more than one sentence) is recorded per draft as a citation-compliance metric and triggers nothing. Reason: the pm-09 draft had one marker per paragraph, so deleting whole spans removed 15 words for a 7-word excess and orphaned the next sentence.
   - **Step 4c, done.** The trim call returns a ranking (most expendable first), not a set. Code deletes in ranked order, re-counts after each sentence and stops as soon as the post fits; ranked sentences that were not needed are kept. A ranking with repeats is rejected. `trim_result` records `ranking`, `deleted` and `kept_ranked`. Reason: on pm-09 the set-based trim deleted 19 words for a 7-word excess.
5. **Done.** Deterministic checks in `pipeline/checks.py`, recorded only.
   - Issue types: `citation_malformed`, `citation_unknown_id`, `uncited_span`, `specific_not_in_cited_source`, `view_contains_specific`, `event_unverified`, `mixed_authorship_span`, `over_length`, `banned_text`. Each issue is `{type, span, text, sources, detail}`.
   - B and C: draft → strip → finalise → checks → trim (if over) → finalise → checks again → end. Trace: `checks_before_trim` and `checks_final` (`{issues, counts}`; identical when no trim ran). A runs no checks.
   - `event_quote_failure` moved to `utils/sentences.py`; A and the checks share it.
   - `banned_text` covers only what can be matched exactly: an em dash outside protected spans, the profile's own `words_to_avoid` (user data), and placeholders in a first post. There is no banned-phrase list (decided 2026-10-09, see section 4).
   - Fixed along the way: `strip_citations` silently dropped a marker standing alone on the last line after a line break; it is now reported as `empty_span`.
6. Review agent, redraft, outcomes, trace fields, response field, quality handling under B. Shows: pipeline B tests.
   - **Step 6a, built (fourth and last design, 6a-4; see section 5).** `agents/review_agent.py`, `review_post(state)` (prompt in `agents/review_prompt.py`): the review alone, not wired in. `evals/fixtures/review_cases.jsonl` has eight cases, each listing the types that `must` be raised and those that `must_not` be; any other type raised is reported as "other" for a human to judge. `wrong_attribution` has no exception for first-person text in an external source. Persona notes the author wrote in the first person but that are stored with external frames (founder `08-default-alive`: learning; founder `04-burnout-month`: observation; ds `04-conformal-prediction-notes` and pm `06-opportunity-solution-trees`: learning notes that mix theory with the author's own remarks) are an authorship-classification problem for `fix/ingest-attribution` (I1), not a reviewer problem; the persona data is not changed on this branch.
   - **Step 6b, applied 2026-10-10.** B and C are now different pipelines.
     - `pipeline/single_writer.py`: `wire_draft_only` (C, unchanged behaviour) and `wire_reviewed` (B). `pipeline/graph.py` keeps the shared nodes, A's chain and `run_pipeline`.
     - `pipeline/redraft.py`: `REDRAFT_RULES` (the one instruction table; a row means the type acts), `RECORD_ONLY`, `split_issues`, `issue_entries`, `decide_node`, `apply_downgrade`, `outcome_node`, `review_summary`. `pipeline/review_validation.py`: the record validation, moved out of `review_agent.py` unchanged.
     - `agents/draft_agent.redraft_node` and `agents/draft_prompt.build_redraft_prompt`; `agents/review_agent.review_node` / `review_redraft_node`, and `review_post(state, previous=...)` for the reuse of unchanged sentences. The review prompt's assignment line lists the numbers when they are not consecutive; a first review's prompt is unchanged.
     - `event_unverified` on a story redrafts to the General structure and records `downgraded_from`.
     - Quality: `draft` under B takes C's path after the first checks; `polished` is standard B. `scored` is true only under A.
     - Trace: `review_first`, `review_second`, `review` (`first`, `redraft.entries`, `second`, `remaining`, `outcome`), `step_timings`; the redraft's tokens are in `review.redraft`, each review's in its result.
     - Response: `GenerateResponse.review`.
     - Tests: `tests/test_pipeline_b.py`, `tests/test_redraft.py`; the older B-and-C tests now run C and B at `quality="draft"`.
   - **Step 6c, built 2026-10-10.** Output envelope, code fixes, targeted fix, routing rule, removed-content record (see sections 3 and 6).
     - `utils/draft_output.py`: `parse_draft_output` (replaces `parse_event_header`) and `parse_fixes`. `utils/citations.py`: `marker`, `with_markers`, `replace_span`.
     - `pipeline/fixes.py`: `code_fix_node`, `choose_route`, `apply_targeted_fixes`. `pipeline/redraft.py`: rules gain `scope`; `wrong_citation` has no instruction (always fixed in code).
     - `agents/redraft_prompt.py`: `build_fix_prompt`, `build_redraft_prompt` (moved from `draft_prompt.py`). `agents/draft_agent.py`: `targeted_fix_node`. `agents/review_agent.py`: `review_fixed_node`, `review_post(origin=...)`.
     - Tests: `tests/test_draft_output.py`, `tests/test_fixes.py`; `tests/test_pipeline_b.py` and `tests/test_redraft.py` rewritten for the three paths.
   - **Step 6d, built 2026-10-10.** The feelings-are-facts citation rule (B and C), code deletion when the unsupported part is the whole sentence, the `after_deletion` repair (removed again in 6e), and `tests/test_single_writer_draft.py` split (`tests/test_strip_envelope.py`). See section 6.
   - **Step 6e, built 2026-10-10.** The `after_deletion` repair removed; `prose_word_count` for B and C; `code_fix_redraft_node` and `review_refixed_node`. `tests/test_pipeline_b.py` split (`tests/test_full_redraft.py`). No live check: the next evidence is the step 7 ablation.
7. Eval harness: `--variant`, the ablation report, `blind.py`, the review regression set. Report input and output tokens per post per variant (A, B, C, B-Opus). Also the model work in "Models and the model ablation" (section 7): per-role model config, variant B-Opus, the Haiku 5.5 small-model check on the smoke set, per-model-family `TOKENS_PER_WORD`, model ids confirmed from the docs, one pricing table. Add `PIPELINE_VARIANT` to the eval guard's backend env var list (`BACKEND_ENV_KEYS` in `evals/guard.py`). Then, when Soham says so: the regression set (Sonnet, and Haiku if cheap) and the smoke run.
   - **Built 2026-10-10.**
     - Models: `llm/models.py` (ids, `ModelSpec`, `DRAFT_MODEL` / `REVIEW_MODEL` / `SMALL_MODEL`, `VARIANT_ROLE_MODELS`), `llm/pricing.py` (the one price table). `PIPELINE_VARIANTS` gains `B-Opus` (`VARIANT_GRAPH` runs it on B's graph). Ids, prices and the four 5.5 call differences were confirmed in the Anthropic docs on 2026-10-10.
     - 5.5 handling: `message_text` (text blocks by type), `output_budget` (thinking room), `complete_structured` with `tool_choice: auto` plus an instruction where a tool cannot be forced, `draft_refused` / `redraft_refused` / `RefusedStructuredOutputError`.
     - `TOKENS_PER_WORD` is per tokenizer. **Step 7b (2026-10-10), from the smoke:** the Claude 4.7 value is 2.4 (six Opus 5.5 drafts: 1.94 to 2.36, mean 2.18) and `THINKING_ALLOWANCE_TOKENS` is 3,000 (nine Opus 5.5 drafts at effort medium: 711 to 1,499 thinking tokens; twice the largest). Sonnet 4.6 measured 1.35 to 1.71 on twelve drafts, under its 1.9. Re-measure all three on the full ablation.
     - **Step 7b:** on `anthropic` 1.13.0 the code reads the SDK's typed fields (`ThinkingBlock`, `usage.output_tokens_details.thinking_tokens`, `stop_details`), and an Opus 5.5 draft sends `output_config.effort` = `medium` (the API default, `OPUS_5_5_DRAFT_EFFORT`), recorded in `meta.json` as `draft_effort`. `instrument.py` writes a review that did not happen as `not_reviewed` and retries it.
     - Haiku price: the evals' $1 / $5 was right for `claude-haiku-4-5-20251001`; `usage_store`'s $0.25 / $1.25 was Claude 3 Haiku's, so past production Haiku costs are a quarter of the real figure.
     - Harness: `run.py --variant` / `--model`, `report.py --variants`, `ablation.py`, `instrument.py`, `blind.py` (`audit`, `make`, `score`), `review_regression.py`; `PIPELINE_VARIANT` in the eval guard.
     - Not done: forced tool choice on Haiku 5.5 is accepted per the docs, so the small-model check needs no call-shape change, but it has not been run. (The SDK was `anthropic==0.40.0` when step 7 was built; it is 1.13.0 since the merge of `chore/anthropic-sdk-1x`.)
   - **Full-ablation prep, built 2026-10-10.**
     - Fifth variant `C-Opus`: C with `DRAFT_MODEL` = Opus 5.5 at `OPUS_5_5_DRAFT_EFFORT`, everything else as C. The blind read now shows five posts per golden (labels V, W, X, Y, Z).
     - Judge set for the full run: `unsupported_specifics` (Sonnet) and answer relevancy (Haiku) only.
     - **The instrument is not run in the full ablation.** It reviews every final post with B's own reviewer. B's posts were fixed against exactly that reviewer's findings, so the count favours B by construction and cannot decide between variants (smoke: A 48, C 31, B 9, B-Opus 4 acting issues, which says B does what its reviewer asks, not that its posts are better). The decision rests on the independent judge, the judge audit and the blind read.
     - The review regression set runs once on `REVIEW_MODEL`; it is the development set and not part of the decision.
     - Hard spend cap: `EVAL_SPEND_CAP_USD` (14) in `evals/eval_config.py`. Every script run with `--ablation <name>` adds its measured cost (list prices, `llm/pricing.py`) to `results/ablations/<name>/spend.json` after each post and stops before the next post once the cap is reached. `python ablate.py --name <name>` runs the whole sequence under it.
   - **Full ablation, as decided 2026-10-10 (before the run).**
     - Variants: **A, C, B-Opus, C-Opus**. B is dropped: in the smoke it was the most expensive Sonnet option ($0.145 a post against C's $0.017) with the lowest judge score (0.90, 5 of 6 passing), and what the review is worth is still tested by B-Opus against C-Opus. `EVAL_SPEND_CAP_USD` stays at 14.
     - **Pre-registered decision rules, pinned 2026-10-10 before the run.** The one copy is `eval_config.DECISION_RULES`, `DECISION_TIEBREAK` and `DECISION_NOTE`, printed at the top of `ablation.md`; quoted here:
       1. C-Opus becomes the default if its `unsupported_specifics` pass count is at most 1 below B-Opus AND, in the blind read, B-Opus is ranked above C-Opus in 6 or fewer of the 10 goldens.
       2. B-Opus becomes the default if, in the blind read, it is ranked above C-Opus in 7 or more of the 10 goldens.
       3. A is retired if C or C-Opus is ranked above A in at least 5 of the 10 goldens.
       - Tiebreak if neither 1 nor 2 holds: hand-check C-Opus's judge failures beyond B-Opus's. Failures caused by the known authorship-framing problem (the author's own first-person notes framed as external, I1) are excluded from both variants' pass counts equally. Re-apply rule 1. If it still fails, B-Opus becomes the default ("never invents" outranks cost).
       - "Clearly" means 7 of 10 head to head. This is a practical bar, not a statistical test.
       - Fewer than 10 ranked (`DECISION_FEWER_RANKED`): the blind read uses only goldens for which every variant produced a post, so it has 10 complete goldens. If fewer than 10 are ranked, the thresholds apply as proportions of those ranked: "clearly" (rule 2) is at least 70%, rule 1's limit is at most 60%, rule 3 is at least 50%.
       - Judge audit below the bar (`DECISION_AUDIT_BELOW`): if the judge audit is below 8 of 10, rule 1's judge criterion is dropped: rules 1 and 2 are decided by the blind read alone, and the tiebreak does not apply. `ablation.md` states this when it happens.
       - `blind.py score` prints, for B-Opus vs C-Opus, C vs A and C-Opus vs A, the head-to-head count, its share of the goldens ranked, and whether each rule's condition is met; and the mean ranks.
     - The blind read has 4 posts per golden (A, C, B-Opus, C-Opus), labelled V, W, X, Y.
8. Full ablation, judge audit, blind read. Soham decides.
   - Recompute `TOKENS_PER_WORD` (`utils/formatters.py`) from the ablation's B and C drafts, per model family: output tokens ÷ words of the marked draft. Update each constant and its stated reason; the Sonnet 4.6 value currently rests on one post (pm-01, 419 tokens for 225 words).
   - The blind read has 4 posts per golden (A, C, B-Opus, C-Opus), shuffled.
9. Refine alignment and the frontend `ReviewNotice` (decisions 7 and 9).
   - Selection refine stays a separate writer.
   - It uses the same style constant, the same sources builder, the trace's stored `source_index`, the same markers and checks, and one review call on the rewritten passage.
   - It keeps today's single retry and `reverted` status.

### Decision and result (2026-10-10)

**C-Opus becomes the production default; pipeline A is retired.** Decided by the pre-registered rules on ablation "full" (A, C, B-Opus, C-Opus; 20 posts each; `evals/results/ablations/full/`):
- Blind read, 10 goldens: B-Opus ranked above C-Opus in **0 of 10** (rule 2 not met; rule 1's blind-read condition met). C-Opus ranked above A in **10 of 10**, C above A in 7 of 10 (rule 3 met). C-Opus was ranked first in all 10.
- Judge audit: **3 of 10** findings judged correct. The `unsupported_specifics` judge is unreliable: too lenient. It was right both times it failed a post and wrong seven times it passed one. So rule 1's judge criterion was dropped, the blind read alone decided, and the tiebreak did not apply.
- Judge figures, for the record only: pass counts A 18, C 20, B-Opus 20, C-Opus 20 of 20. Cost per post: A $0.041, C $0.018, B-Opus $0.229, C-Opus $0.055. Wall time p50: A 32.9 s, C 14.3 s, B-Opus 41.4 s, C-Opus 22.1 s.
- Not shown by the ablation: that C-Opus does not invent. The blind read was made without sources, and a later sentence-level read with sources (`faithfulness-read.md`, by Claude, one reader) found unsupported sentences and wrong attributions in both Opus variants, with B-Opus no cleaner and three orphaned sentences left by its deletions.

**Content rule, for later judge and prompt work** (the drafter prompt is NOT changed on this branch):
> Facts about the user, their company, their work, numbers, events, feelings, and what a source says must come from the user's notes; opinion, argument, analogy and takeaways in the author's voice are allowed.

**What the default means in code** (built 2026-10-10): `DEFAULT_PIPELINE_VARIANT = "C-Opus"`; `PIPELINE_VARIANT=A` is the rollback switch until `chore/remove-pipeline-a`; every `quality` value runs C-Opus; the Create and first-post pages show a message for `draft_truncated` and `draft_refused`; selection refine on a single-writer post uses the post's drafter, the stored source index, citation markers and the deterministic checks; the deterministic checks on the draft stay record-only until `feat/citations-ui`; `TOKENS_PER_WORD_CLAUDE_4_7` = 2.5 and `THINKING_ALLOWANCE_TOKENS` = 3,500, from the 40 Opus drafts of the ablation.

After this branch: `fix/retrieval-failure-status` first, then the remaining follow-ups including `chore/remove-pipeline-a` (pipeline A is retired; B's review code goes with it unless kept for `feat/citations-ui`). Before merge: an independent review of `git diff main...HEAD`, a click-through, and a green Vercel build.

## 12. Risks and open items

Risks:
- Markers on every sentence may flatten voice. The blind read of A against B and C shows this.
- The drafter can escape checks by marking claims `[[V]]`. The `claim_marked_as_view` type covers it, but only semantically.
- Reviewer false positives cost a redraft of about 15 s each. The report shows the redraft rate.
- Sonnet reviewing Sonnet shares blind spots, and Sonnet is also the judge. The hand audit is the control.
- One sample per golden is noisy.
- Trim by deletion is coarser than rewording, and a deleted span can orphan the next sentence. (It did worse: it reversed a post's meaning in production. Replaced by compress on 2026-10-10, section 6.)

Streaming is the next branch. Nothing here blocks it:
- Markers strip on the fly.
- The `<event>` part is withheld; the post streams from `<post>`.
- A redraft shows as "checking" and then a replacing stream.
- Compress replaces sentences in place and runs after the draft has streamed, so it shows as a replacing step.

Open items:
- Later: `eval/faithfulness-judge` verifies each compress replacement against its original for stance and unsupported names/events (extra judge latency/cost and semantic false positives to evaluate).
- Later: planned specifics work extracts money as amount + currency, replacing the currency-identity stopgap without growing keyword lists (extraction complexity and locale coverage to evaluate).
- The post-redraft review runs synchronously so the notice is accurate. Running it in the background would save about 5 s on redrafted posts; revisit with the ablation numbers.
- `backend/.env.example` should list `PIPELINE_VARIANT=` (Soham edits env files).

## 13. Stopgaps

Outstanding on this branch:
- `backend/pipeline/graph.py`: variant B's review summary is not shown. Proper fix: `feat/citations-ui` exposes per-sentence citations and recorded results. Explicit no-post statuses and refine alignment are implemented.
- `backend/utils/frames.py` and `backend/agents/draft_prompt.py`: prompt-only faithfulness constraints do not prove attribution or relationships. Proper fix: an independent faithfulness judge plus `feat/citations-ui`; C-Opus records deterministic checks only.
- `backend/utils/formatters.py`: phrase examples are shared with frozen A. Proper fix: a description-based style block on `chore/remove-pipeline-a`.
- `backend/agents/retrieval_agent.py`: fallback-query errors become low coverage and logs include topic/source excerpts. Labels only here; proper fix: `fix/retrieval-failure-status`, first after this merge.

Existing, still in place:
- Source titles are hidden (`backend/utils/frames.py`, `format_chunks_by_frame`). Proper fix: record `title_origin` at ingest (`fix/ingest-attribution`).
- `extract_specifics` currency/time vocabularies are incomplete. Proper fix: structured, locale-aware entity extraction rather than longer phrase lists.
- A's legacy guard, humanizer and fact-check stopgaps remain until `chore/remove-pipeline-a`. Citation markers alone do not resolve semantic faithfulness.

## 14. Independent-review fixes (scratch candidate)

- Empty completed drafts return `draft_empty`, no post and a message, with `empty_output` in the trace.
- Blank cited refine output retries once then explicitly reverts; note-only replies remain intentional. Missing/unknown stored models fail with distinct tracking reason codes. Historical/A refine retains its prompt but handles typed text, refusal and truncation.
- Passage checks include mixed-authorship spans. The single-writer structure call uses escaped sources/data-only instructions; A's snapshots stay frozen. Structure logs contain category/model/request ID, not raw exceptions.
- Usage events persist exact model IDs. Apply nullable-column migration `006_add_usage_model.sql` before deploying; historical model IDs stay NULL. The migration is not run by the agent.
- Onboarding displays coverage-specific explanations, tested through its actual Generate handler and resulting screen.
- Backend, eval and frontend unit tests use fakes; no live eval or external API is run for these fixes.
