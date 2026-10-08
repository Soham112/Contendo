---
paths:
  - "frontend/**"
---

# Frontend rules

- Follow "Engineering standard: no cheap fixes" in CLAUDE.md before proposing any fix.
- Follow "Files and code organisation" in CLAUDE.md before creating a file or helper.
- Read DESIGN.md before any UI change. Editorial Atelier system: Noto Serif headlines, Inter body, the No-Line Rule, surface hierarchy. Never deviate without explicit instruction.
- All API calls go through `useApi()` in `frontend/lib/api.ts`. Never raw `fetch()`. (`app/settings/page.tsx` still uses raw fetch; migrate it when you touch it.)
- Auth comes from the Supabase client (`@supabase/ssr`). Public routes are listed in `frontend/middleware.ts`. Any redirect target read from the URL goes through `safeRedirectPath()` in `frontend/lib/safe-redirect.ts`.
- Model-generated SVG is untrusted: render it with `components/DiagramView.tsx`, never `dangerouslySetInnerHTML`.
- New users are routed to `/first-post` by `useProfileCheck` in AppShell. `/onboarding` is a legacy redirect.
- Prefer a new component or hook over growing an already-long file. When touching `CreatePost.tsx`, `first-post/page.tsx`, or `FeedMemory.tsx`, put new logic in a separate file and import it.
- After changes, run `npx tsc --noEmit` and `npm test` from `frontend/`.
