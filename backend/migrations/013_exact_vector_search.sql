-- Exact per-user vector search.
--
-- match_embeddings filters by user and orders by cosine distance. With the
-- IVFFlat index (lists=100, default probes=1) Postgres answered that from the
-- index: it scanned the one list nearest the query, about 1% of all rows, and
-- applied the user filter afterwards, so most of a user's chunks were never
-- considered. Measured 2026-10-15 against exact cosine over the same stored
-- vectors: recall@8 0.03 on the main production library (149 chunks, 18 real
-- topics), 0.00-0.09 on the eval personas.
--
-- Libraries are small (largest 149 chunks), so an exact scan of one user's rows
-- is cheap: drop the approximate index and index user_id, which the filter had
-- no index for at all. match_embeddings itself is unchanged; without a vector
-- index the planner filters by user_id and sorts those rows exactly.
--
-- Revisit with an ANN index (HNSW with iterative scans, pgvector >= 0.8) only
-- when measured per-user scan time threatens the latency budget.

DROP INDEX IF EXISTS public.embeddings_embedding_idx;

CREATE INDEX IF NOT EXISTS embeddings_user_id_idx ON public.embeddings (user_id);
