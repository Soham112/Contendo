-- Provenance step 3.3: the classifier starts writing sources.authorship
-- (agents/provenance_agent.py via agents/ingestion_agent.py) and the user can
-- set it (PATCH /sources/{id}/authorship). Columns exist since 014; no new ones.
--
-- Apply to the eval project first, then production, BEFORE deploying the
-- backend that writes authorship. Nothing reads authorship yet.
--
-- 1. Index for "sources by label" (the Library's needs-your-answer filter,
--    later readers).
-- 2. user_stated and system_inferred are rule-only labels: the classifier
--    never sets them (it only outputs user_authored or external).
BEGIN;

CREATE INDEX IF NOT EXISTS sources_user_authorship_idx ON public.sources (user_id, authorship);

ALTER TABLE public.sources DROP CONSTRAINT IF EXISTS sources_rule_only_authorship;
ALTER TABLE public.sources ADD CONSTRAINT sources_rule_only_authorship CHECK (
  authorship_set_by IS DISTINCT FROM 'classifier'
  OR authorship NOT IN ('user_stated', 'system_inferred')
);

NOTIFY pgrst, 'reload schema';
COMMIT;

-- Rollback:
--   ALTER TABLE public.sources DROP CONSTRAINT IF EXISTS sources_rule_only_authorship;
--   DROP INDEX IF EXISTS public.sources_user_authorship_idx;
