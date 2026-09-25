---
paths:
  - "frontend/**"
---

# Frontend rules

- Read DESIGN.md before any UI change. Editorial Atelier system: Noto Serif headlines, Inter body, the No-Line Rule, surface hierarchy. Never deviate without explicit instruction.
- All API calls go through `useApi()` in `frontend/lib/api.ts`. Never raw `fetch()`. (`app/settings/page.tsx` and the admin pages still use raw fetch; migrate them when you touch them.)
- Auth comes from the Supabase client (`@supabase/ssr`). Public routes are listed in `frontend/middleware.ts`.
- New users are routed to `/first-post` by `useProfileCheck` in AppShell. `/onboarding` is a legacy redirect.
- Prefer a new component or hook over growing an already-long file. When touching `CreatePost.tsx`, `first-post/page.tsx`, or `FeedMemory.tsx`, put new logic in a separate file and import it.
- After changes, run `npx tsc --noEmit` from `frontend/`.
