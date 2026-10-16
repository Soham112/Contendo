-- Retrieval counts keyed by source_id, not title (apply BEFORE deploying the code).
--
-- source_retrieval_stats was unique on (user_id, source_title): sources sharing a
-- title shared one count, and sources with no title were never counted. Titles
-- are not unique (one production library has 20 sources with an empty title).
--
-- Backfill, per existing row, by the sources with that user and title:
--   exactly one  -> the row moves to that source_id
--   several      -> the count can't be split between them: the row is deleted,
--                   so each starts at 0 (reset, not guessed)
--   none         -> deleted (a deleted source, or a consolidation brief, which
--                   is not a source)
-- Read-only preview, 2026-10-16: production 37 rows, all one source; eval 110
-- rows, 97 one source, 13 consolidation briefs; no title matched several.
--
-- source_title stays until migration 018 so the code deployed before this one
-- keeps working (its increments still land on the backfilled rows, which keep
-- their title). The foreign key deletes a source's count with the source.
BEGIN;

ALTER TABLE public.source_retrieval_stats ADD COLUMN IF NOT EXISTS source_id text;

WITH matches AS (
  SELECT st.id, min(s.source_id) AS source_id, count(*) AS n
  FROM public.source_retrieval_stats st
  JOIN public.sources s ON s.user_id = st.user_id AND s.title = st.source_title
  WHERE st.source_id IS NULL
  GROUP BY st.id
)
UPDATE public.source_retrieval_stats st
SET source_id = matches.source_id
FROM matches
WHERE matches.id = st.id AND matches.n = 1;

-- Several sources or none: reset (see above).
DELETE FROM public.source_retrieval_stats WHERE source_id IS NULL;

CREATE UNIQUE INDEX IF NOT EXISTS source_retrieval_stats_user_source_idx
  ON public.source_retrieval_stats (user_id, source_id);
ALTER TABLE public.source_retrieval_stats
  ADD CONSTRAINT source_retrieval_stats_source_id_fkey
  FOREIGN KEY (source_id) REFERENCES public.sources (source_id) ON DELETE CASCADE;

NOTIFY pgrst, 'reload schema';
COMMIT;

-- Rollback (the backfill's deletes are not reversible):
--   ALTER TABLE public.source_retrieval_stats DROP CONSTRAINT IF EXISTS source_retrieval_stats_source_id_fkey;
--   DROP INDEX IF EXISTS public.source_retrieval_stats_user_source_idx;
--   ALTER TABLE public.source_retrieval_stats DROP COLUMN IF EXISTS source_id;
