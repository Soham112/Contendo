# LLM unit-cost estimate before publish-paywall launch

Prepared 2026-10-13. This is an estimate from real recorded token usage, not fake-test token counts and not a live-provider benchmark of the new grounding gate. No database, live model generation, Stripe API or publishing provider was called for this estimate.

## Measured evidence

Both cohorts were recorded at commit `2f19bb1`, before final grounding and before the trim-to-compression change:

- `evals/results/20261010-215033-standard-C-Opus/runs.jsonl`: 20 completed C-Opus posts. Mean **$0.055392/post**, measured range **$0.037025–$0.081281**; mean 5947 input and 1814 output tokens per post. One of 20 posts used the historical trim.
- `evals/results/20261010-213125-standard-B-Opus/runs.jsonl`: 20 completed B-Opus posts, used only as a measured proxy for the review call shape.

| Model / measured role | Calls | Mean input/call | Mean output/call | Mean cost/call |
|---|---:|---:|---:|---:|
| Opus 5.5 / C drafting | 20 | 4579.80 | 1775.55 | $0.053830 |
| Haiku 4.5 / C structure plus historical trim | 21 | 1302.38 | 36.95 | $0.001487 |
| Sonnet 4.6 / B review | 137 | 4819.27 | 482.07 | $0.021689 |

Base prices match `backend/llm/pricing.py`: Opus 5.5 $4 input/$20 output, Sonnet 4.6 $3/$15, Haiku 4.5 $1/$5, per million tokens. Thinking tokens are included in output, not added a second time. These base rates were checked against [Anthropic's official pricing](https://platform.claude.com/docs/en/about-claude/pricing) on 2026-10-13. No prompt-cache, batch or fast-mode discounts are assumed.

## Projection for the implemented pipeline

C-Opus remains the default. Add one Sonnet grounding check to every completed post, and up to two Opus source-only repairs, each followed by another check. As a planning proxy, use the measured Sonnet review call average and measured C Opus draft average above. Whole-post grounding has a different schema from the historical grouped review, so this proxy must be validated from `grounding_check` and `grounding_repair` usage events after launch.

Compression now uses the draft model. At the historical 1/20 over-limit frequency, replace one average Haiku call with an average Opus call: **+$0.002617/post**. The historical Haiku figure pools structure and trim calls, and Opus drafting is a proxy for compression, so this adjustment is modeled, not an exact compression measurement.

Clean-post estimate = $0.055392 + $0.002617 + $0.021689 = **$0.079698/post**. Each repair-plus-recheck adds approximately **$0.075519**.

| Scenario | LLM cost/post | 300 posts/month | Remainder of $39 before other costs |
|---|---:|---:|---:|
| Historical C-Opus, no final grounding | $0.0554 | $16.62 | $22.38 |
| New pipeline, no grounding repairs | $0.0797 | **$23.91** | **$15.09** |
| 10% need one repair | $0.0872 | $26.17 | $12.83 |
| 10% need both repairs | $0.0948 | $28.44 | $10.56 |
| Every post needs both repairs, at historical call sizes | $0.2307 | $69.22 | $-30.22 |

The new clean-post estimate uses 61.3% of $39 revenue. This remainder is **not profit**: it excludes Zernio account/publishing fees, Stripe processing/taxes, Supabase/Vercel/Railway, source ingestion and summarization, ideas, selection rewrites, scoring, visuals, free users, failed generations, support and refunds. Approving the unchanged final text reuses its grounding result; editing before approval adds a fresh check. Reopening an unchanged review does not add a model call.

The all-repair row is a workload scenario, **not a maximum bill**. Prompt sizes and output length vary, structured-output validation can retry a check, transport retries are allowed, and the recorded cohorts omit failed generations without complete usage. A bounded repair count is not a dollar cap. At full 300-post usage the $39 price leaves limited room for external account fees even without many repairs; verify the actual provider bill and new repair distribution before treating the plan as profitable.

## Reproduce the measured baseline

Read only records with `status == "ok"` and a `pipeline` field. Mean `pipeline.cost_usd` over the C-Opus cohort; for per-model means, sum `pipeline.by_model[model].input_tokens`, `output_tokens` and `cost_usd`, then divide by summed `calls`. These JSONL files contain actual SDK usage captured by the ablation, and stay ignored because they contain source/post data. Report only aggregates. No token usage from unit-test fakes was used.
