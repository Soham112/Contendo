# Generation architecture: Phase 0 report

Spec: [GENERATION_ARCHITECTURE.md](GENERATION_ARCHITECTURE.md). Date: 2026-10-14. Code at `ddb4045` (main).
No feature code in this phase. The instrumentation in section 3 is a proposal, to build only after approval.

## 0. Summary

1. **C-Opus takes about 23 s (p50) and 31 s (p95) end to end, and that was before the grounding gate existed.** The Opus draft call alone is 19 s p50 and 25.5 s p95. About 1,035 of its ~1,870 output tokens are thinking, generated at ~99 tokens/s before any post text, so time to first text is about 10 s even with streaming.
2. **The spec's call count is out of date.** Since `84ef67e` (2026-10-13), `run_pipeline` ends with `enforce_grounding` (`pipeline/grounding.py:22`), which always makes a Sonnet 4.6 `grounding_check` call. On flags it adds up to 2 Opus `grounding_repair` calls, each followed by another check. A normal run is now **3 sequential calls** (structure, draft, grounding check), 4 with compress, and up to 8 in the worst case. None of the eval numbers include this call. The closest proxy is variant B's Sonnet 4.6 structured `review` call (same model, similar input): **8.9 s p50, 13.6 s p95**. So today's production p50 is likely **30 s or more**.
3. **The 10 s p95 target can't be reached by tuning the drafter alone.** Even with thinking off (about 850 visible tokens, ~8.5 s), adding a sequential grounding check (~9 s) and ~3 s outside the model calls gives about 20 s. Streaming can show the first text in 1 to 2 s, but the checked version arrives much later. The grounding path needs its own design decision (section 5.4). It is not in the spec today.
4. **About 3 s per run (p50; p95 4.8 s) is spent outside model calls.** The budget for that part is about 0.3 s. Nothing measures where those 3 s go. The code has visible sequential waste: the query is embedded twice, there is an N+1 lookup per source, and stats writes run on the request path.
5. **The chunk-count experiment (spec 7.1) can't be run meaningfully on the current goldens.** Eval corpora are small: the drafter received a median of 2.5 retrieved chunks (max 9) and entity enrichment added chunks in 3 of 20 runs. Testing 4 vs 6 vs 8 vs 12 needs a richer fixture corpus first.

## 1. Baseline numbers

Source: eval run `20261010-215033-standard-C-Opus` (the ablation "full" run, commit `2f19bb1`), with per-call latency read from its `generation_traces` rows in the eval Supabase project. 27 goldens: 20 drafted, 7 stopped by the coverage gate (`gated`, all `off_topic`/`sparse`). Each golden ran once.

| Measure (n = 20 drafted posts) | p50 | p95 | max |
|---|---|---|---|
| End to end, wall time (`seconds` in runs.jsonl) | 22.6 s | 31.0 s | 31.5 s |
| `archetype` call (Haiku 4.5, structure choice) | 0.8 s | 1.6 s | 2.5 s |
| `generate` call (Opus 5.5, effort medium, thinking on) | 19.0 s | 25.5 s | 26.7 s |
| Compress (`trim` at that commit), ran in 1 of 20 | 1.0 s | | |
| Wall time outside model calls | 3.0 s | 4.8 s | 5.0 s |

| Tokens per draft call | median | max |
|---|---|---|
| Input | 4,200 | 6,581 |
| Output (thinking included) | 1,873 | |
| Thinking | 1,035 | 1,740 |
| Output throughput | ~99 tok/s | |

- Calls per run: 2 in 19 runs, 3 in 1 run. Compress ran in 5% of runs.
- Cost per post: median $0.054, p95 about $0.076 (draft plus structure only).
- For comparison (same goldens): C on Sonnet 4.6 took 14.6 s p50 / 25.2 s p95; B-Opus took 43.6 s p50 / 73.4 s p95.
- Grounding check (added 2026-10-13, after these runs): **not measured.** The proxy is the B-Opus `review` call (Sonnet 4.6, n = 137): 8.9 s p50, 13.6 s p95, max 50.6 s. `targeted_fix` (Opus) took 4.1 s p50.
- Citations: of the drafted posts, 17 of 20 cite exactly one source id, 1 cites two and 1 cites three. With so few chunks retrieved, this says nothing yet about the 12-chunk question.

