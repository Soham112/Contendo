-- Publishing: the social accounts a user has connected, and the jobs that
-- publish their posts to them.
--
-- Written by memory/publish_store.py. The provider (publishing/, chosen by
-- PUBLISHING_PROVIDER) holds each user's platform tokens; these tables hold
-- only the provider's references to them, never a password or a platform token.
--
-- accounts.publishing_provider / publishing_ref: the provider a user was
--   created with, and its reference to them (one tenant per user).
--
-- connected_accounts.status: connected | needs_reconnect | disconnected.
--
-- publish_jobs:
--   content, media: what will be published, copied from the post when the job
--     is created, so a later edit to the post never changes a scheduled job.
--   account_ids: the connected_accounts.id values to publish to.
--   scheduled_at: when the user asked for it to go out (NULL: as soon as possible).
--   next_attempt_at: when the worker may next pick it up. Starts at
--     scheduled_at (or now) and moves forward on each retry.
--   status: draft | scheduled | publishing | published | failed | cancelled.
--   idempotency_key: sent to the provider on every attempt of this job, so a
--     retry can never post twice.
--   error_code: why it failed, as one of publishing.types.ErrorCode; the API
--     turns it into a message a user can act on. error_message is the
--     provider's own text, kept for support and never shown to the user.
--   results: per account, [{account_id, status, url, error_code}].
--   locked_at: when the worker last claimed it.
--
-- claim_publish_jobs(): hands the worker up to max_jobs due jobs and marks
--   them publishing, in one statement. FOR UPDATE SKIP LOCKED means two
--   workers never get the same job. A job left in publishing with no provider
--   reference for stale_minutes (the process died mid-call) is claimed again;
--   its idempotency key makes that safe.
--
-- RLS is enabled with no policies: only the backend's service-role key can read
-- or write. Every backend query must filter by user_id.
--
-- Run this in the Supabase SQL editor, after 007.

ALTER TABLE public.accounts ADD COLUMN IF NOT EXISTS publishing_provider TEXT;
ALTER TABLE public.accounts ADD COLUMN IF NOT EXISTS publishing_ref TEXT;

CREATE TABLE IF NOT EXISTS public.connected_accounts (
  id                    UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id               TEXT NOT NULL,
  provider              TEXT NOT NULL,
  provider_account_ref  TEXT NOT NULL,
  platform              TEXT NOT NULL,
  display_name          TEXT NOT NULL DEFAULT '',
  status                TEXT NOT NULL DEFAULT 'connected'
                        CHECK (status IN ('connected', 'needs_reconnect', 'disconnected')),
  created_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at            TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  UNIQUE (user_id, provider, provider_account_ref)
);

CREATE INDEX IF NOT EXISTS idx_connected_accounts_user
  ON public.connected_accounts (user_id);

ALTER TABLE public.connected_accounts ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.publish_jobs (
  id                 UUID PRIMARY KEY DEFAULT gen_random_uuid(),
  user_id            TEXT NOT NULL,
  post_id            INTEGER NULL REFERENCES public.posts (id) ON DELETE SET NULL,
  content            TEXT NOT NULL,
  media              JSONB NOT NULL DEFAULT '[]'::jsonb,
  account_ids        JSONB NOT NULL DEFAULT '[]'::jsonb,
  scheduled_at       TIMESTAMPTZ,
  next_attempt_at    TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  status             TEXT NOT NULL DEFAULT 'scheduled'
                     CHECK (status IN ('draft', 'scheduled', 'publishing', 'published', 'failed', 'cancelled')),
  provider           TEXT,
  provider_post_ref  TEXT,
  idempotency_key    UUID NOT NULL UNIQUE DEFAULT gen_random_uuid(),
  error_code         TEXT,
  error_message      TEXT,
  results            JSONB NOT NULL DEFAULT '[]'::jsonb,
  attempts           INTEGER NOT NULL DEFAULT 0,
  locked_at          TIMESTAMPTZ,
  published_at       TIMESTAMPTZ,
  created_at         TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at         TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

CREATE INDEX IF NOT EXISTS idx_publish_jobs_user_created
  ON public.publish_jobs (user_id, created_at DESC);

CREATE INDEX IF NOT EXISTS idx_publish_jobs_due
  ON public.publish_jobs (next_attempt_at)
  WHERE status IN ('scheduled', 'publishing');

CREATE INDEX IF NOT EXISTS idx_publish_jobs_provider_ref
  ON public.publish_jobs (provider, provider_post_ref);

ALTER TABLE public.publish_jobs ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.claim_publish_jobs(max_jobs INTEGER, stale_minutes INTEGER)
RETURNS SETOF public.publish_jobs
LANGUAGE sql
AS $$
  UPDATE public.publish_jobs AS job
  SET status = 'publishing',
      locked_at = NOW(),
      attempts = job.attempts + 1,
      updated_at = NOW()
  WHERE job.id IN (
    SELECT id
    FROM public.publish_jobs
    WHERE (status = 'scheduled' AND next_attempt_at <= NOW())
       OR (status = 'publishing'
           AND provider_post_ref IS NULL
           AND locked_at < NOW() - make_interval(mins => stale_minutes))
    ORDER BY next_attempt_at
    LIMIT max_jobs
    FOR UPDATE SKIP LOCKED
  )
  RETURNING job.*;
$$;

-- Callable only with the service-role key.
REVOKE ALL ON FUNCTION public.claim_publish_jobs(INTEGER, INTEGER) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.claim_publish_jobs(INTEGER, INTEGER) TO service_role;

-- Rollback:
--   DROP FUNCTION IF EXISTS public.claim_publish_jobs(INTEGER, INTEGER);
--   DROP TABLE IF EXISTS public.publish_jobs;
--   DROP TABLE IF EXISTS public.connected_accounts;
--   ALTER TABLE public.accounts DROP COLUMN IF EXISTS publishing_ref;
--   ALTER TABLE public.accounts DROP COLUMN IF EXISTS publishing_provider;
