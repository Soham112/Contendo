# Step 3.4 analysis: chunking and embedding input

Analysis only, 2026-10-16, code at `aa7f56c` (main). Nothing was changed: no code, migrations, prompts or data. Every number below was measured in this session, on the eval project (read-only, through the evals env guard) or on the local export of your library (`evals/private/quality_v1/me/export.json`, your production rows as of 2026-10-16). Production was not queried. Token counts use the embedder's own tokenizer (`all-MiniLM-L6-v2` WordPiece).

## Headline

1. The truncation is real and large in a real library: in yours, 134 of 149 chunks (90%) are over the window and 66% of the stored text never reaches an embedding.
2. It explains none of the current quality_v1 misses. The 8 synthetic personas have no chunk over the window (largest 250 tokens), and your one miss is a chunk under the window. 0 of 23 missed sources are caused by truncation.
3. So quality_v1, as built, cannot measure step 3.4. The test set needs long-document cases with passage-level labels before any chunking design can be chosen by measurement.
4. The largest recall gap is elsewhere: 16 of 23 misses are the business profile note, and 9 are cases where nothing passed the 0.30 relevance floor.

## Claims checked

| Claim | Verdict | Evidence |
|---|---|---|
| `CHUNK_SIZE_WORDS = 500`, `OVERLAP_WORDS = 50` | Correct | `backend/utils/chunker.py:3-4` |
| `re.sub(r"\s+", " ", ...)` flattens every newline first | Correct | `chunker.py:16`; measured: 0 newlines survive in any extractor's output after `chunk_text` (section 4) |
| Call sites `ingestion_agent.py:373` and `source_rebuild.py:66` | Correct | the only two callers of `chunk_text` |
| 384 dims, `max_seq_length` 256 | Correct, with a precision | measured; 256 includes `[CLS]` and `[SEP]`, so a chunk's own text is cut after **254** word-pieces. `embed_texts` at `memory/vector_store.py:65` encodes whole chunks and truncates silently |
| Production: 224/250 (89%), median 640, 77% lost, one chunk 13,729 tokens | Not re-verified (no production access); consistent | your library: 134/149 (90%), median 634, 66% lost, largest 10,468 |
| "Some path does not go through the 500-word limit" | **Wrong** | every live write path goes through `chunk_text` (section 1). The oversized chunk is 500 *words*; the limit is on whitespace words, not tokens |
| BM25 in memory, RRF merge, titles in neither index | Correct | `_fetch_corpus_for_bm25` `vector_store.py:275`, `_query_bm25` `:351`, `_rrf_merge` `:419`; the BM25 document is `content` only (`:297`), the embedding is `content` only (`:122`) |
| "Nearshoring" cosine 0.19 | Correct | tc-03: best chunk cosine 0.193; its title alone scores 0.682 |
| `get_adjacent_chunks` expands a hit with neighbours | Correct, and unused by the live prompt | `vector_store.py:681`, ±1 `chunk_index` per matched source (`window=1`), called from `retrieval_agent.py:128`; the result goes only into `retrieved_context`, which `pipeline/trace.py:97` records and the D-Opus-low draft does not read |

## 1. The oversized chunk

Every path that writes `embeddings` rows:

| Path | Writer | Through `chunk_text`? |
|---|---|---|
| Typed and pasted notes, pasted transcripts (`/ingest`) | `ingest_content` → `upsert_chunks` (`vector_store.py:148`) | yes |
| Files, URLs, YouTube links, images (`/ingest-file`, `/scrape-and-ingest`, `/ingest`) | same, after `backend/extractors/` | yes |
| Obsidian (`routers/obsidian.py:41`) | same | yes |
| Business profile note (`routers/account.py:134`) | same | yes |
| Onboarding story (`routers/onboarding.py:66`) | same | yes |
| Pillar details note (`routers/generate.py:264`) | same | yes |
| Consolidation briefs | `upsert_consolidation_chunk` (`memory/consolidation_store.py:53`) | **no**, but bounded by Haiku `max_tokens=300` (`agents/consolidation_agent.py:123`); largest in eval: 250 word-pieces |

