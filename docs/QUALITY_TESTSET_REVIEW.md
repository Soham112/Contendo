# Quality test set v1: labels for review

Generated from `evals/goldens/quality_v1/cases.jsonl` (edit that file, not this one). 61 cases: 40 dev, 21 hold-out (34%).


## rf: persona 1 · individual · large (20 sources) · dev (rf-09 held out)

Sources: `rf-s01` Why we started Sieve · `rf-s02` The refund-policy regression Sieve missed · `rf-s03` Brightline Insurance pilot results · `rf-s04` Moving Sieve from per-seat to usage pricing · `rf-s05` The Ledger migration at Pellucid Logistics · `rf-s06` Gullwing: a side project that taught me docs-first · `rf-s07` Hiring Quillmark's first engineer · `rf-s08` I changed my mind about LLM-as-judge · `rf-s09` Belief: evals are product specs · `rf-s10` Raising Quillmark's pre-seed · `rf-s11` LLM-as-a-judge: a survey of known biases · `rf-s12` Event sourcing patterns for financial systems · `rf-s13` Talk: building eval harnesses for RAG systems · `rf-s14` Evalyze raises 20 million dollar Series A for LLM testing · `rf-s15` The state of customer support automation 2026 · `rf-s16` Usage-based pricing for AI products · `rf-s17` How to run a Series B process · `rf-s18` Observation: every AI demo shows the happy path · `rf-s19` Hiring your first engineers · `rf-s20` Autoscaling Kubernetes for GPU inference


### rf-01 · What the Brightline pilot taught us about deflection

person · objective lesson · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** Weekly eval-and-fix cycles, not the score, moved Brightline from 18% to 31% resolution; the week-3 'claim' refusal is the turning point.
- labels: verified
- must_use_all: `rf-s03` · must_use_any: none · background: `rf-s01`, `rf-s09` · off_topic: `rf-s15`, `rf-s14`, `rf-s13`
- eligible: case_study, unexpected_result, before_after, analysis, how_to
- ineligible: prediction (nothing forward-looking in the evidence)
- do not claim: industry figures from rf-s15 presented as Brightline's or Quillmark's; any Brightline number other than 22 agents, 18%, 31%, six weeks; a quote from Marisol beyond what rf-s03 says

### rf-02 · The bug our evals didn't catch

person · objective lesson · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** The eval passed at 94% because the golden set sampled what was easy to label, not what customers ask; sampling is the eval.
- labels: verified
- must_use_all: `rf-s02` · must_use_any: none · background: `rf-s09`, `rf-s13` · off_topic: `rf-s11`, `rf-s14`, `rf-s15`
- eligible: mistake_lesson, failure_to_realization, confession, personal_story, how_to
- ineligible: prediction (no forward-looking evidence)
- do not claim: the regression was caught by the eval; a number of affected customers; RAG metrics from rf-s13 as Quillmark's practice

### rf-03 · Why I changed my mind about LLM-as-judge

person · objective lesson · authority high · tier 3 · phrasing broad · coverage full · evidence first_person

- **Central idea:** A model judge agreed with humans about as often as humans agreed with each other, so Dara now uses one, but only with a weekly 10% human audit.
- labels: verified
- must_use_all: `rf-s08` · must_use_any: none · background: `rf-s11` · off_topic: `rf-s13`, `rf-s14`
- eligible: changed_my_mind, before_after, framework, unexpected_result
- ineligible: mistake_lesson (no failure event; the old view was not acted on to harm)
- do not claim: survey findings from rf-s11 presented as Quillmark's measurements; agreement figures other than 86% and 88%

### rf-04 · What I learned this year

person · objective reflection · authority high · tier 3 · phrasing vague · coverage full · evidence first_person

- **Central idea:** One lesson from 2026 grounded in one own event (eval sampling, pricing notice period, or the judge audit), not a recap of all of them.
- labels: verified
- must_use_all: none · must_use_any: `rf-s02`, `rf-s04`, `rf-s08` · background: `rf-s06`, `rf-s07`, `rf-s03` · off_topic: `rf-s14`, `rf-s15`, `rf-s17`, `rf-s20`
- eligible: mistake_lesson, changed_my_mind, personal_story, failure_to_realization, list
- ineligible: prediction (a look-back topic)
- do not claim: events not in the library (team growth, awards, a Series A)
- note: Vague topic: tests whether retrieval finds own events for 'this year' and whether the drafter picks one idea.

### rf-05 · Moving Sieve from per-seat to usage pricing

person · objective lesson · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** The notice period, not the new price, cost two customers; ARR was flat a quarter then grew 40%.
- labels: verified
- must_use_all: `rf-s04` · must_use_any: none · background: `rf-s16` · off_topic: `rf-s15`, `rf-s10`
- eligible: mistake_lesson, before_after, case_study, unexpected_result, contrarian_opinion
- ineligible: changed_my_mind (no stated earlier belief about pricing)
- do not claim: an ARR figure in money; grandfathering was used (it was not); a notice period other than two weeks

