-- Indexes for the duplicate check that runs before extraction
-- (memory.source_store.find_duplicate): a file or image by its bytes' sha256,
-- a page or video by its normalised URL. Index only; no data changes, safe to
-- apply before or after deploying the code. Not unique: a user may keep two
-- sources with the same key by choosing to (an upload that fails dedupe today,
-- rows from before this check).
BEGIN;

CREATE INDEX IF NOT EXISTS sources_user_raw_sha256_idx
  ON public.sources (user_id, raw_sha256) WHERE raw_sha256 IS NOT NULL;
CREATE INDEX IF NOT EXISTS sources_user_source_url_idx
  ON public.sources (user_id, source_url) WHERE source_url IS NOT NULL;

COMMIT;

-- Rollback:
--   DROP INDEX IF EXISTS public.sources_user_source_url_idx;
--   DROP INDEX IF EXISTS public.sources_user_raw_sha256_idx;