No migration or script inserts `embeddings` rows; git history shows no other writer since the initial commit (`baa6afe`).

How the giant chunk is made: `chunk_text` limits whitespace words, so a "word" can be any length. Your largest chunk (an article, "Building a Safe & Secure Text-to-SQL System with a Local LLM", ingested 2026-03-21, chunk 4 of 6) has exactly 500 words and 18,412 characters; 71 of its words are Medium sign-in tracking links such as `[](https://medium.com/m/signin?actionUrl=https%3A%2F%2Fmedium.com%2F_%2Fbookmark%2F...)` (up to 419 characters each), and they are 89% of its characters. A URL splits into dozens of word-pieces, so 500 words became 10,468 tokens. It came from the old URL scraper, which stored Jina's markdown with link targets. The new URL extractor (`jina_reader` v2, `normalize_markdown`) keeps link text and drops targets, so this cause is gone for new pages, but the chunker still has no token bound: URLs in notes, code, CJK text or tables without spaces can still produce oversized chunks. The production 13,729-token chunk is almost certainly the same mechanism (another old-scraper page); the SQL in section 2 finds it.

## 2. The loss, measured

Your library (export of production, 2026-10-16; identical to persona `me` as seeded in eval):

| source_type | chunks | over 254 | share | median tokens | max tokens | text past the cut |
|---|---|---|---|---|---|---|
| article | 99 | 94 | 95% | 655 | 10,468 | 71% |
| image | 15 | 14 | 93% | 347 | 697 | 31% |
| note | 21 | 14 | 67% | 562 | 808 | 55% |
| saved_content | 1 | 1 | 100% | 278 | 278 | 8% |
| youtube | 13 | 11 | 85% | 622 | 661 | 56% |
| **all** | **149** | **134** | **90%** | **634** | **10,468** | **66%** |

"Text past the cut" is the share of characters after the 254th word-piece.

Of the article tokens, 47% are old-scraper link markup: re-normalising the stored article text with `normalize_markdown` takes it from 102,752 to 54,545 tokens (notes, images, YouTube: 0% change).

The 8 synthetic personas (rf, tc, ni0, ni1, re, fs, bo, nb; 49 chunks): **0 chunks over 254**; median 62, largest 250 (a consolidation brief). By type: article 14 (max 75), business_profile 4 (max 120), consolidation 3 (max 250), note 2, personal_note 21 (max 149), saved_content 2, youtube 3 (max 63).

Production, read-only, for you to run (SQL cannot run the WordPiece tokenizer, so token counts need the export plus the snippet below):

```sql
-- 1) Rows to measure (read-only). Export the result as CSV.
select e.user_id, e.source_id, e.source_type, coalesce(e.node_type, 'chunk') as node_type,
       e.chunk_index, e.total_chunks, e.ingested_at, e.content
from public.embeddings e
order by e.user_id, e.source_id, e.chunk_index;

-- 2) Quick look without the tokenizer: the biggest chunks and their longest "word".
select e.user_id, e.source_id, e.source_type, e.chunk_index, length(e.content) as chars,
       array_length(regexp_split_to_array(trim(e.content), '\s+'), 1) as words,
       (select max(length(w)) from regexp_split_to_table(e.content, '\s+') w) as longest_word
from public.embeddings e
order by length(e.content) desc
limit 10;
```