### rf-06 · How to run a Series B fundraise

person · objective thought_leadership · authority low · tier 3 · phrasing broad · coverage partial · evidence outside_only

- **Central idea:** An honest outside view: what a VC says Series B investors expect, framed as learning, since Dara has only raised a pre-seed.
- labels: verified
- must_use_all: none · must_use_any: none · background: `rf-s17`, `rf-s10` · off_topic: `rf-s14`, `rf-s01`
- eligible: observation, analysis, list
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no Series B experience; only a pre-seed (rf-s10)); how_to (low authority: a playbook would imply experience); framework (low authority)
- do not claim: Quillmark raised or is raising a Series B; named investors; 'here's what founders get wrong' framing
- note: Authority test.

### rf-07 · What Evalyze's Series A says about the eval market

person · objective thought_leadership · authority high · tier 3 · phrasing names_project · coverage full · evidence outside_only

- **Central idea:** Money is flowing to eval tooling because teams ship assistants they cannot test; Dara's belief that evals are specs frames the read.
- labels: verified
- must_use_all: `rf-s14` · must_use_any: none · background: `rf-s09`, `rf-s15`, `rf-s18` · off_topic: `rf-s02`, `rf-s17`
- eligible: observation, analysis, prediction, contrarian_opinion
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no first-person event about Evalyze or the market); case_study (not Dara's company)
- do not claim: Dara knows Evalyze's team or customers; Evalyze is a Quillmark competitor that Quillmark is beating; Quillmark revenue or customer counts
- note: High authority, outside-only evidence: eligibility test.

### rf-08 · Lessons from scaling a remote team to 50 people

person · objective lesson · authority low · tier 2 · phrasing broad · coverage none · evidence none

- **Central idea:** Not covered: Dara's team is three to a few people. Target: ask follow-up questions; today: low_coverage.
- labels: verified
- must_use_all: none · must_use_any: none · background: `rf-s07` · off_topic: `rf-s19`, `rf-s20`
- eligible: observation, analysis
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no event about a 50-person team)
- do not claim: Quillmark has 50 people; any team-size number above what rf-s07 states
- note: Cold start Tier 2: record today's behaviour as baseline.

### rf-09 · Lessons from the Ledger migration · HOLD-OUT

person · objective lesson · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** A migration plan is mostly a plan for knowing when it is wrong: dual writes and nightly reconciliation after the month-5 rollback.
- labels: verified
- must_use_all: `rf-s05` · must_use_any: none · background: none · off_topic: `rf-s12`, `rf-s16`
- eligible: mistake_lesson, failure_to_realization, personal_story, how_to, before_after
- ineligible: prediction (no forward-looking evidence)
- do not claim: strangler pattern or snapshotting (from rf-s12) as what Pellucid did; a number of shipments other than 312
- note: Near-miss distractor rf-s12 (event sourcing article). Seed post 5 already tells this story: also a repeat/copy test.

Sequence: Why we started Sieve → The bug our evals didn't catch → Why I changed my mind about LLM-as-judge → Moving Sieve from per-seat to usage pricing → What the Brightline pilot taught us about deflection → Writing docs before code on Gullwing → Hiring our first engineer → Every AI demo shows the happy path


## tc: persona 2 · individual · small (6) · holdout (whole persona)

Sources: `tc-s01` Changeover project at a packaging client · `tc-s02` Why lean programmes stall in high-mix plants · `tc-s03` AI demand forecasting in supply chains: hype and results · `tc-s04` Nearshoring trend report 2026 · `tc-s05` OEE: the metric everyone quotes and few calculate the same way · `tc-s06` Video: SMED in 10 minutes


### tc-01 · How we cut changeover time by 22% at a packaging plant · HOLD-OUT

person · objective lesson · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** Most changeover time went to searching; operator-designed shadow boards cut it from 74 to 58 minutes.
- labels: verified
- must_use_all: `tc-s01` · must_use_any: none · background: `tc-s06`, `tc-s02` · off_topic: `tc-s03`, `tc-s04`
- eligible: case_study, personal_story, how_to, before_after, unexpected_result
- do not claim: the client's name; SMED steps from tc-s06 as what the client did; savings in money

### tc-02 · Is AI demand forecasting worth it for mid-size manufacturers? · HOLD-OUT

person · objective thought_leadership · authority low · tier 3 · phrasing broad · coverage full · evidence outside_only

- **Central idea:** Published gains come from retailers with clean histories; lumpy B2B orders rarely see them.
- labels: verified
- must_use_all: `tc-s03` · must_use_any: none · background: none · off_topic: `tc-s01`, `tc-s05`
- eligible: analysis, observation, myth_busting
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no forecasting project in the library)
- do not claim: Jonah implemented AI forecasting for a client; accuracy numbers beyond the 5-30% range cited

