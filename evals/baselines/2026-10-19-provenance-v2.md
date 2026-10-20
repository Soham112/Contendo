# Provenance classifier v2, 2026-10-19

Classifier `provenance_agent` v2 (`provider_author`, byline / interview / evidence rules, two
samples per part), test set v2: 89 sources (77 dev, 12 hold-out written after the v1 baseline;
45 own, 44 external; 7 mixed). Before: `2026-10-19-provenance-v1.md`.
Raw results: `evals/results/provenance/2026-10-19-provenance-v2-{a,b}/` (not committed).

Run B stopped after 81 of 89 sources when the Anthropic credit balance ran out (HTTP 400 on
tc-p01; rejected requests are not billed) and was finished with `--resume` after credits were
added ($0.061 for the last 8).

| | Run A | Run B | Target |
|---|---|---|---|
| Measured spend | $0.6555 (185 calls) | $0.6804 (191 calls) | estimate $0.62, cap $1 each |
| Source labels correct | 88 / 89 | 88 / 89 | |
| Outside text applied as own (confident) | 0 | 0 | 0 |
| Own applied as external (confident) | 0 | 0 | 5% or less |
| Applied automatically | 0.483 (hold-out 0.333) | 0.393 (hold-out 0.417) | 0.80 or more |
| Mixed-paragraph recall | 1.00 | 1.00 | |
| Run agreement (label, confident, paragraphs) | 0.697 | | 0.95 or more |
| Same paragraph labels in both runs | 87 / 89 | | |

Against v1: labels 72-71/73 to 88/89 in both runs. Signed first-person posts by others (tc-p03,
rf-p18, ni1-p04, rf-p02, rf-p03, rf-p14) are external in every sample, except **tc-p07** (fresh
hold-out) in run A: one sample took the body as the user's own and only the signature as
external, the v1 tc-p03 mistake. The other sample disagreed, so the result was external and not
confident: the two-sample rule caught what the byline rule missed (run B: both samples external).
Interviews: tc-p06 external in A, correct in B; re-p05 correct in A, external in B; each wrong
one not confident, so the user would be asked.

## What still fails, with evidence

1. **Citing a fact that is absent (main cause, again).** 86 of 112 not-confident reasons across
   both runs. The rename did not change it: the model cites `provider_author` when it is "not
   reported", reasoning from its absence ("a personal note with no publisher"). The check counts
   that as citing a fact that was not given. Without this one reason, 78/89 (A) and 77/89 (B)
   would be confident, with 0 outside paragraphs applied as own, and run agreement 0.831.
2. **Schema failures.** 3 (A) and 4 (B) samples gave no valid answer after the retry, almost all
   `uncertain: bool_parsing` (the model writes something other than true or false). The raw
   reply is not kept, so what it wrote is unknown.
3. **No evidence.** 7 results across both runs cite no quote and no fact (mostly external
   summaries such as rf-s12 and rf-s16).
4. **Interviews.** As above: labelled external, not confident.