**Caveats.** n = 20 with one run per golden, so the p95 is roughly the second-slowest run. The wall time includes eval harness overhead. I couldn't read production traces: the read-only query against the production project was blocked in this session. To get real production numbers, including `grounding_check` and `grounding_repair` latency and how often repairs happen, run this in `backend/` with the venv active:

```python
from dotenv import load_dotenv; load_dotenv(".env")
from db.supabase_client import supabase as sb
import statistics as st, collections
rows = sb.table("generation_traces").select("created_at,llm_calls,v:node_outputs->>variant,g:node_outputs->grounding->>outcome") \
         .gte("created_at", "2026-10-13").limit(1000).execute().data
rows = [r for r in rows if r["v"] == "C-Opus" and r["llm_calls"]]
by = collections.defaultdict(list)
for r in rows:
    for c in r["llm_calls"]: by[c["event_type"]].append(c["latency_ms"] / 1000)
for ev, xs in by.items():
    xs.sort(); print(ev, len(xs), "p50", round(st.median(xs), 1), "p95", round(xs[int(0.95 * (len(xs) - 1))], 1))
print("grounding outcomes", collections.Counter(r["g"] for r in rows))
```

## 2. What is not measured today

| Gap | Where it would come from |
|---|---|
| Per-step wall time for C and C-Opus | `_timed` wraps only B's nodes (`pipeline/single_writer.py:78`, used in `wire_reviewed`) |
| `load_profile`, `retrieval`, `plan` (shared nodes) | not wrapped for any variant (`pipeline/graph.py:193`) |
| Each DB call inside retrieval: experience nodes, embed, vector, BM25 (cold corpus load), similarity fill, entity lookup, enrichment fetch, second embed, per-source hierarchy and adjacent chunks, `increment_retrieval` writes | none |
| `enforce_grounding` as a whole (checks plus repairs) | the calls are traced, the step is not |
| Total wall time of a production run | only eval runs record `seconds`; the trace row has no total |
| Time to first token | impossible without streaming |
| Effort, thinking config, cache read/write tokens, call start offset | the call record in `llm/client.py:155` has model, tokens, thinking tokens, stop_reason and latency only. Without start offsets you can't tell parallel calls from sequential ones. |
| Trace write time | after the trace is built, so it can't record itself; log it |

## 3. Proposed instrumentation (build after approval)

Branch `feat/gen-instrumentation`. No migration: everything goes into `node_outputs.step_timings` (already in `_OPTIONAL_OUTPUTS`, `pipeline/trace.py:52`) and into the existing `llm_calls` entries.