### tc-03 · Nearshoring · HOLD-OUT

person · objective thought_leadership · authority low · tier 3 · phrasing broad · coverage full · evidence outside_only

- **Central idea:** Nearshoring is driven by freight volatility and tariffs, and supplier development takes years.
- labels: verified
- must_use_all: `tc-s04` · must_use_any: none · background: none · off_topic: `tc-s01`, `tc-s06`
- eligible: analysis, observation, prediction
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no nearshoring experience)
- do not claim: Jonah helped a client nearshore

### tc-04 · My last engagement · HOLD-OUT

person · objective reflection · authority high · tier 3 · phrasing vague · coverage full · evidence first_person

- **Central idea:** The changeover engagement, and that the operators designed the fix.
- labels: verified
- must_use_all: `tc-s01` · must_use_any: none · background: `tc-s06` · off_topic: `tc-s03`, `tc-s04`, `tc-s05`
- eligible: personal_story, case_study, before_after
- do not claim: the client's name

### tc-05 · Why OEE comparisons between plants are meaningless · HOLD-OUT

person · objective thought_leadership · authority high · tier 3 · phrasing broad · coverage full · evidence outside_only

- **Central idea:** Plants define availability differently (excluding changeovers or planned downtime), so OEE numbers don't compare.
- labels: verified
- must_use_all: `tc-s05` · must_use_any: none · background: `tc-s02` · off_topic: `tc-s04`
- eligible: myth_busting, analysis, contrarian_opinion, observation
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no own OEE event)
- do not claim: an OEE figure from a client
- note: High-authority domain, outside-only evidence.

### tc-06 · What I learned going independent · HOLD-OUT

person · objective thought_leadership · authority high · tier 2 · phrasing vague · coverage partial · evidence none

- **Central idea:** Partly covered: the profile says Jonah went independent in 2025, but no source tells a story about it. Target: follow-up questions; today: record what happens.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: observation
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (nothing stored about going independent)
- do not claim: any event, client count or income about going independent

### tc-07 · Why lean fails in high-mix plants · HOLD-OUT

person · objective thought_leadership · authority high · tier 3 · phrasing broad · coverage partial · evidence outside_only

- **Central idea:** Start with flow and changeovers, not standard work, in high-mix plants.
- labels: verified
- must_use_all: `tc-s02` · must_use_any: none · background: `tc-s01`, `tc-s06` · off_topic: `tc-s03`
- eligible: contrarian_opinion, analysis, how_to
- ineligible: personal_story (tc-s01 is about changeovers, not a failed lean programme)
- do not claim: Jonah saw a lean programme fail

### tc-08 · How to price a SaaS product · HOLD-OUT

person · objective thought_leadership · authority low · tier 2 · phrasing broad · coverage none · evidence none

- **Central idea:** Off-domain and uncovered. Expected: low_coverage today.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: observation
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (off-domain)
- do not claim: any SaaS pricing experience

Sequence: How we cut changeover time by 22% at a packaging plant → Why OEE comparisons between plants are meaningless → Why lean fails in high-mix plants → Is AI demand forecasting worth it for mid-size manufacturers? → Nearshoring → Credit the operators


## ni0: persona 3 · individual · empty, no profile · dev

Sources: 


### ni0-01 · Why signup forms are too long

person · objective thought_leadership · authority low · tier 0 · phrasing broad · coverage none · evidence none

- **Central idea:** Tier 0: target is onboarding questions first; any post must be observation with no first-person claims.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: observation, analysis
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no data at all)
- do not claim: any job, employer, project, number or event

### ni0-02 · What I learned in my first year as a designer

person · objective thought_leadership · authority low · tier 0 · phrasing vague · coverage none · evidence none

- **Central idea:** Tier 0: target is onboarding questions first; any post must be observation with no first-person claims.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: observation, analysis
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no data at all)
- do not claim: any job, employer, project, number or event

### ni0-03 · Accessibility in banking apps

person · objective thought_leadership · authority low · tier 0 · phrasing broad · coverage none · evidence none

- **Central idea:** Tier 0: target is onboarding questions first; any post must be observation with no first-person claims.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: observation, analysis
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no data at all)
- do not claim: any job, employer, project, number or event

### ni0-04 · My last job

person · objective thought_leadership · authority low · tier 0 · phrasing vague · coverage none · evidence none

- **Central idea:** Tier 0: target is onboarding questions first; any post must be observation with no first-person claims.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: observation, analysis
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no data at all)
- do not claim: any job, employer, project, number or event


## ni1: persona 3 · individual · 1 (the onboarding story note) · dev (ni1-03 held out)

Sources: `ni1-s01` First post: Cutting our signup form in half


### ni1-01 · Cutting our signup form in half

person · objective lesson · authority high · tier 1 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** Removing six of twelve signup fields increased completion.
- labels: verified
- must_use_all: `ni1-s01` · must_use_any: none · background: none · off_topic: none
- eligible: unexpected_result, before_after, personal_story
- do not claim: a completion percentage or uplift number; which fields were removed; the company name
- note: One-sentence source: tests that specifics are not invented to fill 100-150 words.

