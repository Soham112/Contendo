"use client";

import { useEffect, useState } from "react";
import type { PreviewAuthor } from "@/components/preview/platforms";
import { useApi } from "@/lib/api";
import supabase from "@/lib/supabase";

/**
 * The signed-in user as the post preview shows them: the name and role from
 * their Contendo profile, falling back to their sign-in name, and the photo
 * from their sign-in provider. Anything missing shows a placeholder.
 */
export function usePreviewAuthor(): PreviewAuthor {
  const api = useApi();
  const [author, setAuthor] = useState<PreviewAuthor>({ name: "" });

  useEffect(() => {
    let cancelled = false;
    (async () => {
      const { data } = await supabase.auth.getUser();
      const meta = data.user?.user_metadata ?? {};
      let profile: { name?: string; role?: string } = {};
      try {
        const res = await api.getProfile();
        if (res.ok) profile = (await res.json()).profile ?? {};
      } catch {
        // The preview still works with the sign-in details alone.
      }
      if (cancelled) return;
      setAuthor({
        name: profile.name?.trim() || meta.full_name || meta.name || "",
        headline: profile.role?.trim() || undefined,
        avatarUrl: meta.avatar_url ?? null,
      });
    })();
    return () => { cancelled = true; };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  return author;
}
