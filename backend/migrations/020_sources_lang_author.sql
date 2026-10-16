-- The language of a source's extracted text and the creator a provider names.
--
-- lang: ISO 639-1 code identified at ingestion (utils/language.py), NULL when
-- the text is too short to tell or the source predates this column. Sources in
-- a language the embedder can't search are refused, so new rows hold 'en' or NULL.
-- author: the creator named by the provider, e.g. a YouTube channel from oEmbed.
-- Not authorship (who wrote it relative to the user; see 014).
--
-- Apply before deploying the code that writes these columns.
BEGIN;

ALTER TABLE public.sources ADD COLUMN IF NOT EXISTS lang text;
ALTER TABLE public.sources ADD COLUMN IF NOT EXISTS author text;

COMMIT;

-- Rollback (after reverting the code):
--   ALTER TABLE public.sources DROP COLUMN IF EXISTS author;
--   ALTER TABLE public.sources DROP COLUMN IF EXISTS lang;