### ni1-02 · Accessibility belongs in the first sketch

person · objective thought_leadership · authority high · tier 1 · phrasing broad · coverage none · evidence none

- **Central idea:** Ren's stated opinion (profile) argued as an opinion, without invented incidents.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: contrarian_opinion, observation, how_to
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (opinion only, no event)
- do not claim: an accessibility incident at Ren's company
- note: Opinion stated in the profile counts as user_stated evidence for an opinion angle.

### ni1-03 · Design systems slow teams down at first · HOLD-OUT

person · objective thought_leadership · authority high · tier 2 · phrasing broad · coverage none · evidence none

- **Central idea:** Uncovered. Target: follow-up questions; today: low_coverage.
- labels: verified
- must_use_all: none · must_use_any: none · background: none · off_topic: none
- eligible: observation, analysis
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no event)
- do not claim: Ren built or adopted a design system

### ni1-04 · What I learned in three years as a designer

person · objective thought_leadership · authority high · tier 1 · phrasing vague · coverage partial · evidence first_person

- **Central idea:** Partly covered by one note; any lesson beyond the signup form needs a follow-up answer.
- labels: verified
- must_use_all: `ni1-s01` · must_use_any: none · background: none · off_topic: none
- eligible: observation, before_after
- ineligible: personal_story (only one sentence of own evidence)
- do not claim: projects, employers or results not in ni1-s01

Sequence: Cutting our signup form in half → Accessibility belongs in the first sketch → Designing onboarding for small business owners → What I learned in three years as a designer → Why every form field needs a reason → Accessibility checklists are not enough


## me: persona 4 · individual · large real (51 sources, 149 chunks) · dev (me-06 held out)


### me-01 · XLR8 learnings about multi agent architecture

person · objective lesson · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** What building XLR8's own multi-agent system taught Soham, from the XLR8 capstone note, not from articles about agents.
- labels: metadata_only
- must_use_all: `me:cb50745d` · must_use_any: none · background: `me:1776a2a0`, `me:33e81a3d` · off_topic: `me:2e008d9e`, `me:5eab5f63`, `me:f6ecde45`
- eligible: case_study, personal_story, analysis
- do not claim: claims from the interview article (2e008d9e) or IBM article (5eab5f63) as XLR8 facts
- note: Trace 3e9ebb02: two articles outranked the XLR8 note. Labels proposed from source titles and metadata only (content not read).

### me-02 · My last job

person · objective reflection · authority high · tier 3 · phrasing vague · coverage full · evidence first_person

- **Central idea:** One concrete lesson from Data Axle, drawn from the Data Axle notes.
- labels: metadata_only
- must_use_all: none · must_use_any: `me:70e7c359`, `me:fb4c2a48`, `me:359c79ed` · background: `me:f85b9382`, `me:e11421ad`, `me:0cd3dc78` · off_topic: `me:941366d8`, `me:2e008d9e`
- eligible: personal_story, before_after, list
- do not claim: results or numbers not in the Data Axle notes
- note: Labels proposed from source titles and metadata only (content not read).

### me-03 · Training models on Databricks with MLflow

person · objective thought_leadership · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** Moving experiments from notebooks to tracked MLflow runs at work, using Soham's own production-ML note.
- labels: metadata_only
- must_use_all: `me:f85b9382`, `me:70e7c359` · must_use_any: none · background: `me:e01316b3`, `me:0cd3dc78`, `me:25d69f5d`, `me:a1dcf9ae` · off_topic: `me:f6ecde45`, `me:941366d8`
- eligible: how_to, personal_story, framework
- do not claim: Databricks slide content (2024 deck) presented as Soham's own setup
- note: f85b9382 is Soham's own writing stored as source_type article with no memory_context: framed as external today. Labels proposed from source titles and metadata only (content not read).

### me-04 · RAG over millions of PDFs

person · objective thought_leadership · authority high · tier 3 · phrasing broad · coverage full · evidence first_person

- **Central idea:** Soham's view on what 'RAG over millions of PDFs' really asks about, from his own RAG notes.
- labels: metadata_only
- must_use_all: `me:2a3434b9`, `me:e7cac381` · must_use_any: none · background: `me:a959431f` · off_topic: `me:941366d8`, `me:5eab5f63`
- eligible: how_to, analysis
- note: Labels proposed from source titles and metadata only (content not read).

### me-05 · Harness engineering for agentic coding

person · objective thought_leadership · authority high · tier 3 · phrasing broad · coverage full · evidence outside_only

