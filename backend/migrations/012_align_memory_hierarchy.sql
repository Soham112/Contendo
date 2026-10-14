-- Align the original database baseline with memory/hierarchy_store.py.
-- Preserve legacy columns/rows. Backfill only relationships and text actually
-- present in the old schema; no summaries or source relationships are invented.
BEGIN;
ALTER TABLE public.source_nodes
  ADD COLUMN IF NOT EXISTS total_chunks INTEGER,
  ADD COLUMN IF NOT EXISTS topic_id TEXT,
  ADD COLUMN IF NOT EXISTS source_summary TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
ALTER TABLE public.topic_nodes
  ADD COLUMN IF NOT EXISTS topic_id TEXT DEFAULT gen_random_uuid()::text,
  ADD COLUMN IF NOT EXISTS topic_label TEXT,
  ADD COLUMN IF NOT EXISTS topic_summary TEXT DEFAULT '',
  ADD COLUMN IF NOT EXISTS representative_tags TEXT,
  ADD COLUMN IF NOT EXISTS child_source_ids TEXT,
  ADD COLUMN IF NOT EXISTS created_at TIMESTAMPTZ DEFAULT now();
-- Some installations already have the current schema and no legacy columns.
DO $$
BEGIN
  IF EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='source_nodes' AND column_name='summary') THEN
    EXECUTE 'UPDATE public.source_nodes SET source_summary = summary WHERE source_summary IS NULL';
  END IF;
  IF EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='topic_nodes' AND column_name='tag') THEN
    EXECUTE 'UPDATE public.topic_nodes SET topic_label = COALESCE(topic_label, tag), representative_tags = COALESCE(representative_tags, tag) WHERE topic_label IS NULL OR representative_tags IS NULL';
  END IF;
  IF EXISTS (SELECT FROM information_schema.columns WHERE table_schema='public' AND table_name='topic_nodes' AND column_name='source_ids') THEN
    EXECUTE 'UPDATE public.topic_nodes SET child_source_ids = source_ids WHERE child_source_ids IS NULL';
  END IF;
END $$;
UPDATE public.topic_nodes SET topic_id = gen_random_uuid()::text WHERE topic_id IS NULL;
UPDATE public.topic_nodes SET representative_tags = '' WHERE representative_tags IS NULL;
UPDATE public.topic_nodes SET child_source_ids = '' WHERE child_source_ids IS NULL;
UPDATE public.source_nodes s SET total_chunks = (
  SELECT count(*) FROM public.embeddings e WHERE e.user_id=s.user_id AND e.source_id=s.source_id
) WHERE total_chunks IS NULL;
-- Duplicate identities must be resolved explicitly; never delete or combine rows.
CREATE UNIQUE INDEX IF NOT EXISTS source_nodes_user_source ON public.source_nodes(user_id, source_id);
CREATE UNIQUE INDEX IF NOT EXISTS topic_nodes_user_topic ON public.topic_nodes(user_id, topic_id);
NOTIFY pgrst, 'reload schema';
COMMIT;
