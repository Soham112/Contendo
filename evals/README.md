# Offline evals

Runs the real Contendo pipeline against a separate Supabase project (contendo-dev,
same schema as production via `backend/migrations/000_baseline_schema.sql`), using
three fictional personas. This folder covers setup, seeding and reset. Running
goldens and judging come later.

## Safety model

Evals spend real API credits and write to a real database, so every entry point
checks where it is pointed before doing anything.

- **It only ever talks to the eval project.** `evals/env.py` runs first in every
  script. It reads `evals/.env` and stops unless `EVAL_SUPABASE_URL` is exactly
  `https://<EXPECTED_PROJECT_REF>.supabase.co`. A production URL, a look-alike
  host, or a missing ref all stop the run.
- **It never reads `backend/.env`.** The backend calls `load_dotenv()` when it is
  imported, and that call finds `backend/.env` from anywhere. `env.py` replaces
  `load_dotenv` with a no-op before any backend code is imported, then sets every
  environment variable the backend reads, so nothing is left for a `.env` file to
  fill in. If backend code was imported before `env.py`, it refuses to start.
  `seed.py` and `reset.py` check again that the backend's Supabase client was
  built with the eval URL before using it.
- **`evals/.env` accepts only known keys.** An unprefixed `SUPABASE_URL` or a typo
  is refused rather than ignored.
- **Claude calls use only the key in `evals/.env`.** The guard checks the key's
  format without printing it, and removes `ANTHROPIC_BASE_URL` and
  `ANTHROPIC_AUTH_TOKEN` from the environment so requests go to the Anthropic API
  and nowhere else. Before writing, `seed.py` confirms Anthropic accepts the key
  with a free token-count request.
- **Seeding only writes to real eval users.** `seed.py` checks that every persona
  uuid exists in the eval project's `auth.users` before it writes anything.
- **Reset only deletes eval users' rows.** `reset.py` deletes rows whose user id is
  one of the uuids in `fixtures/users.json`, in every table of the baseline schema
  that has a user id. It refuses any other id, shows row counts, and asks you to
  type the project ref before deleting. Auth users are kept.
- **No telemetry.** `DEEPEVAL_TELEMETRY_OPT_OUT=YES` and `DEEPEVAL_DISABLE_DOTENV=1`
  are set, and there is no Confident AI login.

## Setup

1. In contendo-dev, create three auth users (Authentication > Users > Add user),
   one per persona. Put their uuids in `fixtures/users.json`:
   ```json
   { "ds": "<uuid>", "pm": "<uuid>", "founder": "<uuid>" }
   ```
2. `cp evals/.env.example evals/.env` and fill in the eval project's URL, its
   service-role key, an Anthropic key, and the project ref.
3. Install the eval extras into the backend venv (never into
   `backend/requirements.txt`):
   ```bash
   backend/venv/bin/pip install -r evals/requirements.txt
   ```

## Seed

Run from the repo root:

```bash
backend/venv/bin/python evals/seed.py --check    # validate fixtures, goldens and auth users; writes nothing
backend/venv/bin/python evals/seed.py            # seed all personas (asks first)
backend/venv/bin/python evals/seed.py --persona ds --yes
```

For each persona, seeding saves the profile and experience nodes, ingests every
source with its `memory_context`, and adds the seed posts (so `first_post` is
False). It is safe to re-run: unchanged sources come back as duplicates and cost
nothing, and posts are matched by topic. If you edit or remove a source, the old
version stays in the database and seed warns about it. Reset that persona, then
seed again.

New sources cost roughly $0.01–0.03 each in Claude calls (tags, summary,
entities, and consolidation when an entity reaches 3 sources).

## Reset

```bash
backend/venv/bin/python evals/reset.py                 # all eval personas
backend/venv/bin/python evals/reset.py --persona pm    # one persona, by slug or uuid
```

## Run, judge, report

From the `evals` folder, with the backend venv active:

```bash
python run.py --quality standard --only pm-01     # one golden; drop --only for all 24 (asks first)
python judge.py <run_id>                          # DeepEval metrics, cached in scores.jsonl
python report.py <run_id>                         # writes and prints results/<run_id>/report.md
```

- `run.py` calls `run_pipeline` as the golden's persona and writes `runs.jsonl`:
  trace id, timing, and the pipeline's Claude calls and cost from the trace. A golden
  whose trace was not saved, or whose run raised, is logged and skipped.
- `judge.py` builds test cases from each `generation_traces` row and does not re-run
  the pipeline. The judge calls Claude through `llm.client.complete()` with
  `event_type="eval_judge"`. Set the judge model in `eval_config.py`
  (`JUDGE_MODEL = "HAIKU"` or `"SONNET"`). A (golden, metric, judge model) that
  already has a result is never judged again.
