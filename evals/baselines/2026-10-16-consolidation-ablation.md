# Consolidation chunks: retrieval with and without them

Question: do consolidation chunks (one Haiku brief per entity found in 3 or more sources, `agents/consolidation_agent.py`) improve retrieval? Decides whether the delete cascade should rebuild them or whether they are retired.

Same 61 quality_v1 cases, same eval data, same code (commit `2418c91`). With: run `2026-10-15-consol-baseline`. Without: run `2026-10-15-consol-removed`, the same harness with consolidation rows removed from every candidate source before ranking (the vector RPC is asked for 8 + k rows, k = the user's consolidation count, and the top 8 regular chunks kept; the BM25 corpus and id fetches drop them), as if they had never been written. Both read-only, $0. The ablation wrapper lived in the session scratchpad, not in the repo.

Consolidation chunks in the eval project: 14, across 6 synthetic eval users (1 to 3 each); persona `me` has none. Production has 1 in total (built partly from a deleted source). In the "with" run they reached the drafter in 7 cases (rf-05, rf-08, re-01, re-02, re-04, re-05, re-06).

## Scorecard means, with → without

| Group | Recall@1 | Recall@3 | Recall@cutoff | MRR | Precision@cutoff | Off-topic rate |
|---|---|---|---|---|---|---|
| dev · verified (32) | 0.453 → 0.453 | 0.547 → 0.547 | 0.567 → 0.567 | 0.633 → 0.640 | 0.646 → 0.646 | 0.097 → 0.097 |
| hold-out · verified (20) | 0.618 → 0.559 | 0.647 → 0.588 | 0.647 → 0.647 | 0.735 → 0.691 | 0.738 → 0.738 | 0.073 → 0.073 |
| me · metadata_only (9) | unchanged | unchanged | 0.938 → 0.938 | 0.792 → 0.792 | 0.613 → 0.613 | 0.071 → 0.071 |

Pass counts change only for hold-out MRR, 13/17 → 12/17. Hybrid-search reliability reads 13/28 and 18/20 in the "without" run: an artifact of the ablation (the harness compares the BM25 corpus with the library row count, which still includes consolidation rows), not a search failure.

## Cases that changed

| Case | Split | With | Without |
|---|---|---|---|
| re-05 | hold-out | needed source (re-bp) at rank 1, MRR 1.0 | rank 4, MRR 0.25 |
| re-06 | dev | needed source at rank 3, MRR 0.333 | rank 2, MRR 0.5 |

Every other case keeps the same sources in the same order, minus the consolidation entry.

## Reading

- B1 labels a consolidation chunk as neither a needed source nor off-topic, so these metrics can only show its effect on how the other sources rank; they can't credit the brief's own content. That needs generation scoring (B2-B8).
- The two rank changes go in opposite directions and come from re-ranking when the rows leave the candidate pool (the BM25 corpus changes, so does each chunk's RRF position), not from what the briefs say. One case each, n = 7 affected cases, all synthetic: no measurable gain or loss.
- The delete cascade removes a consolidation chunk when one of its contributing chunks is deleted and does not rebuild it.
