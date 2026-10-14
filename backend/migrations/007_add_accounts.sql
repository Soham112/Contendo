-- Accounts: one row per user for what is true of the user rather than of their
-- writing voice (which stays in profiles.data).
--
-- Written by memory/account_store.py through PUT /account/segment and
-- POST /account/segment/skip. A user with no row has not answered yet.
--
-- segment: NULL until the user answers "Who are you creating content for?".
-- business_niche: a key from backend/config/niches.py (the one list, validated
--   by the API, so there is no CHECK here to fall out of step with it).
-- business_niche_other: the user's own words when business_niche is 'other'.
-- business_profile: {business_name, service_area, website, services, tone,
--   tone_notes}. Business users only.
-- segment_skipped_at: when the user last chose "Skip for now"; the question is
--   asked again after account_store.SEGMENT_REASK_DAYS.
--
-- user_id is TEXT, like every table added since the baseline.
--
-- RLS is enabled with no policies: only the backend's service-role key can read
-- or write. Every backend query must filter by user_id.
--
-- Run this in the Supabase SQL editor.

CREATE TABLE IF NOT EXISTS public.accounts (
  user_id               TEXT PRIMARY KEY,
  segment               TEXT CHECK (segment IN ('business', 'individual')),
  business_niche        TEXT,
  business_niche_other  TEXT,
  business_profile      JSONB,
  segment_skipped_at    TIMESTAMPTZ,
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.accounts ENABLE ROW LEVEL SECURITY;

-- Rollback:
--   DROP TABLE IF EXISTS public.accounts;
