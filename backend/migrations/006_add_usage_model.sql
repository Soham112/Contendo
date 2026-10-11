-- Apply before deploying the usage logger that persists exact model IDs.
-- Historical events remain NULL: the original model cannot be recovered reliably.
ALTER TABLE public.usage_events ADD COLUMN IF NOT EXISTS model text;
COMMENT ON COLUMN public.usage_events.model IS
    'Exact provider model ID for this call; NULL for historical events without model tracking.';
