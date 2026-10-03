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
- Out of credits, a bad key or a forbidden key stops `judge.py` at the first failure (and
  `run.py`/`judge.py` refuse to start when the account is out of credits). Re-run after fixing
  it: finished results stay cached and errored ones are retried.

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
  exactly).

After editing, run the tests. They validate every fixture and golden:

```bash
cd evals && ../backend/venv/bin/python -m pytest
```

These tests need no network and no `.env`, and never import backend code.
