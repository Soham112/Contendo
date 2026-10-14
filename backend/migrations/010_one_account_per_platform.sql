-- Stop concurrent connects and provider callbacks bypassing the Pro limit.
-- If legacy duplicates exist, this migration fails; explicitly disconnect extra
-- accounts before re-running rather than silently removing a user's access.
CREATE UNIQUE INDEX connected_accounts_one_per_platform
ON public.connected_accounts (user_id, platform)
WHERE status <> 'disconnected';