- Wrap every node in `wire_draft_only` and the shared nodes (`load_profile`, `retrieval`, `plan`, `low_coverage`) with the existing `_timed` (move it to `pipeline/trace.py` or a small shared spot so `graph.py` can use it without a cycle). Step names give `profile_load_ms`, `retrieval_ms`, `structure_ms`, `draft_ms`, `strip`/`finalise`, `checks_ms`, `compress_ms`.
- Retrieval sub-timings: a `retrieval_timings` dict on state (embed, hybrid, enrichment, bundle, stats, experience nodes), recorded with `time.perf_counter()` around the existing calls.
- `run_pipeline`: time `enforce_grounding` as `grounding_ms` (with `repairs` count already in the record) and the whole run as `total_ms`.
- `complete()` call record: add `effort` (from `output_config`), `thinking` (the request's thinking config, or "default"), `cache_read_input_tokens`, `cache_creation_input_tokens`, and `started_ms` (offset from the start of `trace_calls`). `ttft_ms` is added in the streaming branch.
- evals: `run.py` reads `step_timings` and adds per-step p50/p95 to the run report.

Tests (fakes only): C trace has a timing for every step that ran; shared nodes timed under A, B and C; gated run has `load_profile` and `retrieval` timings only; `total_ms` ≥ sum of steps; call record carries `effort` and `started_ms`; a timing failure never fails generation.

## 4. Gap map

R = request path, I = ingestion/offline only.

| Spec § | What exists (file: function) | Missing | Path |
|---|---|---|---|
| 2 Live variant | `config/features.py` `DEFAULT_PIPELINE_VARIANT = "C-Opus"`; `pipeline/single_writer.py` `wire_draft_only` | Section 2 omits `enforce_grounding` (see flags) | R |
| 2 Opus thinking | `llm/models.py` `MODELS[OPUS_5_5]` thinks=True, `DRAFT_EFFORT` medium; `THINKING_ALLOWANCE_TOKENS` 3,500 | | R |
| 2 No streaming | confirmed: `routers/generate.py:179` returns JSON; `llm/client.py` is non-streaming only (`MAX_NON_STREAMING_OUTPUT_TOKENS`) | streaming client and endpoint | R |
| 3/4 One Opus call | structure is a separate Haiku call: `agents/archetype_agent.py` `choose_structure`, `structure_node` | folding it in (Phase 1) | R |
| 5 Identities | business context per account: `graph.load_profile_node` → `business_context(get_account(...), pillar)`; `config/niches.py` pillars | identity entity, several per account, choice at generation | R+I |
| 6.1 Fingerprint | `memory/profile_store.py`: `voice_descriptors`, `writing_samples` (≤10, `save_writing_sample`), `profile_voice_context` | structured fingerprint, compiled 300–600-token profile, background job, versioning, `provisional` flag | I (read on R) |
| 6.2 Experience events | `memory/experience_store.py`: work, personal_project and education records (entity_name, role, dates). Events exist only as the drafter's `<event>` quote from a source (`draft_prompt.py:301`, checked by `checks.event_unverified`) | event records with verification; extractor | I |
| 6.3 Beliefs | none | store plus extractor | I |
| 6.4 Authority map | partial signal: `utils/frames.py` frame/authorship (with a labelled STOPGAP at `frames.py:124`); `decide_perspective` in plan | map plus constraint on strategy | I (read on R) |
| 6.5 Strategy history | `posts.archetype` only (`memory/feedback_store.py:23` `log_post`); `get_recent_posts` | angle, hook, structure, CTA and opening line per post; summary for the prompt | R (write) |
| 6.6 Cold start | `coverage_gate` (`agents/retrieval_agent.py:55`) → `low_coverage_node` (empty post); `skipped_first_post`; no-specifics off | data tiers, follow-up questions, `user_stated` memories, starter voice | R+I |
| 7 Retrieval | `query_similar_hybrid` (vector ‖ BM25 already in a 2-thread pool, RRF), `_enrich_with_entity_chunks`, `_build_retrieval_bundle`; thresholds in `config/retrieval.py` | purpose split, metadata ranking, chunk-type metadata, concurrency across the other lookups | R |
| 7.1 Chunking | `utils/chunker.py`: fixed 500-word windows, 50-word overlap | by-meaning chunks (if splitting is shown) | I |
| 8 Strategy | archetype registry (`utils/formatters.get_archetype`), `allowed_archetypes` (story types need a self-authored chunk; opinion perspective restricts to opinion/explainer/general) | angle, hook and CTA taxonomies as config; eligibility table; repetition penalty | R |
| 9 Writing rules | rules live inline in `agents/draft_prompt.py`; deterministic checks in `pipeline/checks.py` (citations, specifics in cited source, event verification, length, profile `words_to_avoid`) | `CONTENT_WRITING_RULES.md`; recent-post similarity (rule 5); n-gram copy check (rule 6) | R |
| 10 Output contract | `<event>` + `<post>` envelope with `[[S1]]`/`[[R]]`/`[[V]]` markers (`draft_prompt.py:280`) | strategy block, alternative hooks | R |
| 10.4 Two paths | variant B (`wire_reviewed`) exists and works | "refine more" entry point that runs B on request | R |
| 11 Latency | see section 1 | | R |
| 12 Evals | `evals/`: run, ablate, blind (human read), judge (DeepEval through `complete`), goldens (27: rich, sparse, off_topic across ds/pm/founder) | identity types, business persona, sequence diversity, first-person-without-source check for cold start | offline |
| 13 Learning loop | `post_versions` history; `user_events` UI analytics (`routers/analytics.py`); Zernio publishing (`publishing/`) | engagement pull from Zernio; edit-signal derivation from `post_versions` | I |
| 14 Layout | `agents/`, `pipeline/`, `memory/`, `utils/` per CLAUDE.md | Recommend keeping the existing layout and adding `config/strategy.py`, not new top-level packages | |

### Contradictions and corrections

1. **Call count (§2).** Wrong since `84ef67e`: see summary point 2. Any latency plan has to include `enforce_grounding`.
2. **CLAUDE.md "Rules: Models"** says Sonnet 4.6 for generation. The code drafts with Opus 5.5 under the default C-Opus (`VARIANT_ROLE_MODELS`). CLAUDE.md is out of date. The grounding check uses the `review` role (Sonnet 4.6); repairs use the `draft` role (Opus 5.5).
3. **Archetype rule (§2)** is correct and stricter than the spec says: story archetypes also require the drafter to quote, word for word, the source sentence describing the event, and a failed quote downgrades to General (`strip_draft_node`).
4. **Retrieval (§2, §7)** is right on n_results=8, +4 and the 0.30 floor. Additional points:
   - vector and BM25 are already parallel;
   - the query is embedded twice (`query_similar_hybrid:482` and again inside enrichment at `retrieval_agent.py:307`);
   - `_build_retrieval_bundle` calls `get_source_node` and `get_adjacent_chunks` once per source, sequentially;
   - `increment_retrieval` writes once per source title on the request path;
   - the BM25 corpus is fetched in full from Supabase on a cold cache (5-minute TTL, `vector_store.py:45`), which is a likely p95 spike;
   - experience nodes are loaded every request, and the comment says they're for the fact checker (pipeline A). Whether C reads them still needs checking.
5. **compress event name.** At `2f19bb1` the call was logged as `trim`; it's now `compress` (`agents/compress_agent.py:96`). Eval comparisons across that change need to map both names.

## 5. Streaming feasibility and design

### 5.1 How the cited draft is produced today
1. `cited_draft_node` (`agents/draft_agent.py:119`): one non-streaming Opus call. The output is `<event>…</event>` (story archetypes only) then `<post>…</post>`, every prose sentence ending in `[[S2]]`, `[[S1,S3]]`, `[[R]]` or `[[V]]`.
2. `strip_draft_node`: parses the envelope, keeps the body, records the event, and downgrades to General on `<event>none</event>`.
3. `finalise_draft_node` → `finalise_marked`: normalises the text, removes the markers into spans (`citations`), records marker failures and validates length.
4. `checks_node`: deterministic checks, record only.
5. compress (only when over the maximum) → refinalise → recheck.
6. `enforce_grounding` (after the graph): a model check, and up to 2 repairs that rewrite the post.

### 5.2 Can it stream?
Yes. Everything after the draft needs the complete text, but the text itself streams. A streaming filter can drop `<event>…</event>`, emit only what's inside `<post>`, and hold back any `[[…]]` until the closing `]]`, then drop it. That's a closed format, so a small deterministic state machine handles it; markers can be split across deltas, which the tests must cover. Normalisation in `finalise` (punctuation, spacing) changes characters, so the streamed text is a preview, not the final text.

Constraint: with thinking on, no text arrives until thinking ends (~10 s today). Streaming only meets the 1 to 2 s first-text goal if Phase 1 picks a setting with thinking off or very low.

### 5.3 Design
- `llm/client.py`: add `stream_complete()` next to `complete()`. Same shared client, same usage logging and trace record, plus `ttft_ms`.
- `utils/`: pure `MarkerStreamFilter` (feed delta → visible text).
- `cited_draft_node` writes deltas to a per-request queue carried in state. The pipeline still runs in `run_in_threadpool`, and the endpoint reads the queue asynchronously.
- New endpoint `POST /generate/stream` (SSE over `fetch`, since the Supabase JWT goes in a header and `EventSource` can't send one). `/generate` stays as is. Events:
  - `status` (retrieving, writing, checking)
  - `delta` (visible text)
  - `final` (the same payload `/generate` returns today, including `grounding`, `citations`, `trace_id`)
  - `error` (refused, truncated, empty, low_coverage)
- Railway: confirm the proxy doesn't buffer SSE (`Cache-Control: no-cache`, no compression on that route). One uvicorn worker is fine because the endpoint is async.

### 5.4 What the user sees when the final text differs
- While streaming: the text appears as a preview marked "Checking against your sources…" and isn't editable.
- On `final`: the preview is replaced by the final post. If sentences changed (grounding repair, compress), those sentences get a brief highlight and a line like "2 sentences adjusted to match your sources", using the spans the pipeline already records. If the outcome is `needs_review`, the flags appear as they do today.
- On a non-ok status: the preview is cleared and the existing message is shown.
- The grounding problem: with the check running after the full draft, "final" lands about 9 s after the stream ends. The options to evaluate are below. None of them weakens grounding:
  - (a) Accept it, with the preview clearly marked.
  - (b) Check spans as they complete during the stream, in parallel calls, so the result lands about 1 to 2 s after the last sentence. Same check, earlier start. This costs more calls and needs a test that its recall matches the whole-post check.
  - (c) A faster model for `grounding_check`. This is a model change, so it needs your explicit instruction and an eval on a labelled unsupported-claim set.

  I recommend measuring (b) and (c) in a dedicated branch after Phase 1.

## 6. Phase 1 experiment design

**Question:** the fastest drafter configuration whose grounding and blind ranking are not worse than C-Opus.

**Arms** (all keep the structure eligibility rule in code via `allowed_archetypes`, and all keep `enforce_grounding`):

| Arm | Structure | Drafter |
|---|---|---|
| a | Haiku call (today) | Opus 5.5, effort medium, thinking default |
| b | folded into the draft: the prompt lists only `allowed_archetypes(...)` and the drafter names its choice in the envelope | Opus 5.5, medium |
| c1 | as b | Opus 5.5, effort low |
| c2 | as b | Opus 5.5, thinking disabled |
| d | as b | Sonnet 5.5 (default effort high). If its latency fails, also try effort low, as d2 |

**Implementation:**
- Add a variant `D` (one-call graph: plan → draft → strip → finalise → checks → compress → recheck) sharing C's nodes.
- Add an eval-only override for effort and thinking, alongside the existing `--model ROLE=CONSTANT`.
- Never expose either as a `/generate` field.

**Fixed context:** retrieval is deterministic for an unchanged corpus. The harness checks that each golden's retrieved chunk ids match across arms (from the trace) and marks any mismatch.

**Runs:** the 20 drafting goldens × 3 repeats per arm (n = 60 per arm, so p95 means something). The 7 gated goldens run once to confirm the gate behaves the same.

**Measures, from the Phase 0 instrumentation:**
- p50/p95 of total, draft, structure and grounding time
- thinking tokens
- cost per post
- `checks_final` issue counts
- grounding outcome (verified / repaired / needs_review) and repair count
- `unsupported_specifics` (existing judge metric)
- the event downgrade rate (story archetype chosen but no quotable event)

**Blind read (you):** 10 goldens. Drop any arm whose grounding is worse than a first, then read up to 3 arms against a. Same procedure as ablation "full".

**Decision rules (fix them before running):**
1. An arm is eligible if its grounding failure count is at most a's and its `needs_review` rate is not higher.
2. Among eligible arms, the fastest by p95 total wins unless a beats it in 7 or more of 10 blind reads.

**Cost estimate**, from section 1 tokens and `llm/pricing.py` prices. The grounding check is about $0.021 per post plus repairs at ~$0.01 expected; both are assumptions until the production query above is run.

| Arm | ≈ $/post | × 60 |
|---|---|---|
| a | 0.085 | 5.10 |
| b | 0.087 | 5.22 |
| c1 | 0.071 | 4.26 |
| c2 | 0.066 | 3.96 |
| d | 0.060 | 3.60 |
| Judge (existing DeepEval metrics, ~$0.02 × 300) | | 6.00 |
| **Total** | | **≈ $28** (set `--spend-cap 35`; d2 adds ≈ $3) |

## 7. Branch plan

Smallest first, one PR each. Changes from the spec order are marked with ⇄, each with its reason.

| # | Branch | Content | Tests |
|---|---|---|---|
| 0 | `docs/generation-phase0` | the spec and this report | none |
| 1 | `feat/gen-instrumentation` | section 3 | section 3 list |
| 2 ⇄ | `perf/retrieval-request-path` | Only if instrumentation shows > 0.5 s: reuse the query embedding, batch hierarchy/adjacent lookups, move `increment_retrieval` off the request path, skip unused experience-node loads, warm the BM25 cache after ingest. Results must be identical. **Why earlier:** ~3 s outside model calls is 30% of the p95 budget, and the fix doesn't change output. | same bundle (ids, order) before and after on the fakes; stats still recorded; one DB call per kind |
| 3 | `exp/one-call-drafter` (Phase 1) | variant D, eval override flags, run, then set the default | D wiring; eligible archetypes only in the prompt; story types blocked without a self-authored chunk; `PIPELINE_VARIANT=A` still runs; override flags rejected outside evals |
| 4 ⇄ | `feat/grounding-latency` (new) | measure options (b) and (c) from 5.4 and pick one. **Why:** the measurements show the 10 s target is unreachable with today's sequential check. | recall on a labelled unsupported-claim set ≥ today; repair path unchanged |
| 5 | `feat/generate-stream` (Phase 2) | section 5.3 and minimal frontend | filter: markers split across deltas, `<event>` hidden, text outside `<post>` dropped; SSE event order; non-ok statuses; 401 without token; `/generate` unchanged |
| 6 | `evals/rich-fixture-corpus` ⇄ | a larger persona corpus so the 7.1 experiment means something. **Why:** current goldens retrieve a median of 2.5 chunks. | loader tests |
| 7 | `exp/chunk-count`, then `feat/retrieval-by-purpose` (Phase 3) | 7.1 experiment; purpose split; metadata ranking; concurrent lookups | bounded context object; source ids kept; quotas respected; concurrency doesn't change results |
| 8 ⇄ | `feat/cold-start-questions` (Phase 5b, moved before 4 and 5) | Data tiers, template questions, answers stored as `user_stated` sources citeable as `[[S…]]`. **Why earlier:** 7 of 27 goldens (26%) hit the empty-post dead end, and the eligibility rule it needs already exists (`allowed_archetypes`). | no first-person claim without a stored source; skipped questions give an observation post with the flag set; answers persisted per user |
| 9 | `feat/writer-fingerprint` (Phase 4) | | compiled profile ≤ 600 tokens; provisional flag; never computed on the request path |
| 10 | `feat/strategy-contract` (Phase 5) | | config validation; eligibility gate table; repetition penalty from history; strategy stored with the post |
| 11 | Phase 6 split into four PRs: `feat/experience-events`, `feat/beliefs`, `feat/authority-map`, `feat/identities` (with LinkedIn import) | | per PR |
| 12 | Phase 7: `feat/edit-signals`, then `feat/post-performance` | | |

**No-specifics decision:** retire it once branch 8 lands. The follow-up answers become real stored sources the drafter cites, which removes the after-the-fact repair that caused the dangling references. Remove the flag, the 400 path and their tests in branch 8.
