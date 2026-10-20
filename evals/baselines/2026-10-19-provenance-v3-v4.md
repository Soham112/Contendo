# Provenance classifier v3 and v4, 2026-10-19

One run each (run agreement not measured: both samples of every source must already agree
before a result is applied). Before: `2026-10-19-provenance-v2.md`.
Raw results: `evals/results/provenance/2026-10-19-provenance-{v3-a,v4-a}/` (not committed).

- **v3**: `reading_schema(facts)` offers only the source facts that have a value; a failed
  sample's replies are kept on `Provenance.failures`. Test set v2 (89 sources: 77 dev, 12 hold-out).
- **v4**: adds `signed_by` (after reasoning, before the label). Code marks a reading not confident
  when the signature is not in the text, or when it does not contain the user's full name or their
  business's full name while some paragraph is labelled the user's. Test set v4: 95 sources (84 dev,
  11 hold-out; 48 own, 47 external; 9 mixed). Changes: six new dev signature cases (rf-p23, rf-p24,
  ni1-p07, ni1-p08, re-p07, re-p08); tc-p07 moved to dev (read to diagnose v3); rf-p16 P1 relabelled
  as the user's own.

| | v3 | v4 | Target |
|---|---|---|---|
| Measured spend | $0.7042 (198 calls) | $0.7607 (201 calls) | estimate $0.62 / $0.69, cap $1 each |
| Source labels correct | 86 / 89 | 92 / 95 | |
| Outside text applied as own (confident) | **2 sources** (tc-p07 whole, rf-p16 P1) | 0 | 0 |
| Own applied as external (confident) | 0 | 0 | 5% or less |
| Applied automatically | 0.899 (dev 0.935, hold-out 0.667) | 0.884 (dev 0.893, hold-out 0.818) | 0.80 or more |
| Mixed-paragraph recall | 1.00 | 0.917 | |
| Samples with no valid answer | 3 | 0 | |

Against v2: applied automatically 0.48 / 0.39 to 0.90 (v3). The fix to absent facts removed v2's main
not-confident reason, and with it an accidental check: in v2 run B, tc-p07 was kept from being
applied only because a sample cited an absent fact (run A: that, plus disagreeing samples).

## v3 misses, with evidence

1. **tc-p07** (someone else's first-person post, signature "Ravi Mehta, lean coach" alone on the last
   line). Both samples labelled paragraphs 1-3 the user's and only the signature paragraph external,
   with quotes that were in the text, so the result was confident. One sample named the signature
   as "a different person" in its reasoning. The prompt already said a signature covers the whole
   text: the rule was there, the model did not apply it.
2. **rf-p16 P1** ("Read the Andreessen piece on AI in customer support this morning."). Both samples
   called it the user's own line. That is a true statement of the user's own action, not a summary
   of the article, so the fixture was relabelled (external source, P1 own). The note is one chunk,
   so `chunk_labels` keeps the chunk external: no first-person claim reaches a post.

## v4 results

- tc-p07: both samples still labelled the body the user's, but both named the signature, so the
  code check made it not confident (asked, never applied). **The check, not the model's reading,
  stops this case.** rf-p23 and ni1-p07 (other signed posts) were caught the same way, and were also
  uncertain or had disagreeing samples.
- True negatives: ni1-p08 (signed with the user's full name) and re-p07 (signed "The Fernleigh Homes
  team") were applied as own. re-p08 (another agency's sign-off) was applied as external. rf-p24
  (the user's note ending with a quotation attributed to someone else) was applied as own with the
  quotation paragraph external: the attribution was not taken as a signature.
- False trigger: rf-p15 (the user's own retro, input type file). One sample gave its title
  ("Gullwing two-year retro") as `signed_by`, so it was not confident. That cost one automatic label
  and no wrong one.
- rf-p16 P1: the samples disagreed, so it resolved to external (the safe side) and was not confident.
- Interviews: tc-p06 and re-p05 resolved to external, not confident (asked), as in v2.
- Not-confident reasons (11 sources): samples disagree 5, signature check 4, uncertain 3, quote not
  in the text 2, no evidence 1. Three samples needed the structured retry (`uncertain: bool_parsing`);
  all succeeded on it.

## Before anything reads `authorship`

- The hold-out has 11 sources, and tc-p07 is no longer in it. Adding new hold-out cases (written by
  someone other than whoever tunes the prompt) would make the next measurement independent.
- Run agreement was not measured for v3 or v4.