- Metrics: answer relevancy, contextual relevancy (skipped when retrieval returns
  nothing), faithfulness and `unsupported_specifics` (both judged against the
  retrieved chunks plus the author profile), and `source_recall` (deterministic;
  skipped for goldens that expect no sources). Thresholds are in `eval_config.py`.
- One `standard` golden cost about $0.03 for the pipeline and $0.04 for a Haiku judge.
- Second-opinion judge: `python judge.py <run_id> --judge-model SONNET --only <golden_id> ...`
  writes `scores-sonnet.jsonl` (each judge model has its own file), then
  `python report.py <run_id> --judge-model HAIKU --compare SONNET` writes a side-by-side table.
- One metric from another judge: `python judge.py <run_id> --judge-model SONNET --metric unsupported_specifics`
  judges only that metric with Sonnet, then `python report.py <run_id> --metric-judge unsupported_specifics=SONNET`
  writes `report-mixed.md` (Haiku for the rest).
- `run.py` runs each post's background (log-only) fact check after the timing stops and saves its flags in
  `runs.jsonl`; the report lists them under "Background fact-check flags". They are leads, not verdicts: the
  find-prompt over-flags paraphrases.
- Out of credits, a bad key or a forbidden key stops `judge.py` at the first failure (and
  `run.py`/`judge.py` refuse to start when the account is out of credits). Re-run after fixing
  it: finished results stay cached and errored ones are retried.

## Ablation (pipeline variants)

Variants are `A`, `B`, `C`, `B-Opus` and `C-Opus` (`backend/config/features.py`; models per role in
`backend/llm/models.py`). The judge model and its settings are the same for every variant.

The full ablation is one command, under one spend cap:

```bash
python ablate.py --name full          # shows the plan and the cap, asks first
```

It runs the full ablation's variants (`eval_config.ABLATION_VARIANTS`: A, C, B-Opus, C-Opus; B is left out),
judges `unsupported_specifics` (Sonnet) and answer relevancy (Haiku), runs the review regression set once and
writes `results/ablations/full/ablation.md`, which opens with the decision rules fixed before the run
(`eval_config.DECISION_RULES`). It does not run the instrument.
`EVAL_SPEND_CAP_USD` in `eval_config.py` (14) caps the whole thing: measured cost is added to
`results/ablations/full/spend.json` after every post, and the step in progress stops before its next post once
the cap is reached and says where. `--spend-cap` overrides the cap; running the command again reuses the runs
already made and continues the judging.

The steps can also be run one at a time (add `--ablation <name>` to each to put them under the same cap):

```bash
python run.py --quality standard --variant A --only pm-05 ...     # one run per variant
python judge.py <run_id> --judge-model SONNET --metric unsupported_specifics
python judge.py <run_id>                                          # full run only: the Haiku metrics
python instrument.py <run_id>                                     # review of the final posts (calls Claude for A and C)
python report.py --variants <run A> <run B> <run C> <run B-Opus> --name smoke
python blind.py audit smoke     # audit.md: mark 10 judge findings correct / wrong
python blind.py make smoke      # read.md: rank four posts per golden, blind
python blind.py score smoke     # then re-run report.py --variants to add both to ablation.md
python review_regression.py     # the review development set on REVIEW_MODEL; not part of the decision
```

- Everything lands in `results/ablations/<name>/`: `ablation.md`, `ablation.json` (the runs), `audit.md`,
  `audit-key.json`, `read.md`, `key.json`, and after `score`, `audit.json` and `blind.json`.
- `instrument.py` is record-only and uses the reviewer B was fixed against, so it is biased in B's favour.
- Below 8 of 10 audited findings correct, `ablation.md` labels `unsupported_specifics` unreliable.
- `PIPELINE_VARIANT` may be set in `evals/.env` as the default for `run.py`; an unknown value stops every script.
- Costs everywhere come from `backend/llm/pricing.py`.

### Phase 1: the latency experiment

`python ablate.py --name phase1 --spend-cap 3.5` runs the plan in `eval_config.PHASE1_PLAN`: C-Opus (today)
against D-Opus (structure folded into the Opus call) and D-Opus-low (the same at effort low; Opus 5.5 cannot turn
thinking off) on the full ablation's 10 blind-read goldens, once each, with the same two judges and no review
regression set. The runs are interleaved: golden by golden, the three arms in a seeded random order per golden
(`run.run_interleaved`), and the report checks per golden that every arm drafted from the same inputs. Then `python blind.py make phase1`, rank the three posts per golden in `read.md`,
`python blind.py score phase1` and `python report.py --variants <the three run ids> --name phase1`.
`ablation.md` opens with the rules fixed before the run; any other ablation name keeps the full ablation's plan.

## Known retrieval gaps