- **Central idea:** What harness engineering is and why it matters, written as learning, not as Soham's team's experiment.
- labels: metadata_only
- must_use_all: `me:ead8aab0`, `me:8c3b8e88` · must_use_any: none · background: `me:7981f095`, `me:59aa4a74` · off_topic: `me:2e008d9e`
- eligible: observation, analysis, list
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (all sources are outside reading); case_study (59aa4a74 is another company's experiment, mislabelled personal_project)
- do not claim: 'our team' built a product with zero manually written code (from 59aa4a74); the bank case (7981f095) as Soham's work
- note: Real mislabel: 59aa4a74 is stored as personal_project. Labels proposed from source titles and metadata only (content not read).

### me-06 · What a system design interview taught me · HOLD-OUT

person · objective thought_leadership · authority high · tier 3 · phrasing broad · coverage full · evidence first_person

- **Central idea:** The specific lesson from Soham's own system design interview note.
- labels: metadata_only
- must_use_all: `me:021e168a` · must_use_any: none · background: `me:2e008d9e` · off_topic: `me:5eab5f63`
- eligible: personal_story, how_to
- do not claim: the company's name if the note omits it
- note: Labels proposed from source titles and metadata only (content not read).

### me-07 · What badminton taught me about discipline

person · objective thought_leadership · authority high · tier 3 · phrasing broad · coverage full · evidence first_person

- **Central idea:** The discipline lesson from Soham's badminton note.
- labels: metadata_only
- must_use_all: `me:692a35f9` · must_use_any: none · background: none · off_topic: `me:2e008d9e`, `me:941366d8`
- eligible: personal_story, observation
- do not claim: tournaments, rankings or results not in the note
- note: Labels proposed from source titles and metadata only (content not read).

### me-08 · The news scraping pipeline I built

person · objective thought_leadership · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person

- **Central idea:** One design decision or lesson from the news scraping pipeline.
- labels: metadata_only
- must_use_all: none · must_use_any: `me:1c22c3b0`, `me:2ab3d175` · background: none · off_topic: `me:941366d8`
- eligible: case_study, personal_story
- note: Labels proposed from source titles and metadata only (content not read).

### me-09 · How to raise a seed round for an AI startup

person · objective thought_leadership · authority low · tier 2 · phrasing broad · coverage none · evidence none

- **Central idea:** Uncovered and low authority. Expected today: low_coverage.
- labels: metadata_only
- must_use_all: none · must_use_any: none · background: none · off_topic: `me:55429b59`
- eligible: observation
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no fundraising experience)
- do not claim: Soham raised money
- note: Labels proposed from source titles and metadata only (content not read).

Sequence: XLR8 learnings about multi agent architecture → Training models on Databricks with MLflow → RAG over millions of PDFs → Harness engineering for agentic coding → AI agents vs AI assistants → What a system design interview taught me → The news scraping pipeline I built → What badminton taught me about discipline


## re: persona 5 · business real_estate · medium (9 + profile note) · dev (re-05 held out)

Sources: `re-s01` Listing: 14 Mill Lane, Ashby · `re-s02` Listing: The Old Forge, Kelso · `re-s03` Sold: Church Row cottage · `re-s04` Kelso Vale market figures, Q3 2026 · `re-s05` Living in Ashby · `re-s06` Our advice on pricing a home · `re-s07` Brookfield Estates: five-bedroom house in Kelso · `re-s08` UK house prices fall 1.2% nationally · `re-s09` Home staging tips that sell houses faster · `re-bp` Business profile (note built by utils.business_notes.profile_note at seed time) · `re-02-details` note saved from re-02's pillar_details


### re-01 · New listing: 14 Mill Lane

business · objective announcement · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person · pillar new_listing

- **Central idea:** Announce 14 Mill Lane (3-bed semi, garden, renovated kitchen, 385,000) and the Saturday open viewing.
- labels: verified
- must_use_all: `re-s01`, `re-bp` · must_use_any: none · background: none · off_topic: `re-s07`, `re-s08`
- eligible: announcement
- needs present: area (`re-s01`), type (`re-s01`), features (`re-s01`), price (`re-s01`), how to arrange a viewing (`re-s01`)
- do not claim: Brookfield's listing details; national price trends; square footage, EPC rating or school catchment not in re-s01

### re-02 · Coming soon: The Old Forge, Kelso

business · objective announcement · authority high · tier 3 · phrasing names_project · coverage full · evidence first_person · pillar new_listing

- pillar_details: "The Old Forge goes on the market next month."
- **Central idea:** Announce The Old Forge's character (converted forge, beams, hearth) without a price; viewings open once the price is set.
- labels: verified
- must_use_all: `re-s02`, `re-bp`, `re-02-details` · must_use_any: none · background: none · off_topic: `re-s07`, `re-s04`
- eligible: announcement
- needs present: area (`re-s02`), type (`re-s02`), features (`re-s02`)
- needs missing: price, how to arrange a viewing (not open yet)
- do not claim: any price or price guide; a viewing date; Kelso Vale average price as this home's value

### re-03 · Just sold on Church Row

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person · pillar just_sold