```python
# Token counts for the CSV from query 1 (run with backend/venv/bin/python; no network, no database).
import csv, sys, statistics as st
from collections import defaultdict
from sentence_transformers import SentenceTransformer
tok = SentenceTransformer("all-MiniLM-L6-v2").tokenizer; LIMIT = 254
g = defaultdict(list)
for r in csv.DictReader(open(sys.argv[1])):
    enc = tok(r["content"], add_special_tokens=False, return_offsets_mapping=True)
    n, chars = len(enc["input_ids"]), len(r["content"])
    cut = enc["offset_mapping"][LIMIT][0] if n > LIMIT else chars
    for k in (r["node_type"] if r["node_type"] == "consolidation" else r["source_type"], "ALL"):
        g[k].append((n, chars, cut))
for k, v in sorted(g.items()):
    print(k, len(v), "over:", sum(n > LIMIT for n, _, _ in v), "median:", st.median(n for n, _, _ in v),
          "max:", max(n for n, _, _ in v), "lost:", round(sum(c - u for _, c, u in v) / sum(c for _, c, _ in v), 2))
```

## 3. Does truncation explain the misses?

Run `2026-10-16-exact-vector` (the latest baseline), 61 cases (40 dev, 21 hold-out). A case misses when an expected source (each `must_use_all` label, or the `must_use_any` group as one unit) is not in the top k, k being the run's cutoff (the chunks that passed the relevance floor). For each missed source I embedded, with the production model and the production query (`f"{topic}. {context}"`, `retrieval_agent.py:331`): the head of each chunk (what is embedded today), every 254-token window past the cut, and the source title. "Truncation" means a window past the cut would have scored at least as high as a chunk that made the top k and higher than the head.

23 cases miss one source each (15 dev, 8 hold-out). Verdicts: **truncation 0**, title 1, neither 22.

| case | split | missed | k | gate | best head cosine | past the cut | title cosine |
|---|---|---|---|---|---|---|---|
| rf-03 | dev | rf-s08 | 0 | low_coverage | 0.287 | none (fits) | **0.972** |
| rf-04 | dev | rf-s02/s04/s08 | 0 | low_coverage | 0.093 | none | 0.160 |
| tc-03 | holdout | tc-s04 | 0 | low_coverage | 0.193 | none | **0.682** |
| ni1-04 | dev | ni1-s01 | 0 | low_coverage | 0.119 | none | 0.011 |
| re-01, re-02, re-03, re-07, re-08 | dev | re-bp | 6, 5, 4, 5, 0 | pass ×4, low_coverage | 0.18-0.30 | none | ≤ 0.20 |
| fs-01, fs-03, fs-04, fs-05, fs-07 | holdout | fs-bp | 2, 1, 1, 1, 0 | pass ×4, low_coverage | 0.09-0.22 | none | ≤ 0.10 |
| bo-01, bo-03, bo-04, bo-05, bo-06 | dev, holdout, dev, dev, dev | bo-bp | 1, 0, 0, 0, 1 | pass, low_coverage ×3, pass | 0.01-0.25 | none | ≤ 0.11 |
| nb-02, nb-03, nb-04 | dev, holdout, dev | nb-bp | 1, 0, 0 | pass, skipped_first_post ×2 | 0.12-0.28 | none | ≤ 0.10 |
| me-04 | dev | me:e7cac381 | 5 | pass | 0.296 (bar 0.332) | none (fits) | **0.362** |

Gate decisions over the 23: pass with k > 0: 12; low_coverage (nothing over the 0.30 floor): 9; skipped_first_post: 2.

Reading:
- Chunking explains none of the 0.57 dev recall gap as measured. The gap is mostly the business profile note (16 of 23: `re-bp`, `fs-bp`, `bo-bp`, `nb-bp`), whose short summary text rarely resembles a topical query (best cosine 0.01-0.30). That is a question of how the profile reaches the prompt (retrieved like a note, or always included as context), not of chunking.
- Titles would rescue 3: rf-03 (0.972), tc-03 (0.682), me-04 (0.362), all above their bars and the 0.30 floor.
- 9 misses are the coverage gate at the 0.30 floor, which the known-issues table already flags for recalibration.
- Truncation could only matter in your library, where its misses are 1 of 9 cases. Large text loss with no measured miss means the test set does not ask about text deep inside long documents, not that the loss is harmless.

