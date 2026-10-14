-- Billing: each user's Stripe subscription, the Stripe events already handled,
-- and how many posts each user has generated this month.
--
-- Written by memory/billing_store.py.
--
-- subscriptions: one row per user. status is Stripe's own subscription status
--   (trialing, active, past_due, canceled, unpaid, incomplete, ...) and is
--   written ONLY from a verified Stripe webhook or a server-side fetch from
--   Stripe, never from anything the browser sends. A user with no row, or with
--   only stripe_customer_id set, is on the free plan.
--
-- stripe_events: the id of every webhook event handled. The primary key is
--   what makes the webhook idempotent: a redelivered event fails the insert
--   and is acknowledged without being applied twice.
--
-- generation_usage: posts generated per user per calendar month (UTC).
--   period is 'YYYY-MM'. A new month has no row, which is how the quota resets.
--
-- reserve_generation(): adds one to the user's count for the period if that
--   keeps it within max_count, and says whether it did, in one statement, so
--   two requests at the limit cannot both get through. max_count NULL means no
--   limit. release_generation() gives one back when nothing was generated.
--
-- RLS is enabled with no policies: only the backend's service-role key can read
-- or write. Every backend query must filter by user_id.
--
-- Run this in the Supabase SQL editor, after 008.

CREATE TABLE IF NOT EXISTS public.subscriptions (
  user_id                 TEXT PRIMARY KEY,
  stripe_customer_id      TEXT UNIQUE,
  stripe_subscription_id  TEXT UNIQUE,
  status                  TEXT,
  price_id                TEXT,
  current_period_end      TIMESTAMPTZ,
  trial_end               TIMESTAMPTZ,
  cancel_at_period_end    BOOLEAN NOT NULL DEFAULT FALSE,
  created_at              TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  updated_at              TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.subscriptions ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.stripe_events (
  event_id     TEXT PRIMARY KEY,
  type         TEXT NOT NULL,
  received_at  TIMESTAMPTZ NOT NULL DEFAULT NOW()
);

ALTER TABLE public.stripe_events ENABLE ROW LEVEL SECURITY;

CREATE TABLE IF NOT EXISTS public.generation_usage (
  user_id     TEXT NOT NULL,
  period      TEXT NOT NULL,
  count       INTEGER NOT NULL DEFAULT 0 CHECK (count >= 0),
  updated_at  TIMESTAMPTZ NOT NULL DEFAULT NOW(),
  PRIMARY KEY (user_id, period)
);

ALTER TABLE public.generation_usage ENABLE ROW LEVEL SECURITY;

CREATE OR REPLACE FUNCTION public.reserve_generation(p_user_id TEXT, p_period TEXT, max_count INTEGER)
RETURNS BOOLEAN
LANGUAGE plpgsql
AS $$
DECLARE
  reserved INTEGER;
BEGIN
  INSERT INTO public.generation_usage AS usage (user_id, period, count)
  VALUES (p_user_id, p_period, 1)
  ON CONFLICT (user_id, period) DO UPDATE
    SET count = usage.count + 1, updated_at = NOW()
    WHERE max_count IS NULL OR usage.count < max_count
  RETURNING usage.count INTO reserved;
  -- A first insert when the limit is zero must not count either.
  IF reserved IS NOT NULL AND max_count IS NOT NULL AND reserved > max_count THEN
    UPDATE public.generation_usage SET count = count - 1
    WHERE user_id = p_user_id AND period = p_period;
    RETURN FALSE;
  END IF;
  RETURN reserved IS NOT NULL;
END;
$$;

CREATE OR REPLACE FUNCTION public.release_generation(p_user_id TEXT, p_period TEXT)
RETURNS VOID
LANGUAGE sql
AS $$
  UPDATE public.generation_usage
  SET count = count - 1, updated_at = NOW()
  WHERE user_id = p_user_id AND period = p_period AND count > 0;
$$;

-- Callable only with the service-role key.
REVOKE ALL ON FUNCTION public.reserve_generation(TEXT, TEXT, INTEGER) FROM PUBLIC, anon, authenticated;
REVOKE ALL ON FUNCTION public.release_generation(TEXT, TEXT) FROM PUBLIC, anon, authenticated;
GRANT EXECUTE ON FUNCTION public.reserve_generation(TEXT, TEXT, INTEGER) TO service_role;
GRANT EXECUTE ON FUNCTION public.release_generation(TEXT, TEXT) TO service_role;

-- Rollback:
--   DROP FUNCTION IF EXISTS public.release_generation(TEXT, TEXT);
--   DROP FUNCTION IF EXISTS public.reserve_generation(TEXT, TEXT, INTEGER);
--   DROP TABLE IF EXISTS public.generation_usage;
--   DROP TABLE IF EXISTS public.stripe_events;
--   DROP TABLE IF EXISTS public.subscriptions;