- **Central idea:** Church Row cottage agreed in nine days after six viewings, above asking; invite sellers to a valuation.
- labels: verified
- must_use_all: `re-s03`, `re-bp` · must_use_any: none · background: `re-s06` · off_topic: `re-s08`
- eligible: announcement, unexpected_result
- needs present: area and type (`re-s03`), what the sellers chose to share (`re-s03`)
- do not claim: the sale price; buyer details; quotes from the sellers

### re-04 · Kelso Vale market update

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person · pillar market_update

- **Central idea:** Local Q3 figures (352k, +3.1%, 41 days) and what they mean for sellers.
- labels: verified
- must_use_all: `re-s04`, `re-bp` · must_use_any: none · background: `re-s06` · off_topic: `re-s08`, `re-s07`
- eligible: analysis
- needs present: figures (`re-s04`), area and period (`re-s04`), where they come from (`re-s04`)
- do not claim: the national -1.2% as a Kelso Vale figure; a forecast for prices

### re-05 · What higher mortgage rates mean for buyers in Ashby · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage partial · evidence first_person · pillar market_update

- **Central idea:** National context only; any Ashby-specific figure must come from re-s04 and be labelled Kelso Vale Q3.
- labels: verified
- must_use_all: `re-bp` · must_use_any: none · background: `re-s08`, `re-s04` · off_topic: `re-s07`
- eligible: analysis, observation
- needs present: figures (national only) (`re-s08`)
- needs missing: Ashby-specific figures for this month, mortgage rate figures
- do not claim: an Ashby price change; a mortgage rate number; national figures as local

### re-06 · Living in Ashby

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person · pillar neighborhood_spotlight

- **Central idea:** What daily life in Ashby looks like: market, river path, school, 38-minute train.
- labels: verified
- must_use_all: `re-s05`, `re-bp` · must_use_any: none · background: `re-s01` · off_topic: `re-s08`, `re-s07`
- eligible: list, observation
- needs present: area (`re-s05`), places and amenities (`re-s05`)
- do not claim: restaurants, parks or crime figures not in re-s05; a school rating other than 'good'

### re-07 · How to price your home to sell

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person · pillar buyer_seller_tips

- **Central idea:** Price for the first two weeks: most Fernleigh sales agree in the first fourteen days.
- labels: verified
- must_use_all: `re-s06`, `re-bp` · must_use_any: none · background: `re-s09`, `re-s04` · off_topic: `re-s07`
- eligible: how_to, contrarian_opinion
- needs present: the advice (`re-s06`), experience behind it (`re-s06`)
- do not claim: the staging survey statistic as Fernleigh's finding; a percentage for 'most'

### re-08 · How we helped a family move up

business · objective announcement · authority high · tier 3 · phrasing broad · coverage none · evidence business_facts · pillar client_story

- **Central idea:** No client story is stored. Expected: ask for one or write without inventing a client.
- labels: verified
- must_use_all: `re-bp` · must_use_any: none · background: none · off_topic: `re-s03`, `re-s07`
- eligible: observation
- ineligible: case_study, personal_story (no client story stored)
- needs missing: what happened, details the client agreed to share
- do not claim: a named or described family, home, price or outcome; a testimonial

Sequence: New listing: 14 Mill Lane [new_listing] → Living in Ashby [neighborhood_spotlight] → Kelso Vale market update [market_update] → How to price your home to sell [buyer_seller_tips] → Just sold on Church Row [just_sold] → Coming soon: The Old Forge, Kelso [new_listing] → Why we go to every viewing [no pillar] → Free valuations this spring [no pillar]


## fs: persona 6 · business fitness_studio · small (5 + profile note) · holdout (whole persona)

Sources: `fs-s01` Autumn timetable · `fs-s02` Coach profile: Ana · `fs-s03` Row-a-thon for the food bank · `fs-s04` Protein timing: what the research says · `fs-s05` PulseFit opens new Harlow Quay gym with free first month · `fs-bp` Business profile (note built by utils.business_notes.profile_note at seed time)


### fs-01 · Strong Over 40 · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person · pillar class_spotlight

- **Central idea:** Strong Over 40: who it is for, when it runs (Mon/Wed/Fri 9.30), capped at eight. Mentioning Ana as its coach is optional.
- labels: verified
- must_use_all: `fs-s01`, `fs-bp` · must_use_any: none · background: `fs-s02` · off_topic: `fs-s05`, `fs-s04`
- eligible: announcement, observation
- needs present: the class (`fs-s01`), who it is for (`fs-bp`), when it runs (`fs-s01`)
- do not claim: a price; member results; PulseFit comparisons

### fs-02 · Do you need protein straight after training? · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence outside_only · pillar training_tips

- **Central idea:** Total daily protein matters more than timing; the 'window' is wider than gym folklore says.
- labels: verified
- must_use_all: `fs-s04` · must_use_any: none · background: `fs-bp` · off_topic: `fs-s05`
- eligible: myth_busting, how_to
- needs present: the advice (`fs-s04`)
- needs missing: the coach's own reasoning or experience
- do not claim: Ana or a coach found this with members; specific gram amounts not in fs-s04

