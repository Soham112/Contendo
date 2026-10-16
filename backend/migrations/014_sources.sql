-- Preserve originals: one row per source, the record every derived row
-- (chunks, embeddings, entities, summaries) can be rebuilt from.
--
-- Text originals live in this table. Binary originals (uploaded files, images)
-- live in the private Storage bucket `source-originals` at
-- {user_id}/{source_id}/{sha256}{ext}; the row holds the path.
--
-- status: a row is written as 'pending' BEFORE its Storage object or chunks,
-- and set to 'ready' after the chunks are stored. Every object and chunk
-- therefore has a row naming it, and memory.source_store.sweep_stale_pending
-- removes whatever a crash left behind.
--
-- origin_status: 'original' = what the user gave us; 'rebuilt_from_chunks' =
-- reconstructed by backend/scripts/backfill_sources.py from stored chunks
-- (line breaks lost, raw_text NULL). The two must never be confused.
--
-- authorship: who wrote the text. Written only by the user, a rule (business
-- profile form) or the provenance classifier; nothing reads it until that
-- classifier is measured on quality_v1. NULL = unknown.
--
-- Identities (step 3, decision 4): when the identities table exists, add
--   identity_id text REFERENCES public.identities(identity_id)
-- here, next to user_id. Not added now.
--
-- The unique index on (user_id, content_hash) is migration 015, applied after
-- the backfill's duplicate report has been resolved.
BEGIN;

CREATE TABLE IF NOT EXISTS public.sources (
  source_id          text PRIMARY KEY,
  user_id            text NOT NULL,
  status             text NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','ready')),
  input_type         text NOT NULL CHECK (input_type IN
                       ('note','file','url','youtube','image','obsidian','business_profile','unknown')),
  title              text,
  title_origin       text CHECK (title_origin IN ('provided','derived')),
  source_url         text,
  original_filename  text,
  fetched_at         timestamptz,
  raw_text           text,
  raw_json           jsonb,
  raw_storage_path   text,
  raw_mime           text,
  raw_size_bytes     bigint,
  raw_sha256         text,
  raw_omitted_reason text,
  extracted_text     text NOT NULL,
  extractor          text NOT NULL,
  extractor_version  text NOT NULL,
  extracted_at       timestamptz NOT NULL DEFAULT now(),
  content_hash       text NOT NULL,
  origin_status      text NOT NULL CHECK (origin_status IN ('original','rebuilt_from_chunks')),
  rebuild_check      text CHECK (rebuild_check IN ('rechunk_exact','rechunk_mismatch','incomplete')),
  rebuild_hash_match boolean,
  authorship         text CHECK (authorship IN
                       ('user_authored','user_stated','external','system_inferred')),
  authorship_set_by  text CHECK (authorship_set_by IN ('user','classifier','rule')),
  authorship_detail  jsonb,
  created_at         timestamptz NOT NULL DEFAULT now(),
  updated_at         timestamptz NOT NULL DEFAULT now(),
  CHECK ((origin_status = 'rebuilt_from_chunks') = (rebuild_check IS NOT NULL))
);

CREATE INDEX IF NOT EXISTS sources_user_idx ON public.sources (user_id);
CREATE INDEX IF NOT EXISTS sources_user_hash_idx ON public.sources (user_id, content_hash);
CREATE INDEX IF NOT EXISTS sources_pending_idx ON public.sources (updated_at) WHERE status = 'pending';

-- Same pattern as every other table: RLS on, no policies, so only the
-- backend's service role can read or write.
ALTER TABLE public.sources ENABLE ROW LEVEL SECURITY;

-- Per-chunk authorship, for chunks whose authorship differs from their
-- source's (a note quoting an article). NULL = same as the source.
ALTER TABLE public.embeddings
  ADD COLUMN IF NOT EXISTS chunk_authorship text CHECK (chunk_authorship IN
    ('user_authored','user_stated','external','system_inferred'));

-- Private bucket, 10 MB per object (the upload limit). No storage.objects
-- policies: deny-all to clients, like the tables.
INSERT INTO storage.buckets (id, name, public, file_size_limit)
VALUES ('source-originals', 'source-originals', false, 10485760)
ON CONFLICT (id) DO NOTHING;

NOTIFY pgrst, 'reload schema';
COMMIT;

-- Rollback (empty bucket first, from the Storage UI or API):
--   DELETE FROM storage.buckets WHERE id = 'source-originals';
--   ALTER TABLE public.embeddings DROP COLUMN IF EXISTS chunk_authorship;
--   DROP TABLE IF EXISTS public.sources;
