# Provenance classifier baseline, 2026-10-19

Classifier `provenance_agent` v1 (Haiku 4.5, structured), test set provenance v1: 73 sources
(56 dev, 17 hold-out; 37 own, 36 external; 4 mixed). Two identical runs, for run agreement.
Raw results: `evals/results/provenance/2026-10-19-provenance-v1-{a,b}/` (not committed).

| | Run A | Run B | Target |
|---|---|---|---|
| Measured spend | $0.2504 (74 calls) | $0.2595 (76 calls: 3 schema retries) | estimate $0.24, cap $1 each |
| Source labels correct | 72 / 73 | 71 / 73 | |
| Outside text applied as own (confident) | 0 | 0 | 0 |
| Own applied as external (confident) | 0 / 37 | 1 / 37 (rf-p09) | 5% or less |
| Applied automatically | 0.329 | 0.384 | 0.80 or more |
| Mixed-paragraph recall | 1.00 | 0.80 | |
| Run agreement (label, confident, paragraphs) | 0.726 | | 0.95 or more |

Dev, both runs: every source label correct (precision and recall 1.00).

## What went wrong, with evidence

1. **"author" in `source_facts_used` is ambiguous (main cause of low confidence and of disagreement).**
   88 of 95 not-confident reasons across both runs are "cited a source fact that was not given":
   the model lists `author` to mean the text's byline or authorship in general, while the field
   means the creator a provider names (a YouTube channel), which most sources don't have.
   tc-p03 run B: "no author given in the source facts", yet `source_facts_used: ["author"]`.
   Whether a case trips this is random, so most disagreements between runs are this flag.
   Ignoring that one reason would give 69 / 73 (A) and 70 / 73 (B) confident.

2. **A wrong answer can pass every structural check (hallucination risk).** tc-p03 (hold-out:
   another consultant's first-person SMED post, signed "Martina Lopez") in run B: labelled the
   body the user's own because the topic matches Jonah's work, and only the signature paragraph
   external. Its quotes were real. It was not applied only because of the ambiguous `author`
   citation above; with that fixed alone, it would have been applied as the user's own. Run A
   labelled the same text external. Structural checks cannot catch a confident, well-quoted
   wrong reading; the two runs disagreeing can.

3. **Interviews: the user's own answers labelled external.** rf-p09 (hold-out: podcast where Dara
   is interviewed) labelled external in both runs ("a transcript produced and published by Support
   Leaders Podcast"), confidently in run B. Safe direction (no first-person claim), but a miss.

4. **Quotes taken from the user's details instead of the text.** rf-s05 run A quoted "Led the
   Ledger migration to an event log.", which is from the experience context; the quote check caught
   it. 6 such reasons in total.

## Hold-out is now seen

Failures 2 and 3 are hold-out cases, read here to diagnose them. A fix informed by them is tuned
on hold-out, so the next measurement needs new dev cases of the same kinds and fresh hold-out cases
written before the re-run.

## Follow-up (same day): classifier v2 and test set v2, not measured yet

- `author` fact renamed `provider_author`, shown as "the channel or site that published it" (cause 1).
- Three prompt rules: a byline or signature naming someone else covers the whole text it signs;
  the user's words in an interview are theirs, the other speakers' are external; evidence comes
  from the text only (causes 2, 3, 4).
- Confidence needs two parallel samples to agree on every paragraph; where they disagree, a
  paragraph either calls external is external (cause 2: structural checks pass a well-quoted
  wrong reading).
- Test set: 4 dev cases of the failure kinds (rf-p18, ni1-p04, re-p05, rf-p19); the first
  hold-out moved to dev; 12 fresh hold-out cases written before any run on them.
