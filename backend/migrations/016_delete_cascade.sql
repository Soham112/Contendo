-- Delete cascade: derived data goes when its source or chunk goes.
--
-- Before this migration, deleting a source removed its `sources` row, Storage
-- object and chunks, but left behind entity links to the deleted chunks,
-- entities with no chunk left, consolidation chunks built from deleted text,
-- `source_nodes` rows and topic children. Replacing the business profile note
-- reused chunk ids ({source_id}_{i}), so the new chunks inherited the old
-- chunks' entity links.
--
-- 1. Cleanup of what earlier deletes left behind (the foreign keys in step 3
--    cannot be added while orphans exist). Counted read-only first on
--    2026-10-15: production 25 orphan links, 19 linkless entities, 1
--    consolidation chunk, 2 source_nodes rows, 2 topic children.
-- 2. Chunk ids unique per ingest: `ingest_id` names the chunk set an ingest
--    wrote. A replace writes a new set, then deletes the old one, so the
--    foreign key below removes the old links. Existing ids are not renamed:
--    they stay unique, and ingest_id NULL marks them as written before this.
-- 3. Foreign keys, so no delete path can leave links or hierarchy rows behind.
--    embeddings.source_id gets none: consolidation chunks store an entity_id
--    there.
--
-- Consolidation chunks (memory/consolidation_store.py) are not relational:
-- memory/derived_store.py removes the ones a deleted chunk contributed to.
BEGIN;

-- 1a. Consolidation chunks built from a chunk that no longer exists, of an
--     entity that no longer exists, or of an entity under 3 live sources (the
--     threshold consolidation runs at). Must run before the orphan links that
--     identify them are deleted.
WITH live AS (
  SELECT ce.entity_id, count(DISTINCT e.source_id) AS sources
  FROM public.chunk_entities ce JOIN public.embeddings e ON e.id = ce.chunk_id
  GROUP BY ce.entity_id
), tainted AS (
  SELECT DISTINCT ce.entity_id FROM public.chunk_entities ce
  WHERE NOT EXISTS (SELECT 1 FROM public.embeddings e WHERE e.id = ce.chunk_id)
)
DELETE FROM public.embeddings c
WHERE c.node_type = 'consolidation'
  AND (c.source_id IN (SELECT entity_id::text FROM tainted)
       OR NOT EXISTS (SELECT 1 FROM live WHERE live.entity_id::text = c.source_id AND live.sources >= 3));

-- 1b. Links to chunks that no longer exist.
DELETE FROM public.chunk_entities ce
WHERE NOT EXISTS (SELECT 1 FROM public.embeddings e WHERE e.id = ce.chunk_id);

-- 1c. Entities no chunk links to.
DELETE FROM public.entities en
WHERE NOT EXISTS (SELECT 1 FROM public.chunk_entities ce WHERE ce.entity_id = en.entity_id);

-- 1d. Hierarchy rows of deleted sources.
DELETE FROM public.source_nodes sn
WHERE sn.source_id IS NULL
   OR NOT EXISTS (SELECT 1 FROM public.sources s WHERE s.source_id = sn.source_id);

UPDATE public.topic_nodes t
SET child_source_ids = coalesce((
  SELECT string_agg(kid, ',' ORDER BY ord)
  FROM unnest(string_to_array(t.child_source_ids, ',')) WITH ORDINALITY AS k(kid, ord)
  WHERE EXISTS (SELECT 1 FROM public.sources s WHERE s.source_id = trim(kid))
), '')
WHERE t.child_source_ids <> '';

-- 2. Chunk sets.
ALTER TABLE public.embeddings ADD COLUMN IF NOT EXISTS ingest_id text;
-- The chunk set that is live for this source (NULL: chunks written before 016).
ALTER TABLE public.sources ADD COLUMN IF NOT EXISTS ingest_id text;
-- A replace in progress: {"ingest_id", "raw_storage_path"} of the new content,
-- written before its chunks. NULL when no replace is running. A crash leaves
-- it set; memory.source_store.sweep_stale_pending removes what it names.
ALTER TABLE public.sources ADD COLUMN IF NOT EXISTS pending_replace jsonb;
CREATE INDEX IF NOT EXISTS embeddings_source_id_idx ON public.embeddings (source_id);

-- 3. Foreign keys.
ALTER TABLE public.chunk_entities
  ADD CONSTRAINT chunk_entities_chunk_id_fkey
  FOREIGN KEY (chunk_id) REFERENCES public.embeddings (id) ON DELETE CASCADE;
ALTER TABLE public.source_nodes
  ADD CONSTRAINT source_nodes_source_id_fkey
  FOREIGN KEY (source_id) REFERENCES public.sources (source_id) ON DELETE CASCADE;

NOTIFY pgrst, 'reload schema';
COMMIT;

-- Rollback (the cleanup in step 1 is not reversible):
--   ALTER TABLE public.source_nodes DROP CONSTRAINT IF EXISTS source_nodes_source_id_fkey;
--   ALTER TABLE public.chunk_entities DROP CONSTRAINT IF EXISTS chunk_entities_chunk_id_fkey;
--   DROP INDEX IF EXISTS public.embeddings_source_id_idx;
--   ALTER TABLE public.sources DROP COLUMN IF EXISTS pending_replace;
--   ALTER TABLE public.sources DROP COLUMN IF EXISTS ingest_id;
--   ALTER TABLE public.embeddings DROP COLUMN IF EXISTS ingest_id;
