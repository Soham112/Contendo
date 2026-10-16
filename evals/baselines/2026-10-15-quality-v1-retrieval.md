# Retrieval scorecard: 2026-10-15-baseline

Commit `1a71a2d` · 2026-10-16T01:32:38.563662+00:00 · eval project `croalztabgzowjkkhkcm` · 61 cases · Claude spend $0.000 · retried: rf-02, rf-08, me-02, me-03, me-06, me-08

Criteria: docs/QUALITY.md B1. First table: cases passed / cases where the criterion applies. Second: means over applicable cases (Recall@K counts each must_use_all source and each must_use_any group as one unit; the cutoff is the sources that reach the drafter).

| Group | n | recall | mrr | precision | off_topic | own_share | gate_accuracy | hybrid_reliability |
|---|---|---|---|---|---|---|---|---|
| dev · verified | 32 | 7/25 | 9/25 | 4/14 | 28/32 | 6/7 | 15/30 | 28/28 |
| hold-out · verified | 20 | 9/17 | 13/17 | 9/13 | 20/20 | 1/2 | 12/16 | 20/20 |
| me · metadata_only | 9 | 7/8 | 6/8 | 5/8 | 8/9 | – | 9/9 | 9/9 |

| Group | n | recall@1 | recall@3 | recall@5 | recall@cutoff | mrr | precision@cutoff | off_topic_rate |
|---|---|---|---|---|---|---|---|---|
| dev · verified | 32 | 0.193 | 0.367 | 0.367 | 0.367 | 0.347 | 0.548 | 0.132 |
| hold-out · verified | 20 | 0.588 | 0.647 | 0.647 | 0.647 | 0.735 | 0.846 | 0.0 |
| me · metadata_only | 9 | 0.5 | 0.812 | 0.938 | 0.938 | 0.812 | 0.769 | 0.083 |

## By persona

| Group | n | recall | mrr | precision | off_topic | own_share | gate_accuracy | hybrid_reliability |
|---|---|---|---|---|---|---|---|---|
| rf | 9 | 5/7 | 3/7 | 3/7 | 7/9 | 5/5 | 5/8 | 9/9 |
| tc | 8 | 5/6 | 5/6 | 3/5 | 8/8 | 0/1 | 5/6 | 8/8 |
| ni0 | 4 | – | – | – | 4/4 | – | 0/4 | – |
| ni1 | 4 | 0/2 | 0/2 | – | 4/4 | 0/1 | 2/3 | 4/4 |
| re | 8 | 3/8 | 7/8 | 1/7 | 6/8 | 2/2 | 7/7 | 8/8 |
| fs | 7 | 2/7 | 6/7 | 5/6 | 7/7 | – | 4/6 | 7/7 |
| bo | 6 | 0/6 | 0/6 | 0/1 | 6/6 | – | 3/6 | 6/6 |
| nb | 6 | 1/6 | 1/6 | 1/1 | 6/6 | – | 1/6 | 6/6 |
| me | 9 | 7/8 | 6/8 | 5/8 | 8/9 | – | 9/9 | 9/9 |

| Group | n | recall@1 | recall@3 | recall@5 | recall@cutoff | mrr | precision@cutoff | off_topic_rate |
|---|---|---|---|---|---|---|---|---|
| rf | 9 | 0.429 | 0.714 | 0.714 | 0.714 | 0.524 | 0.622 | 0.2 |
| tc | 8 | 0.833 | 0.833 | 0.833 | 0.833 | 0.833 | 0.833 | 0.0 |
| ni0 | 4 | – | – | – | – | – | – | – |
| ni1 | 4 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | – | – |
| re | 8 | 0.229 | 0.646 | 0.646 | 0.646 | 0.688 | 0.545 | 0.064 |
| fs | 7 | 0.571 | 0.571 | 0.571 | 0.571 | 0.857 | 0.889 | 0.0 |
| bo | 6 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| nb | 6 | 0.167 | 0.167 | 0.167 | 0.167 | 0.167 | 1.0 | 0.0 |
| me | 9 | 0.5 | 0.812 | 0.938 | 0.938 | 0.812 | 0.769 | 0.083 |

## Cases (synthetic)

