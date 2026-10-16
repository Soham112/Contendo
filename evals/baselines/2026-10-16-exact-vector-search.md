# Exact vector search (migration 013): before and after

Same 61 quality_v1 cases, same eval data, same code except migration 013 (drop the IVFFlat index, index `embeddings.user_id`). Before: `2026-10-15-quality-v1-retrieval.md` (commit `1a71a2d`). After: run `2026-10-16-exact-vector` (commit `2e74a7a` + 013). Both runs read-only, $0. Retries recorded per run (after: tc-08, re-02, fs-02, fs-03, fs-04, me-05, me-09); hybrid-search reliability passed on every case in both runs.

Migration 013 was applied to the eval project and to production on 2026-10-16.

## The engine: match_embeddings top 8 vs exact cosine over the same stored vectors

| Library | Chunks | Recall@8 vs exact, before → after | Rows returned of 8, before → after |
|---|---|---|---|
| production, main account (18 real topics) | 149 | 0.03 → 1.00 | 3.3 → 8.0 |
| eval me (copy of the same library) | 149 | 0.04 → 1.00 | 2.3 → 8.0 |
| eval rf | 21 | 0.01 → 1.00 | 0.4 → 8.0 |
| eval re | 12 | 0.09 → 1.00 | 0.9 → 8.0 |
| eval tc / fs / bo / ni1 | 6 / 6 / 2 / 1 | 0.00-0.08 → 1.00 | → whole library |

Function latency (median per call, from a laptop): 105-117 ms before, 107-223 ms after across three repeats, with the same library swinging 131-186 ms between repeats. No consistent cost from the exact scan; production `hybrid_search` timings in traces are the cleaner check.

## Scorecard means, before → after

| Group | Recall@1 | Recall@3 | Recall@cutoff | MRR | Precision@cutoff | Off-topic rate |
|---|---|---|---|---|---|---|
| dev · verified (32) | 0.19 → 0.45 | 0.37 → 0.55 | 0.37 → 0.57 | 0.35 → 0.63 | 0.55 → 0.65 | 0.13 → 0.10 |
| hold-out · verified (20) | 0.59 → 0.62 | 0.65 → 0.65 | 0.65 → 0.65 | 0.74 → 0.74 | 0.85 → 0.74 | 0.00 → 0.07 |
| me · metadata_only (9) | 0.50 → 0.56 | 0.81 → 0.88 | 0.94 → 0.94 | 0.81 → 0.79 | 0.77 → 0.61 | 0.08 → 0.07 |

Pass counts, before → after: dev recall 7/25 → 11/25, MRR 9/25 → 16/25, gate accuracy 15/30 → 18/30; hold-out unchanged except precision 9/13 → 7/13 and off-topic 20/20 → 17/20; me gate accuracy 9/9 → 8/9.

## Cases that changed (gate · Recall@cutoff · MRR)

| Case | Gate | Recall | MRR | Note |
|---|---|---|---|---|
| ni1-01 | low_coverage → pass | 0 → 1 | 0 → 1 | the user's only note, titled as the topic, now found |
| bo-01 | low_coverage → pass | 0 → 0.5 | 0 → 1 | |
| bo-02 | low_coverage → pass | 0 → 1 | 0 → 1 | |
| nb-01, nb-05 | skipped_first_post → pass | 0 → 1 | 0 → 1 | covered now, so the first-post skip no longer applies |
| nb-02 | skipped_first_post → pass | 0 → 0.5 | 0 → 1 | |
| rf-05, re-04, re-05 | pass | 1 → 1 | 0.33-0.5 → 1 | required source moved to rank 1 |
| rf-02 | pass | 1 → 1 | 0.33 → 0.5 | one more off-topic source |
| re-06, fs-01 | pass | unchanged | 0.5 → 0.33, 1 → 0.5 | a background source now ranks first |
| me-01 (XLR8) | pass | 1 → 1 | 0.5 → 1 | own note now rank 1; sources 3 → 6, off-topic 2 → 3 |
| me-03, me-05 | pass | 1 → 1 | down | more sources pass the 0.30 relevance floor |
| me-09 (uncovered, low authority) | low_coverage → pass | n/a | n/a | gate now passes on 3 loosely related sources |

## Reading

- The fix is a correctness fix to the search engine, not tuning: it was chosen from the spec (search should return the nearest chunks), verified against exact search independently of the labels, and it improves the real production library from 3% to 100% of the true nearest chunks.
- Dev improves clearly (recall +0.20, MRR +0.29). Hold-out recall is flat and precision drops, because more true matches now clear the 0.30 relevance floor, distractors included. Under the hold-out rule this is not an overfit (nothing was fitted to dev), but it shows the next problems, which exact search no longer hides:
  1. **Titles aren't searched.** rf-03's note is titled with the topic and still scores 0.287 cosine; tc-03 "Nearshoring" scores 0.19 cosine and 0.0 BM25 because the word is only in the title. Step 3: chunking and what gets embedded.
  2. **Thresholds were set on broken scores.** The 0.30 relevance floor and coverage gate were tuned while vector search returned near-random rows; now distractors pass and me-09 passes the gate. Recalibrate on quality_v1 once step 3's embeddings settle.
  3. **Ranking is by relevance only.** Background and distractor sources outrank required ones in re-06 and fs-01; own experience isn't preferred (step 4 ranking).
