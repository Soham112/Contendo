# Handoff: core rebuild, start of step 3 (data layer)

Written 2026-10-16 at main `97c67f9`. Read this, then `CODEBASE.md` §6 "Retrieval quality backlog", then `docs/QUALITY.md` B1. Don't read whole long files; search first.

## Where we are

Build order (agreed with Soham): **raw source → extraction → provenance/metadata → chunking → embeddings/indexes → retrieval → evidence/coverage decision → strategy → generation.** Quality before latency, and no change may make time to first word slower than production without his decision.

Done and merged:
1. **Quality bar** `docs/QUALITY.md`: criteria B1-B8. B1 is the retrieval scorecard: Recall@cutoff (+@1/@3/@5), MRR, Precision@cutoff, off-topic rate, own-source share, coverage-gate accuracy, hybrid-search reliability. Evidence Recall@cutoff is planned (needs fact labels; candidate judge: DeepEval `ContextualRecall`). DeepEval has no label-based rank metrics; ours are in `evals/quality_metrics.py`.
2. **Test set quality_v1** (labels approved by Soham): 9 personas, 61 cases, 21 hold-out.
   - Synthetic: `rf` rich founder, `tc` thin consultant (hold-out), `ni0`/`ni1` new user Tier 0/1, `re` real estate, `fs` fitness studio (hold-out), `bo` niche "other", `nb` new business. Fixtures `evals/fixtures/quality_v1/`, cases `evals/goldens/quality_v1/cases.jsonl`.
   - `me`: Soham's real production library (51 sources, 149 chunks), copied read-only into the eval project. Its cases, snapshot and export live only in gitignored `evals/private/quality_v1/`. **The GitHub repo is public: never commit anything from his library.**
   - Label schema: `must_use_all` / `must_use_any` (a group counts as one unit), `label_confidence` verified (synthetic) / metadata_only (me; angle labels never a hard fail), request notes `<case>-details`. Cases with `pillar_details` (re-02, nb-02) run as their own eval users so scoring never writes.
3. **Retrieval baseline and the vector-search fix.** IVFFlat (lists=100, probes=1, user filter after the scan) found 3% of the true top-8 in production. Migration 013 (exact per-user scan: IVFFlat dropped, `embeddings(user_id)` index) is applied to eval **and production**: 100%, latency within noise.
   - Before: `evals/baselines/2026-10-15-quality-v1-retrieval.md`
   - **Current yardstick:** `evals/baselines/2026-10-16-exact-vector-search.md`: dev Recall@cutoff 0.57, MRR 0.63, Precision@cutoff 0.65; hold-out Recall 0.65, Precision 0.74, off-topic 0.07.

## Step 3 scope, in Soham's order

1. **Preserve originals**: raw text or file reference + extractor and version metadata. The existing 51 production sources can only be rebuilt from stored chunks: mark them `rebuilt_from_chunks`, never confuse with re-extractable originals. Images and PDFs get better extraction only if re-uploaded.
2. **Extraction**: one place per input type (note, file, URL, YouTube, image, Obsidian), versioned.
3. **Provenance/verification metadata**: `user_authored`, `user_stated`, `external`/`inferred`, per source and per chunk (today `memory_context` is per document, null on 91% of production chunks, and real data has mislabels: an outside article stored as `personal_project`, own writing stored as `article`). The business profile note currently counts as own experience (`utils/frames.py SELF_FRAMES`).
4. **Chunking**: chunks must fit the embedder's 256-token window (89% of production chunks don't; 77% of stored text is never embedded; one chunk is 13,729 tokens). Index the source title with each chunk (rf-03: exact-title note scores cosine 0.287 < 0.30 gate; tc-03 "Nearshoring" scores 0 on BM25 because the word is only in the title).
5. **Embedding model chosen by measurement**, not by default (MiniLM puts near-miss articles close to own notes).
6. **Reproducible re-ingestion** from stored originals without another upload.
7. Benchmark chunk size / model / settings on quality_v1, then recalibrate the 0.30 relevance floor and coverage gate (tuned on broken scores; me-09 now passes the gate). Then step 4 ranking (provenance-aware, fewer sources, entity enrichment kept only if it helps), then the thin-evidence follow-up questions (answers stored as `user_stated`).
8. Evidence Recall needs fact labels per case: add them while redesigning chunks.

Open design questions to bring to Soham early: where originals are stored (table vs Supabase Storage) and retention; the provenance enum and who sets it (user, classifier, rule); whether titles are embedded as a prefix or a separate field; migration and backfill plan for the 7 production users.