| Case | split | recall | mrr | precision | off_topic | own_share | gate_accuracy | hybrid_reliability | drafter sources |
|---|---|---|---|---|---|---|---|---|---|
| rf-01 | dev | ✓ 1.0 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | ✓ 1.0 | ✓ pass | ✓ 21/21 | rf-s03 |
| rf-02 | dev | ✓ 1.0 | ✗ 0.333 (rank 3) | ✗ 0.667 | ✓ 0 | ✓ 1.0 | ✓ pass | ✓ 21/21 ×2 | rf-s09, rf-s03, rf-s02 |
| rf-03 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ low_coverage | ✓ 21/21 | none |
| rf-04 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ low_coverage | ✓ 21/21 | none |
| rf-05 | dev | ✓ 1.0 | ✗ 0.333 (rank 3) | ✗ 0.286 | ✓ 0 | ✓ 0.857 | ✓ pass | ✓ 21/21 | rf-s08, rf-s16, rf-s04, consolidation, rf-s01, rf-s02, rf-s06, rf-s03 |
| rf-06 | dev | – | – | ✓ 1.0 | ✓ 0 | – | – | ✓ 21/21 | rf-s17 |
| rf-07 | dev | ✓ 1.0 | ✓ 1.0 (rank 1) | ✗ 0.4 | ✗ 2 | ✓ 0.6 | ✓ pass | ✓ 21/21 | rf-s14, rf-s09, rf-s17, rf-s03, rf-s02 |
| rf-08 | dev | – | – | ✗ 0.0 | ✗ 1 | – | ✗ pass | ✓ 21/21 ×2 | rf-s19, consolidation |
| rf-09 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | ✓ 1.0 | ✓ pass | ✓ 21/21 | rf-s05 |
| tc-01 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✗ 0.667 | ✓ 0 | ✗ 0.333 | ✓ pass | ✓ 6/6 | tc-s01, tc-s05, tc-s02 |
| tc-02 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✓ pass | ✓ 6/6 | tc-s03 |
| tc-03 | holdout | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ low_coverage | ✓ 6/6 | none |
| tc-04 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✓ pass | ✓ 6/6 | tc-s01 |
| tc-05 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✓ pass | ✓ 6/6 | tc-s05 |
| tc-06 | holdout | – | – | – | ✓ 0 | – | – | ✓ 6/6 | none |
| tc-07 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✗ 0.5 | ✓ 0 | – | – | ✓ 6/6 | tc-s02, tc-s05 |
| tc-08 | holdout | – | – | – | ✓ 0 | – | ✓ low_coverage | ✓ 6/6 | none |
| ni0-01 | dev | – | – | – | ✓ 0 | – | ✗ skipped_first_post | – | none |
| ni0-02 | dev | – | – | – | ✓ 0 | – | ✗ skipped_first_post | – | none |
| ni0-03 | dev | – | – | – | ✓ 0 | – | ✗ skipped_first_post | – | none |
| ni0-04 | dev | – | – | – | ✓ 0 | – | ✗ skipped_first_post | – | none |
| ni1-01 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | ✗ 0.0 | ✗ low_coverage | ✓ 1/1 | none |
| ni1-02 | dev | – | – | – | ✓ 0 | – | ✓ low_coverage | ✓ 1/1 | none |
| ni1-03 | holdout | – | – | – | ✓ 0 | – | ✓ low_coverage | ✓ 1/1 | none |
| ni1-04 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | – | ✓ 1/1 | none |
| re-01 | dev | ✗ 0.5 | ✓ 1.0 (rank 1) | ✗ 0.5 | ✓ 0 | ✓ 1.0 | ✓ pass | ✓ 12/12 | re-s01, re-s05, consolidation |
| re-02 | dev | ✗ 0.667 | ✓ 1.0 (rank 1) | ✗ 0.5 | ✗ 1 | ✓ 0.75 | ✓ pass | ✓ 13/13 | re-02-details, re-s02, consolidation, re-s07, re-s05 |
| re-03 | dev | ✗ 0.5 | ✓ 1.0 (rank 1) | ✗ 0.5 | ✓ 0 | – | ✓ pass | ✓ 12/12 | re-s03, re-s04 |
| re-04 | dev | ✓ 1.0 | ✓ 0.5 (rank 2) | ✗ 0.4 | ✗ 1 | – | ✓ pass | ✓ 12/12 | consolidation, re-bp, re-s04, re-s07, re-s02, re-s05 |
| re-05 | holdout | ✓ 1.0 | ✓ 0.5 (rank 2) | ✗ 0.5 | ✓ 0 | – | – | ✓ 12/12 | re-s08, re-bp, re-s03, re-s05 |
| re-06 | dev | ✓ 1.0 | ✓ 0.5 (rank 2) | ✗ 0.667 | ✓ 0 | – | ✓ pass | ✓ 12/12 | consolidation, re-s05, re-bp, re-s03 |
| re-07 | dev | ✗ 0.5 | ✓ 1.0 (rank 1) | ✓ 0.75 | ✓ 0 | – | ✓ pass | ✓ 12/12 | re-s06, re-s09, re-s04, re-s03 |
| re-08 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✓ low_coverage | ✓ 12/12 | none |
| fs-01 | holdout | ✗ 0.5 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✓ pass | ✓ 6/6 | fs-s01, fs-s02 |
| fs-02 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✓ pass | ✓ 6/6 | fs-s04 |
| fs-03 | holdout | ✗ 0.5 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | – | ✓ 6/6 | fs-s01 |
| fs-04 | holdout | ✗ 0.5 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✓ pass | ✓ 6/6 | fs-s02 |
| fs-05 | holdout | ✗ 0.5 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✓ pass | ✓ 6/6 | fs-s03 |
| fs-06 | holdout | ✓ 1.0 | ✓ 1.0 (rank 1) | ✗ 0.333 | ✓ 0 | – | ✗ pass | ✓ 6/6 | fs-bp, fs-s05, fs-s04 |
| fs-07 | holdout | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ low_coverage | ✓ 6/6 | none |
| bo-01 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ low_coverage | ✓ 2/2 | none |
| bo-02 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ low_coverage | ✓ 2/2 | none |
| bo-03 | holdout | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✓ low_coverage | ✓ 2/2 | none |
| bo-04 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✓ low_coverage | ✓ 2/2 | none |
| bo-05 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✓ low_coverage | ✓ 2/2 | none |
| bo-06 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | ✗ 0.0 | ✓ 0 | – | ✗ pass | ✓ 2/2 | bo-s01 |
| nb-01 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ skipped_first_post | ✓ 1/1 | none |
| nb-02 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✓ skipped_first_post | ✓ 2/2 | none |
| nb-03 | holdout | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ skipped_first_post | ✓ 1/1 | none |
| nb-04 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ skipped_first_post | ✓ 1/1 | none |
| nb-05 | dev | ✗ 0.0 | ✗ 0.0 (rank None) | – | ✓ 0 | – | ✗ skipped_first_post | ✓ 1/1 | none |
| nb-06 | dev | ✓ 1.0 | ✓ 1.0 (rank 1) | ✓ 1.0 | ✓ 0 | – | ✗ skipped_first_post | ✓ 1/1 | nb-bp |
