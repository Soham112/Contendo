# Business block relabel: the baseline for option A

Same 61 quality_v1 cases, same eval data, same pipeline (commit `aa7f56c`, no backend change). Only the labels changed, for option A of `docs/analysis/business-profile-note.md`: the business profile note will reach business posts as a fixed block in the prompt, not through retrieval, so retrieval should no longer be scored on finding it. Before: run `2026-10-16-exact-vector` (old labels). After: run `relabel-baseline` (new labels). Both read-only, $0.

The retrieval output is identical in both runs: no case changed its ranked list or gate decision. Every difference below is the relabel.

## What changed in the labels

- The 27 business cases (re, fs, bo, nb) carry `business_block: true`; no other case does (`quality_fixtures._case_errors` checks both ways).
- `<persona>-bp` was removed from `must_use_all` in 26 of them (fs-02 never required it). No business case may require its note any more (checked).
- 14 business cases now have no required source and leave the recall and MRR means: re-05, re-08, fs-06, fs-07, bo-02, bo-03, bo-04, bo-05, bo-06, nb-01, nb-03, nb-04, nb-05, nb-06.
- In `business_block` cases the note is neutral for precision and off-topic, like consolidation briefs (`quality_metrics._counted`): it will not be retrievable under option A, so it should neither help nor hurt.
- Unchanged: fs-02 keeps the note as `background`; fs-01 and nb-01 keep it as the source of a `needs_present` fact (still true: the fact will be in the block).

## Means, old labels → new labels

| Group | Recall@1 | Recall@3 | Recall@cutoff | MRR | Precision@cutoff | Off-topic rate |
|---|---|---|---|---|---|---|
| dev · verified (32) | 0.453 → 0.656 | 0.547 → 0.812 | 0.567 → 0.812 | 0.633 → 0.740 | 0.646 → 0.542 | 0.097 → 0.102 |
| hold-out · verified (20) | 0.618 → 0.833 | 0.647 → 0.917 | 0.647 → 0.917 | 0.735 → 0.875 | 0.738 → 0.712 | 0.073 → 0.077 |
| me · metadata_only (9) | unchanged | unchanged | 0.938 | 0.792 | 0.613 | 0.071 |

Pass counts, old → new: dev recall 11/25 → 13/16, MRR 16/25 → 12/16, precision 9/20 → 5/16; hold-out recall 9/17 → 11/12, MRR 13/17 → 11/12, precision 7/13 → 7/13. Gate accuracy, off-topic, own share and hybrid reliability counts are unchanged.

## Reading

- Recall and MRR rise because 16 misses of the note leave the metric, not because retrieval improved. This is the baseline the business block is measured against; compare nothing else to `2026-10-16-exact-vector` for business cases.
- Precision falls in dev for two reasons, both real under option A. Four dev cases (bo-02, nb-01, nb-05, nb-06) drafted only the note: they scored 1.0 and now have no countable source, so they leave the mean. In re-04, re-05, re-06 and fs-06 the note was a "good" slot; without it the other drafted sources are judged on their own (re-05 0.40 → 0.25, fs-06 0.20 → 0.00).
- With the note out of retrieval, its slot goes to another chunk; the business-block run measures whether that chunk is a needed source or noise.

## Explicit business gate labels (re-scored 2026-10-16)

The later addition gives every business case expected_gate, including the 14 without required sources. Re-scoring these saved outcomes without changing retrieval yields business gate accuracy **dev 9/17**, **hold-out 5/10**. These replace the earlier claim above that gate accuracy is unchanged: that statement predates the explicit labels. Recall, MRR and precision above remain unchanged. The named comparison artifact is `evals/results/quality_v1/2026-10-16-relabel-baseline/report.md`; full labels and metadata are in `evals/baselines/2026-10-16-business-block.md`.

## Writability revision, step 10 complete

Pillar metadata is now writable_from_profile, true only for the 11 configured evergreen pillars; a request with no pillar behaves as true. nb-04 expects low_coverage; re-05 and fs-06 remain unchanged for Soham to review. Re-scoring saved retrieval preserves all prior retrieval metrics and business gate accuracy (9/17 dev, 5/10 hold-out). The completed $0 business-block comparison, per-case full prompt token counts and source audit are in `2026-10-16-business-block.md`.