## How to measure a change

```bash
cd evals && ../backend/venv/bin/python -m pytest -q        # 166 pass; 1 known failure test_guard BILLING_DISABLED
backend/venv/bin/python evals/quality_seed.py --estimate     # cost before any paid seeding
backend/venv/bin/python evals/quality_retrieval.py --name <date>-<change>   # read-only, $0, all 61 cases
```

Compare against the current yardstick: dev first, hold-out at the end of the step. Ship only if recall isn't given back and first word isn't slower. Write a before/after file in `evals/baselines/`.

Changing ingestion means re-seeding eval personas (paid). Rules: `--estimate` first, Soham approves the number, run under `--spend-cap` (default $1), report measured spend.

## Things learned the hard way

- **Migrations:** Soham applies SQL himself in the Supabase SQL editor. Ask for eval first, measure, then production (013 went to both at once).
- **Usage logging:** the backend writes `usage_events` only through a server event loop; scripts log nothing unless they register one (`UsageLog` in `evals/quality_seed.py`). Migration 006 is now applied to eval.
- **Supabase connections drop** ("Server disconnected") intermittently. `retrieval_node` swallows failures into silent fallbacks; the harness retries (path not hybrid, or BM25 error) and records attempts.
- **Deleting a source leaves derived data** (`chunk_entities`, consolidation chunks). Production bug, documented, not fixed.
- **Supabase returns at most 1,000 rows per request**; keyword search's library download doesn't paginate. Not hit yet (largest library 149 chunks). Postgres BM25 move deferred to the indexes stage.
- **Production has 0 rows in `source_nodes`/`topic_nodes`** although eval writes them fine: production-specific, unexplained.
- Production read-only scripts load `backend/.env` from the scratchpad; eval scripts must import `evals/env.py` first (guard).

## Working with Soham

- He creates branches only when he asks you to; he commits, pushes and merges himself. No co-author lines.
- No em dashes anywhere. Keep context lean; fresh session per part.
- No cheap fixes: root cause with evidence, fix the source, test beyond the failing case, label stopgaps, end summaries with "Files created" and "Stopgaps introduced".
- Update `docs/ARCHITECTURE.md` (diagrams, status colours, known issues, "Drawn from" line) and `CODEBASE.md` with any ingestion/storage/retrieval/generation change. Section 9 there describes the evals; the two eval suites should be consolidated onto quality_v1 when generation scoring (B2-B8) is built.

## Update 2026-10-16: shipped since this handoff, and the next task

Shipped to main (all migrations applied to eval and production): delete cascade (PR #163 follow-up, migration 016: FKs + `memory/derived_store.py`, chunk ids unique per ingest), Library delete by `source_id` (#164), retrieval stats keyed by `source_id` (#165, migrations 017 then 018), step 3.2 extraction (`backend/extractors/`, migration 019, pdfplumber instead of PyMuPDF, vision v2, duplicate check by bytes/URL with Replace). Consolidation is parked by Soham; don't raise it. CODEBASE.md §6 "Step 3 data layer" has the details and the backlog.

**Next: `fix/youtube-title-language`** (Soham creates or asks for the branch). Found in production on 2026-10-16 after the extraction deploy, video `o0UmCtfL1UY`:
1. No real title: Supadata's `/v1/youtube/transcript` response has only `content`, `lang`, `availableLangs`, never a title, so every YouTube source got "YouTube video <id>" (old code too). YouTube oEmbed (`https://www.youtube.com/oembed?url=...&format=json`, free, no key) returns `title` and `author_name` ("How to Build a Custom Shopify Store using AI (Claude Code)", "Kyle Skelly").
2. Wrong language: we pass no `lang` and never check the returned one. That English video came back `lang: "ar"`, `availableLangs: ["ar"]`, extracted text 97% Arabic (likely an auto-dubbed track). MiniLM is English-only, so those passages are near-unsearchable.

Proposed fix (approved in outline, decisions pending): title from oEmbed (`provided`); request the user's language (English unless the profile says otherwise) and compare the returned `lang` code (closed ISO set, equality check, no word lists); bump `supadata` to v2; add "MD" to the File tab help text ("Upload a PDF, DOCX, or TXT file").
Open decisions for Soham: (A) refuse with "This video has no English transcript" or (B) retry with Supadata's generate-from-audio mode (more credits); approval to spend 3-5 real Supadata calls testing (this video, an English one, a non-English one). The Arabic source stays in his library until the fix ships; then re-add the link and choose Replace, or delete it.