- **pm-04** ("How to say no to sales without becoming the villain"): the knowledge base
  covers it ("Saying no to a sales-driven feature request"), but the topic and the
  source use different words, so the best chunk scores cosine 0.24 and BM25 0.09 and
  the coverage gate blocks it (`low_coverage`). The right source is listed as the
  closest one. Candidate fix: query rewriting (expand the topic into the vocabulary
  the user's notes use) before retrieval.

## Editing fixtures and goldens

- `fixtures/personas/<slug>/sources/*.md`: one source per file. A header block
  sets `title`, `source_type` and `memory_context`, and the body is what gets
  ingested.
- `fixtures/personas/<slug>/profile.json`, `experience_nodes.json`, `posts.json`.
- `goldens/goldens.jsonl`: one golden per line, with fields `id`, `persona`,
  `difficulty` (`rich`, `sparse` or `off_topic`), `topic`, `context`, `format`,
  `tone`, `length`, and `expected_source_titles` (each must match a source title
  exactly). Optional: `expected_perspective` (`experience`, `learned`, `opinion`
  or `mixed`), the perspective the pipeline should decide for that golden; it is
  stored in the trace as `node_outputs.perspective`. Optional: `note`, a comment
  explaining the golden.

After editing, run the tests. They validate every fixture and golden:

```bash
cd evals && ../backend/venv/bin/python -m pytest
```

These tests need no network and no `.env`, and never import backend code.

## Quality test set v1 (retrieval baseline)

The multi-persona set for `docs/QUALITY.md`: 8 synthetic personas plus persona `me`
(Soham's production library, kept in gitignored `evals/private/`). Separate users
(`fixtures/quality_v1/users.json`), fixtures and cases (`goldens/quality_v1/`), so
the goldens above are unchanged. Run from the repo root:

```bash
backend/venv/bin/python evals/quality_seed.py --estimate          # expected Claude cost; writes nothing
backend/venv/bin/python evals/quality_seed.py --create-users      # one eval auth user per persona (free)
backend/venv/bin/python evals/quality_export_me.py                # read-only production export to evals/private/
backend/venv/bin/python evals/quality_seed.py --persona me        # load that export (no Claude calls)
backend/venv/bin/python evals/quality_seed.py                     # seed the synthetic personas (asks; --spend-cap 1.00)
backend/venv/bin/python evals/quality_retrieval.py --name baseline  # B1 retrieval scores, no draft call
backend/venv/bin/python evals/reset.py --quality                  # delete the quality personas' rows
```

- Business personas are seeded the way `PUT /account/segment` saves them, so the
  profile note is built and ingested by the real code.
- `quality_export_me.py` reads production through a select-only client and never
  imports backend code; the eval import copies rows as they are today (provenance
  `copied_from_production_chunks`), flaws included.
- Seeding and the retrieval run refuse to start unless `usage_events.model` exists
  (migration 006): the spend cap prices calls from it.
- `quality_retrieval.py` runs the pipeline's `load_profile` and `retrieval` nodes per
  case and observes keyword search from the eval side; the backend is unchanged.
  It writes nothing: a case with `pillar_details` (re-02, nb-02) runs as its own eval
  user, seeded as its persona plus that note, so no case changes a library another reads.
  A dropped connection (or a silent fallback off the hybrid path) retries the case up
  to 3 times; `attempts` is in each row.
- Spend is read from `usage_events`. Scripts have no server event loop, so the backend
  would skip those writes; `UsageLog` runs one on a background thread for the run.
  Reports go to `results/quality_v1/<name>/`; persona `me`'s per-case rows to
  `private/quality_v1/results/<name>/`.

## Provenance classifier (step 3.3)

```bash
backend/venv/bin/python evals/provenance_eval.py --check       # validate labels; $0
backend/venv/bin/python evals/provenance_eval.py --estimate    # expected cost; $0, no network
backend/venv/bin/python evals/provenance_eval.py --run --name <date>-<label>   # paid, asks first, --spend-cap 1.00
backend/venv/bin/python evals/provenance_eval.py --rescore <name> --agreement-with <other name>
```

- Cases: every quality_v1 source (its `authorship` header) and `fixtures/provenance_v1/<persona>/*.md`,
  hard cases for the classifier only, never seeded. The persona's profile, account and experience
  nodes are the user's details. Hold-out: the provenance_v1 cases marked `split: holdout`, written after the
  2026-10-19 baseline; every quality_v1 source and the first hold-out (read to diagnose that baseline) are dev.
- The classifier runs on the fixture text: no database, no embeddings. Adding `authorship` headers
  does not change any fixture's text, so the seeded eval users stay as they are.
- Scores (`provenance_metrics.py`): the worst error is an outside paragraph applied as the user's
  own without asking (target 0); own sources applied as external (5% or less); share applied
  automatically (80% or more); run agreement between two runs (95% or more).
