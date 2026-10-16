-- One source per (user, content). Ingestion already refuses duplicate content
-- (ingestion_agent checks content_hash first); this makes the database enforce it.
--
-- Apply only after backend/scripts/backfill_sources.py has run and its
-- duplicate report shows no (user_id, content_hash) shared by two sources.
BEGIN;
DROP INDEX IF EXISTS public.sources_user_hash_idx;
CREATE UNIQUE INDEX IF NOT EXISTS sources_user_hash_key ON public.sources (user_id, content_hash);
NOTIFY pgrst, 'reload schema';
COMMIT;

-- Rollback:
--   DROP INDEX IF EXISTS public.sources_user_hash_key;
--   CREATE INDEX IF NOT EXISTS sources_user_hash_idx ON public.sources (user_id, content_hash);
