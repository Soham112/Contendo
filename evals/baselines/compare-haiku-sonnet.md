# Judge comparison: HAIKU vs SONNET · 20261001-041214-standard

Goldens judged by both: ds-07, ds-08, founder-04, pm-04, pm-07, pm-08

| metric | n | mean HAIKU | mean SONNET | pass HAIKU | pass SONNET | verdicts differ |
|---|---|---|---|---|---|---|
| answer_relevancy | 6 | 0.61 | 0.49 | 50% | 50% | – |
| contextual_relevancy | 6 | 0.15 | 0.10 | 17% | 17% | – |
| faithfulness | 6 | 0.96 | 0.90 | 100% | 100% | – |
| unsupported_specifics | 6 | 0.87 | 0.62 | 83% | 33% | ds-08, founder-04, pm-08 |
| source_recall | 2 | 0.50 | 0.50 | 50% | 50% | – |

## Per golden

| golden | answer_relevancy | contextual_relevancy | faithfulness | unsupported_specifics | source_recall |
|---|---|---|---|---|---|
| ds-07 | 0.00 / 0.00 | 0.00 / 0.00 | 1.00 / 0.96 | 1.00 / 0.80 | – |
| ds-08 | 1.00 / 0.95 | 0.00 / 0.00 | 1.00 / 0.91 | 0.90 / 0.40 ⚠ | – |
| founder-04 | 1.00 / 0.96 | 0.92 / 0.58 | 1.00 / 0.91 | 0.90 / 0.60 ⚠ | 1.00 / 1.00 |
| pm-04 | 0.65 / 0.00 | 0.00 / 0.00 | 1.00 / 1.00 | 1.00 / 0.90 | 0.00 / 0.00 |
| pm-07 | 0.00 / 0.00 | 0.00 / 0.00 | 0.93 / 0.80 | 0.50 / 0.40 | – |
| pm-08 | 1.00 / 1.00 | 0.00 / 0.00 | 0.85 / 0.82 | 0.90 / 0.60 ⚠ | – |

Cells are HAIKU / SONNET; ⚠ marks a pass/fail disagreement.

Judge cost on these goldens: HAIKU $0.2630 · SONNET $0.9233