## 4. Structure available

The eval library cannot show this: all 110 eval sources are `rebuilt_from_chunks` with no newlines (seeded before the new extractors). The examples below are the real extractors run on the repository's saved fixtures (real Jina and Supadata responses; generated PDF and DOCX used by the tests). `⏎` marks a newline.

| Extractor | Survives into `ingest_content` | After `chunk_text` |
|---|---|---|
| URL (`extractors/url.py`, Jina JSON) | headings, paragraphs, lists; link text without targets. Wikipedia RAG fixture: 15,714 chars, 92 newlines, 2 headings, 27 list items | 0 newlines |
| PDF (`extractors/file.py`, pdfplumber) | paragraphs (blank line between), running headers and footers removed; no page-break marker | 0 newlines |
| DOCX | headings as `#`, tables as `a \| b` rows, paragraphs | 0 newlines |
| Markdown file, Obsidian | headings, paragraphs, lists, tables; Obsidian aliases kept, embeds and block ids removed | 0 newlines |
| Image (`extractors/image.py`) | two sections: `# Text in the image` and `# What the image shows` | 0 newlines |
| YouTube (`extractors/youtube.py`) | none: Supadata's timed segments are joined with spaces; the offsets stay in `sources.raw_json` | n/a |

Examples:

```text
URL:   From Wikipedia, the free encyclopedia⏎⏎**Retrieval-augmented generation** (**RAG**) is a technique that enables large language models ...
PDF:   Paragraph one of page 1 talks about section1 the next line of paragraph one.⏎⏎Paragraph two of page 1 starts after a gap.⏎⏎Paragraph one of page 2 ...
DOCX:  # Launch plan⏎⏎## Goals⏎⏎Ship the importer by May.⏎⏎Owner | Due⏎Priya | May 3
MD:    # Pricing⏎⏎We tested three tiers.⏎⏎- Starter: $9⏎- Team: $29⏎⏎| Plan | Seats |⏎|---|---|⏎| Team | 5 |
Obsidian: # Weekly review⏎⏎Shipped the retrieval fix⏎⏎- [ ] follow up with  team
YouTube segment: {"text": "In today's video, I'm going to show you", "offset": 0, "duration": 3360}
```

## 5. Options

Measured on your library (51 sources, 124,316 tokens of text rebuilt from the export with `utils/source_rebuild.rebuild_source`), on this Mac's CPU. Budget 230 tokens of text plus up to ~24 for a "title › heading" line, inside the 254 limit.

| Design | Rows | Most rows for one source | Largest | Over 254 | Embed whole library | BM25 build + one query |
|---|---|---|---|---|---|---|
| today (500 words) | 149 | 26 | 10,468 | 134 | 1.28 s | 63 ms |
| (a) 230-token window, 30 overlap | 639 | 98 | 232 | 0 | 3.43 s | 71 ms |
| (b) structure-aware, packed to 230 | 655 | 105 | 231 | 0 | 3.43 s | 49 ms |
| (c) 500-word parents stored, 230-token children embedded | 149 parents + 730 children | 119 | 231 | 0 | 4.30 s | 57 ms |

(b) here packs sentences (`utils/sentences.sentence_offsets`) because your rebuilt text has no newlines; with extractor output it splits on headings and paragraphs first. Baseline retrieval on your library: `hybrid_search` median 0.34 s, all retrieval steps median 0.92 s (max 1.05 s).

