-- A final-text snapshot, claim resolutions and an explicit user's approval.
CREATE TABLE public.publish_approvals (
    id UUID PRIMARY KEY DEFAULT gen_random_uuid(),
    user_id TEXT NOT NULL,
    post_id BIGINT,
    content TEXT NOT NULL,
    media JSONB NOT NULL DEFAULT '[]'::jsonb,
    flags JSONB NOT NULL DEFAULT '[]'::jsonb,
    accepted_flag_ids JSONB NOT NULL DEFAULT '[]'::jsonb,
    approved_at TIMESTAMPTZ,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now()
);
-- Backend service-role only. All application queries additionally filter user_id.
ALTER TABLE public.publish_approvals ENABLE ROW LEVEL SECURITY;
CREATE INDEX publish_approvals_user ON public.publish_approvals(user_id, created_at DESC);
ALTER TABLE public.publish_jobs ADD COLUMN approval_id UUID REFERENCES public.publish_approvals(id);

CREATE FUNCTION public.freeze_publish_approval() RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
    IF OLD.approved_at IS NOT NULL THEN
        RAISE EXCEPTION 'An approved publishing snapshot is immutable';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER freeze_publish_approval BEFORE UPDATE ON public.publish_approvals
FOR EACH ROW EXECUTE FUNCTION public.freeze_publish_approval();

CREATE FUNCTION public.require_publish_approval() RETURNS trigger LANGUAGE plpgsql AS $$
DECLARE approval public.publish_approvals;
BEGIN
    -- Status/retry updates are allowed for legacy jobs; the worker rejects any
    -- legacy job lacking approval before sending it to the provider.
    IF TG_OP = 'UPDATE' THEN
        IF ROW(NEW.content, NEW.media, NEW.user_id, NEW.approval_id)
           IS NOT DISTINCT FROM ROW(OLD.content, OLD.media, OLD.user_id, OLD.approval_id) THEN
            RETURN NEW;
        END IF;
    END IF;
    SELECT * INTO approval FROM public.publish_approvals WHERE id = NEW.approval_id;
    IF NOT FOUND OR approval.approved_at IS NULL
       OR approval.user_id IS DISTINCT FROM NEW.user_id
       OR approval.content IS DISTINCT FROM NEW.content
       OR approval.media IS DISTINCT FROM NEW.media
       OR approval.post_id IS DISTINCT FROM NEW.post_id
       OR jsonb_array_length(approval.accepted_flag_ids) <> jsonb_array_length(approval.flags)
       OR EXISTS (SELECT 1 FROM jsonb_array_elements(approval.flags) flag
                  WHERE NOT (approval.accepted_flag_ids ? (flag->>'id'))) THEN
        RAISE EXCEPTION 'Publishing requires approval of this exact text and all claim flags';
    END IF;
    RETURN NEW;
END;
$$;
CREATE TRIGGER require_publish_approval BEFORE INSERT OR UPDATE ON public.publish_jobs
FOR EACH ROW EXECUTE FUNCTION public.require_publish_approval();
