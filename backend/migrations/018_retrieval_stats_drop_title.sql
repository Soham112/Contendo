-- Retrieval counts: drop the title key (apply AFTER the code keyed by source_id is deployed).
--
-- Between migration 017 and the deploy, the old code could still insert rows by
-- title only (source_id NULL); the new code never reads them. They are removed,
-- source_id becomes required, and the title column and its unique key go.
BEGIN;

DELETE FROM public.source_retrieval_stats WHERE source_id IS NULL;
ALTER TABLE public.source_retrieval_stats ALTER COLUMN source_id SET NOT NULL;
ALTER TABLE public.source_retrieval_stats DROP CONSTRAINT IF EXISTS source_retrieval_stats_user_id_source_title_key;
ALTER TABLE public.source_retrieval_stats DROP COLUMN IF EXISTS source_title;

NOTIFY pgrst, 'reload schema';
COMMIT;

-- Rollback: not reversible (titles are gone). Re-add the column only together
-- with code that writes it.