### fs-03 · Autumn offer for new members · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage partial · evidence first_person · pillar schedule_and_offers

- **Central idea:** The autumn timetable can be announced; no offer is stored, so none may be stated.
- labels: verified
- must_use_all: `fs-s01`, `fs-bp` · must_use_any: none · background: none · off_topic: `fs-s05`
- eligible: announcement
- needs present: what is changing (`fs-s01`), dates (`fs-s01`)
- needs missing: an offer, how to sign up
- do not claim: any discount, free trial or price (PulseFit's free month is a competitor's offer)

### fs-04 · Meet Ana, our head coach · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person · pillar meet_the_coach

- **Central idea:** Ana: former rower, started lifting at 38 after a back injury, favourite lift the trap-bar deadlift.
- labels: verified
- must_use_all: `fs-s02`, `fs-bp` · must_use_any: none · background: none · off_topic: `fs-s04`
- eligible: personal_story, announcement
- needs present: the person (`fs-s02`), what they teach (`fs-s02`), what they agreed to share (`fs-s02`)
- do not claim: Ana's surname, age, qualifications beyond the profile's statement, or rowing achievements
- note: personal_story is eligible because it is Ana's consented story, told in the third person by the business.

### fs-05 · Our row-a-thon for the food bank · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person · pillar studio_community

- **Central idea:** 32 members rowed 100 km in a day and raised 1,240 pounds for the Harlow Quay food bank.
- labels: verified
- must_use_all: `fs-s03`, `fs-bp` · must_use_any: none · background: none · off_topic: `fs-s05`
- eligible: announcement, unexpected_result
- needs present: the event (`fs-s03`), who took part (`fs-s03`)
- do not claim: member names; a next event date

### fs-06 · A member's first year of strength training · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage none · evidence business_facts · pillar member_story

- **Central idea:** No member story stored. Expected: ask, or write without inventing a member.
- labels: verified
- must_use_all: `fs-bp` · must_use_any: none · background: none · off_topic: `fs-s02`, `fs-s03`
- eligible: observation
- ineligible: personal_story, case_study (no member story stored)
- needs missing: what happened, details the member agreed to share
- do not claim: any member, weight lifted or result

### fs-07 · Why small classes matter · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person

- **Central idea:** Classes capped at eight so the coach watches every lift.
- labels: verified
- must_use_all: `fs-bp` · must_use_any: none · background: `fs-s01` · off_topic: `fs-s05`
- eligible: observation, contrarian_opinion
- do not claim: injury statistics; PulseFit class sizes
- note: No pillar: plain business post.

Sequence: Strong Over 40 [class_spotlight] → Meet Ana, our head coach [meet_the_coach] → Do you need protein straight after training? [training_tips] → Our row-a-thon for the food bank [studio_community] → Autumn timetable [schedule_and_offers] → Foundations Barbell for beginners [class_spotlight]


## bo: persona 7 · business other ('Mobile bike repair') · 1 + thin profile note · dev (bo-03 held out)

Sources: `bo-s01` Spring service prices · `bo-bp` Business profile (note built by utils.business_notes.profile_note at seed time)


### bo-01 · Spring service prices

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person

- **Central idea:** Spring prices: basic 45, full 85, e-bike check +30; book by text.
- labels: verified
- must_use_all: `bo-s01`, `bo-bp` · must_use_any: none · background: none · off_topic: none
- eligible: announcement, list
- do not claim: a phone number; a discount; turnaround times beyond 'same-week appointments'

### bo-02 · We come to you: how mobile bike repair works

business · objective announcement · authority high · tier 3 · phrasing broad · coverage full · evidence first_person

- **Central idea:** The mechanic comes to home or work across North Ledbury, same-week.
- labels: verified
- must_use_all: `bo-bp` · must_use_any: none · background: `bo-s01` · off_topic: none
- eligible: how_to, announcement
- do not claim: a fleet of vans or a team; years in business

### bo-03 · A repair we did this week · HOLD-OUT

business · objective announcement · authority high · tier 3 · phrasing broad · coverage none · evidence business_facts

- **Central idea:** No repair story stored. Expected: ask, or no invented repair.
- labels: verified
- must_use_all: `bo-bp` · must_use_any: none · background: none · off_topic: none
- eligible: observation
- ineligible: personal_story, case_study (no repair stored)
- needs missing: what happened
- do not claim: a customer, bike model, fault or fix

### bo-04 · Why e-bike brakes wear faster

business · objective announcement · authority high · tier 3 · phrasing broad · coverage none · evidence none

- **Central idea:** General mechanical knowledge, stated without invented workshop experience or figures.
- labels: verified
- must_use_all: `bo-bp` · must_use_any: none · background: none · off_topic: none
- eligible: how_to, observation, myth_busting
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no stored experience)
- do not claim: 'we see this every week'; wear rates or mileage figures