**(a) Same splitter, token budget.** Window of 230 word-pieces, 30 overlap, counted with the embedder's tokenizer (a word budget cannot bound tokens, section 1). Embedded = stored = BM25 = the chunk. Rows ×4.3. Ingest embedding ×2.7. The drafter gets 230 tokens per hit instead of ~634, so 8 hits are ~1,840 tokens instead of ~5,000 (smaller prompt, less context per hit: measure). Your library would be 639 rows, 64% of the 1,000-row BM25 fetch cap, so paginate or move BM25 into Postgres first. `get_adjacent_chunks` ±1 now covers ~690 tokens instead of ~1,900. `source_rebuild.py:66` checks chunker_v1 output only; keep it for v1 rows. Entity links (per chunk) are lost with the old rows (cascade, migration 016); `memory_context` and tags are per document and copied. Rollback: re-chunk with v1 from `sources.extracted_text` (deterministic).

**(b) Structure-aware, packed.** Stop flattening newlines; split at headings, then paragraphs, list items and table rows; pack consecutive blocks up to 230 tokens; a block over budget splits by sentence, then by tokens. Embedded text = "title › heading path" + chunk; stored content = chunk only; BM25 document = title + heading + chunk. Counts and costs as (a). Chunks respect sections, so a hit is a coherent passage, and the heading gives short chunks their context. Sources without structure (rebuilt from chunks, YouTube) fall back to sentence packing; YouTube could later split on Supadata's time gaps. Same cap, adjacency, rebuild and entity consequences as (a). Rollback as (a).

