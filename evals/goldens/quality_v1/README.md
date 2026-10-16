# Quality test set v1

The multi-persona test set for `docs/QUALITY.md`. Separate from `goldens/goldens.jsonl` and `fixtures/personas/`, so existing runs and `seed.py --check` are unchanged.

- `cases.jsonl`: one labelled case per line (52 synthetic cases). Persona `me` (9 cases, Soham's real library) lives in `evals/private/quality_v1/` (gitignored: the repo is public): `me_cases.jsonl`, `me_sequence.json`, `me/snapshot.json`.
- `sequences.json`: per persona, an ordered list of 6–8 topics to generate in a row (criteria 34–35, pillar variety).
- `personas.json`: the data situation each persona covers.
- Fixtures: `fixtures/quality_v1/personas/<slug>/` with `profile.json` (or `null`), `account.json` (segment, niche, business profile, as `PUT /account/segment` saves it), `experience_nodes.json`, `posts.json`, `sources/*.md` (same header format as `fixtures/personas`).

## Personas are a measuring tool

Design decisions come from the spec's principles, never from tuning to a case. The personas cover **data situations**, not job titles:

| Persona | Identity | Library size | Own share | Topic coverage in cases | Phrasing in cases | Distractors | Split |
|---|---|---|---|---|---|---|---|
| rf · rich founder | person | large (20) | 50% | full, partial, none | project, vague, broad | high, near-miss per own project | dev, 1 hold-out case |
| tc · thin consultant | person | small (6) | 17% | full, partial, none | project, vague, broad | medium | **hold-out persona** |
| ni0 · new user, Tier 0 | person | empty, no profile | – | none | vague, broad | none | dev |
| ni1 · new user, Tier 1 | person | 1 (onboarding story) | 100% | full, partial, none | project, vague, broad | none | dev, 1 hold-out |
| me · Soham, real | person | large real (51) | ~35%, mostly unlabelled | full, outside-only, none | project, vague, broad | high + real mislabels | dev, 1 hold-out |
| re · real estate | business | medium (9 + profile) | 67% | full, partial, none | project, broad | high | dev, 1 hold-out |
| fs · fitness studio | business | small (5 + profile) | 60% | full, partial, none | broad | medium | **hold-out persona** |
| bo · niche "other" | business | 1 + thin profile | 100% | full, none | broad | none | dev, 1 hold-out |
| nb · new business | business | profile note only | 100% | full (via pillar_details), none | broad | none | dev, 1 hold-out |

Split across all 61 cases: 40 dev, 21 hold-out (34%). Score hold-out only at the end of a step; a change that improves dev but not hold-out doesn't ship.

**Gaps (no persona yet, add when they matter):** a large business library (e.g. after a website import; not built), a person with both a personal and a business identity (spec §5; code has one segment per account), a library that is mostly own posts imported from LinkedIn (import not built), a non-English user.

**Refresh.** The set is versioned (`quality_v1`). Add a case when production shows a failure the set doesn't cover (as trace 3e9ebb02 became `me-01`), and add a persona before marketing to a new segment.

## Case fields

`id, persona, split (dev|holdout), identity (person|business), topic, context, pillar, pillar_details, tone, objective, authority (high|low), cold_start_tier (0-3), phrasing (names_project|vague|broad), coverage (full|partial|none), evidence (first_person|outside_only|business_facts|none), must_use_all, must_use_any, background, off_topic, central_idea, eligible_angles, ineligible_angles [{angle, reason}], needs_present [{fact, source}], needs_missing, do_not_claim, note, label_confidence (verified|metadata_only)`.

`must_use_all`: every source is needed. `must_use_any`: one of them is enough (a group of two or more). `label_confidence`: `verified` when written from the full source text (all synthetic cases), `metadata_only` when proposed from titles and metadata (persona `me`); metadata_only angle labels are never a hard fail (see `docs/QUALITY.md`).

Source ids are file stems (`rf-s03`), `<persona>-bp` for the business profile note created at seed time, `nb-details` for the note `pillar_details` creates at request time, and `me:<prefix>` for persona 4 (resolved in `evals/private/quality_v1/me/snapshot.json`).

## Running it

Seeding, the `me` export and the retrieval scorer are described in `evals/README.md` ("Quality test set v1"). Loader: `evals/quality_fixtures.py`; B1 scorers: `evals/quality_metrics.py`. The production user for `me` is found from the owner of the labelled sources, so no user id is stored.