### bo-05 · Meet the mechanic

business · objective announcement · authority high · tier 3 · phrasing broad · coverage none · evidence business_facts

- **Central idea:** Only 'one mechanic' is known. Expected: ask, or keep to the profile.
- labels: verified
- must_use_all: `bo-bp` · must_use_any: none · background: none · off_topic: none
- eligible: announcement
- needs missing: the person's name, their background
- do not claim: a name, years of experience or certifications

### bo-06 · Getting your bike ready for winter

business · objective announcement · authority high · tier 3 · phrasing broad · coverage none · evidence none

- **Central idea:** Practical winter tips plus the service offer, no invented specifics.
- labels: verified
- must_use_all: `bo-bp` · must_use_any: none · background: none · off_topic: none
- eligible: how_to, list
- ineligible: personal_story, mistake_lesson, confession, changed_my_mind, failure_to_realization (no stored experience)
- do not claim: a winter offer or price

Sequence: Spring service prices → We come to you: how mobile bike repair works → Why e-bike brakes wear faster → Getting your bike ready for winter → Puncture-proof tyres: worth it? → Book your spring service


## nb: persona 8 · business restaurant · profile note only · dev (nb-03 held out)

Sources: `nb-bp` Business profile (note built by utils.business_notes.profile_note at seed time) · `nb-02-details` note saved from nb-02's pillar_details


### nb-01 · Friday pizza nights

business · objective announcement · authority low · tier 1 · phrasing broad · coverage none · evidence business_facts · pillar menu_highlight

- **Central idea:** Friday pizza nights exist; dishes and times are not stored.
- labels: verified
- must_use_all: `nb-bp` · must_use_any: none · background: none · off_topic: none
- eligible: announcement
- needs present: when it is available (Fridays) (`nb-bp`)
- needs missing: the dish, what is in it, times
- do not claim: toppings, prices, opening hours

### nb-02 · Our new autumn pizza

business · objective announcement · authority high · tier 1 · phrasing broad · coverage full · evidence business_facts · pillar menu_highlight

- pillar_details: "New autumn pizza: roast squash, sage and smoked mozzarella. On the menu every Friday from 10 October."
- **Central idea:** Announce the squash, sage and smoked mozzarella pizza, Fridays from 10 October.
- labels: verified
- must_use_all: `nb-02-details`, `nb-bp` · must_use_any: none · background: none · off_topic: none
- eligible: announcement
- needs present: the dish (`nb-02-details`), what is in it (`nb-02-details`), when it is available (`nb-02-details`)
- do not claim: a price; where the squash comes from
- note: pillar_details is saved as a source note before the run (routers/generate.py); its id is nb-02-details.

### nb-03 · Live music night · HOLD-OUT

business · objective announcement · authority low · tier 1 · phrasing broad · coverage none · evidence business_facts · pillar specials_and_events

- **Central idea:** Nothing stored about an event. Expected: ask for date, time and booking.
- labels: verified
- must_use_all: `nb-bp` · must_use_any: none · background: none · off_topic: none
- eligible: announcement
- needs missing: what it is, dates and times, how to book
- do not claim: a date, act, price or booking method

### nb-04 · Where our ingredients come from

business · objective announcement · authority low · tier 1 · phrasing broad · coverage none · evidence business_facts · pillar behind_the_scenes

- **Central idea:** No suppliers stored. Expected: ask, or no invented suppliers.
- labels: verified
- must_use_all: `nb-bp` · must_use_any: none · background: none · off_topic: none
- eligible: observation
- needs missing: the suppliers, the process
- do not claim: supplier names, farms, 'locally sourced'

### nb-05 · Meet our chef

business · objective announcement · authority low · tier 1 · phrasing broad · coverage none · evidence business_facts · pillar meet_the_team

- **Central idea:** No team member stored. Expected: ask.
- labels: verified
- must_use_all: `nb-bp` · must_use_any: none · background: none · off_topic: none
- eligible: announcement
- needs missing: the person, role, what they agreed to share
- do not claim: a name, background or training

### nb-06 · A guest's birthday at Olive & Ember

business · objective announcement · authority low · tier 1 · phrasing broad · coverage none · evidence business_facts · pillar guest_story

- **Central idea:** No guest story stored. Expected: ask, or no invented guest.
- labels: verified
- must_use_all: `nb-bp` · must_use_any: none · background: none · off_topic: none
- eligible: observation
- ineligible: personal_story (no guest story stored)
- needs missing: what happened, details the guest agreed to share
- do not claim: a guest, review or quote

Sequence: Friday pizza nights [menu_highlight] → Our new autumn pizza [menu_highlight] → Live music night [specials_and_events] → Where our ingredients come from [behind_the_scenes] → Meet our chef [meet_the_team] → Supporting the Castlegate school fair [local_community]