**(c) Parent and child.** Keep stored chunks for generation (today's or structure-aware parents) and embed 230-token children that point to them (a `chunk_embeddings` table or child rows with `parent_id`). Retrieval matches children, groups by parent, and sends parents to the drafter, so context per hit is unchanged. Entity links, `memory_context` and retrieval stats stay on parents, untouched. Costs: most rows (879), most embedding time (×3.4), a new table or row kind, RPC and BM25 changes (index children or parents), and a parent may be retrieved for a small child match while its other text is unrelated. The prompt stays large. Rollback: drop the children and embed parents again.

Common to all: record the chunker version on every chunk and source (it is recorded nowhere today except the backfill's `chunker_v1`), and fix the 1,000-row fetch before or with the change.

## 6. Titles

| Way | What it does | Fits |
|---|---|---|
| Prepend to the embedded text | "title › heading" line on every chunk's embedding input, not its stored content | (a), (b), (c) children; cheapest; costs ~10-24 of the 254 tokens |
| Separate title embedding | one vector per source, a third ranked list in RRF, mapped to the source's best chunk | any; best for exact-title queries (rf-03 0.972); one more query per request |
| Add to the BM25 document | title words in each chunk's keyword document | any; trivial; needs the Lucene IDF (GENERATION_ARCHITECTURE.md §7.2) so recurring title words keep weight |

Measured potential: titles would rescue rf-03, tc-03 and me-04 (section 3). Prepending plus BM25 suits (b) best; a separate title vector is worth testing only if prepending misses rf-03-style exact-title queries.

## 7. Experiment plan

1. Extend quality_v1 with long-document cases first. Without them no option can win or lose (section 3). Add 2-3 long sources per persona from real long pages, transcripts and PDFs (the Wikipedia RAG page, the YouTube fixtures, a multi-page report), and 10-15 cases whose answer sits past token 254, labelled at passage level (the planned Evidence Recall in QUALITY.md), with a hold-out share as today. Re-score the current chunker on it: this is the new baseline B0.
2. Seed one eval user per design (persona slug plus a design suffix) with a chunker chosen by config, $0 (local embeddings; tags and classifiers are not needed for retrieval scoring, or reuse the existing ones).
3. Runs: B0 (today), (a), (b), (b)+title in BM25, (c). Each against B0 on the same cases. Report dev and hold-out separately for: synthetic cases, your 9 private cases, and the new long-document cases. Metrics: Recall@cutoff, Recall@1/3/5, MRR, Precision, off-topic rate, gate decisions.
4. Pick: the simplest design that raises long-document recall and MRR on dev and hold-out without lowering any synthetic or private metric. Prefer (b) over (a) at equal scores (coherent passages, room for the heading); choose (c) only if (a) and (b) lose generation context in a blind read.
5. Latency guard: retrieval step timings from the same runs (`retrieval_timings`); median total must stay within noise of B0 (0.92 s on your library). Also measure ingest time per source and the BM25 fetch payload. Then one draft per case for the winner vs B0 to confirm time-to-first-word does not get worse with the smaller prompt.

## 8. Re-ingest plan

Re-chunking needs no re-extraction: every source keeps its `extracted_text` in `sources` (also the 80 production sources rebuilt from chunks). Order:

1. Ship the new chunker with a version stamp, used for new ingests only; old sources keep chunker_v1.
2. Per source, one at a time: chunk `extracted_text`; embed; write the new chunk set with a new `ingest_id` (begin_replace), copying document-level fields (tags, `memory_context`, `source_type`, title); switch the row; the old set and its entity links are deleted by the cascade (migration 016). No model calls: this is a re-chunk, not `ingest_content`.
3. Entity links: re-extracting entities is a Haiku call per new chunk (×4 calls); the alternative is mapping each old link to the new chunks that overlap its old chunk's text span. Decide by cost. Retrieval stats are keyed by `source_id` and survive. Source summaries and topic nodes are per source and survive.
4. Invalidate the user's BM25 cache after each user.

What a user sees: at every moment each source has exactly one live chunk set (the replace mechanism), so retrieval works throughout; for the seconds of a swap retrieval can see both sets, as with any replace. The Library's passage counts grow ~4×. Rollback: re-chunk with v1 from the same text (deterministic, checked by `source_rebuild`), plus re-mapping entity links.

Sources with no stored original (`rebuilt_from_chunks`: production 80, eval all 110, your whole library): they still have `extracted_text`, so they can be re-chunked, but not re-extracted. Their text keeps flaws of the old extractors: 47% of your article tokens are link markup, which `normalize_markdown` removes structurally from the stored text. For these, re-chunk from `normalize_markdown(extracted_text)` for articles, or ask the user to re-add the link (Replace), which also fetches a real title.

## 9. Order relative to provenance

Confirmed for per-chunk labels, refuted for source-level ones. `sources.authorship` is per source and survives re-chunking. Per-chunk labels (`memory_context` on each chunk, `chunk_authorship`) are written on chunk rows, which re-chunking replaces: labelling them first means labelling again. Today `memory_context` is one value per document copied to every chunk, so nothing per chunk would be lost yet; the waste appears only if the classifier labels chunks individually. Structure-aware chunks also give the classifier better units (a section, not 500 flattened words). Chunking first is the cheaper order if provenance labels chunks; if provenance stays per source, either order works.

## Decisions for Soham

1. **Test set first.** Extend quality_v1 with long-document cases and passage-level labels before choosing a design / choose now from the simulation. Default: extend first. Reason: the current set has no chunk over the window, so no design can show a gain.
2. **Design.** (a) token window / (b) structure-aware packed / (c) parent-child. Default: (b), with title and heading prepended to the embedded text and the title added to BM25. Reason: same cost as (a), coherent passages, uses the structure the extractors now keep; (c) only if the blind read shows lost context.
3. **The business profile note.** Keep retrieving it like a note / include it as context for business posts. Default: decide in its own branch before 3.4. Reason: it is 16 of the 23 measured misses, and chunking cannot fix it.
4. **Old-scraper articles.** Re-chunk stored text as is / apply `normalize_markdown` first / ask users to re-add links. Default: `normalize_markdown` first, then re-chunk. Reason: removes 47% junk tokens without a fetch, keeps the user's library intact.
5. **Entity links on re-chunk.** Re-extract per new chunk (paid, ~4× calls) / map old links by text span ($0). Default: map by span, re-extract only if the mapping leaves entities unlinked. Reason: entity enrichment is already a weak signal (substring matching, known issue), so paying 4× for it is premature.
