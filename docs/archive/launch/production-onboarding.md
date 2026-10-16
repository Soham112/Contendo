# Production recovery and short onboarding — 2026-10-14

## Diagnosis

Railway log `/Users/sohampatil/Downloads/logs.1791943713986.log` shows:
- GET `/account` → 500: PostgREST PGRST205, `public.accounts` absent from schema cache (log line 83).
- GET `/billing/entitlements` → 500: PGRST205, `public.subscriptions` absent (line 149).
- The new account, niche and billing routes are running; this rules out an old backend or fatal Stripe import error as the cause of those requests.
- CORS preflights in the supplied log succeeded. Current public health returns 200/ok; a read-only OPTIONS check for `https://www.contendoai.com` succeeds and echoes that origin. The public frontend previously inspected points to the correct Railway backend.
- Generation uses the same missing subscriptions/quota dependency, but this log excerpt does not include the failing generation request itself.
- The frontend swallowed account lookup errors and guessed the Individual path. That behavior is removed.
- The Connected accounts screenshot shows the provider-unavailable message; it does not establish which publishing setting is missing. Production configuration must be checked in Railway.

No production credentials were read. Production database migrations, exact deployment commit and private service configuration remain unverified. No production settings, schema or deployments were modified.

## Changes

Startup validates required configuration before importing clients and probes required schema columns without returning any customer rows. Missing schema/config blocks startup with clear logs. Database errors get logged and converted to actionable 503 responses within CORS. Account/onboarding checks fail explicitly with Retry; Scheduled never presents a failed load as an empty successful list. Generation errors preserve the brief and give an actionable message.

Business signup: segment → niche → one profile screen → first draft (four screens).
Individual signup: segment → topic, format, story and optional takes together → first draft (three screens).
No role, resume or five-question voice gate precedes the post or workspace. Those are optional in Settings and after the draft. The third saved post offers an optional voice prompt with persisted dismissal. Stored answers survive all merges.

Onboarding step events are persisted server-side with started/completed/skipped/error outcomes, without logging profile/story text in event metadata. Model-generated takes receive the current UTC date and treat all supplied text as data. Existing ideation paths also receive the current date.

Docker verification exposed baseline hierarchy drift: the old `topic_nodes` lacks `created_at` and other fields the existing store requires. Migration 012 preserves legacy values, adds current fields and user-scoped identity indexes. Hierarchy upserts use composite user/identity conflict targets.

## Deployment order

See README.md, “Production recovery and short onboarding”, for the exact read-only SQL checks and environment variables.

1. In the Supabase project identified by Railway `SUPABASE_URL`, inspect actual schema objects. Apply outstanding migrations 007–012 in order; also 006 if `usage_events.model` is missing. Do not run the baseline dump on production or rerun non-idempotent 011 blindly. Resolve duplicate live platform accounts before 010; no automatic deletion is performed. Reload the PostgREST schema cache.
2. Set required Railway configuration: ENVIRONMENT=production, Supabase URL/service-role key, Anthropic key, FRONTEND_ORIGIN=https://www.contendoai.com, the three Stripe settings, PUBLISHING_PROVIDER=zernio and both Zernio secrets. STRIPE_TRIAL_DAYS, when set, must be an integer.
3. Deploy the intended backend commit; confirm completed startup and /health.
4. Confirm Vercel production API URL is https://contendo-production.up.railway.app, public site URL is https://www.contendoai.com, and public Supabase settings identify the same project. Rebuild frontend; keep domain/auth callback configuration consistent.
5. Test two fresh production accounts, then live Stripe checkout/webhooks and a real approved Zernio publish. These were not exercised against production.

## Verification

Two fresh local Supabase Auth accounts completed headless Chrome Business and Individual paths, first draft, workspace handoff, Scheduled and Plan/billing. Optional suggested takes, third-post voice prompt/dismissal and optional work-role save also passed. The final walkthroughs produced no browser errors. Real Postgres/PostgREST stored the first-post notes, hierarchy rows, quotas, saved drafts and onboarding events. Model calls and embeddings were explicit local test doubles; no paid/provider API calls were made. Live model quality, Stripe checkout, Zernio delivery and production schema remain unverified.

Migration 012 was executed on local PostgreSQL; legacy summary/tag/source relationships were preserved and repeat application passed. The full backend suite includes both frozen A snapshot suites. Final validation: 1,560 backend tests (including both frozen A snapshot suites), 128 eval tests, 101 frontend tests, TypeScript and next build passed.

Screenshots: `/private/tmp/contendo-browser/business-first-post.png`, `individual-first-post.png`, `business-scheduled.png`, `individual-scheduled.png`, `business-billing.png`, `individual-billing.png`.

## Files created

| File | Responsibility |
|---|---|
| backend/config/startup.py | Deployment environment validation before client imports. |
| backend/memory/schema_check.py | Read-only startup schema contract probes. |
| backend/tests/test_startup.py | Missing configuration/schema, safe error response and startup regressions. |
| frontend/components/RetryNotice.tsx | Shared accessible error and Retry control. |
| frontend/lib/request-errors.ts | Plain actionable messages for network/status failures. |
| backend/agents/onboarding_agent.py | Dated structured take generation. |
| backend/memory/onboarding_store.py | User-scoped onboarding events and personalization status. |
| backend/routers/onboarding.py | Protected onboarding and optional personalization endpoints. |
| backend/tests/test_onboarding_short.py | Auth, isolation, evidence, date and profile-preservation regressions. |
| frontend/lib/onboarding-api.ts | Typed onboarding methods on the shared authenticated transport. |
| frontend/components/onboarding/FirstPostFlow.tsx | Shared short signup controller and explicit retry states. |
| frontend/components/onboarding/IndividualBrief.tsx | One-screen Individual inputs and optional takes. |
| frontend/components/onboarding/FirstDraft.tsx | First-draft display and provenance-preserving workspace handoff. |
| frontend/components/onboarding/Personalization.tsx | Optional work, resume and voice setup. |
| frontend/components/onboarding/PersonalizationPrompt.tsx | Optional third-post invitation and persisted dismissal. |
| frontend/app/settings/personalization/page.tsx | Settings route for optional personalization. |
| backend/migrations/012_align_memory_hierarchy.sql | Preserve legacy hierarchy data and align its schema contract. |
| backend/tests/test_hierarchy_identity.py | User-scoped hierarchy upsert regression. |
| frontend/components/onboarding/optional-and-scheduled.test.tsx | Optional prompt and Scheduled failure/retry regressions. |
| docs/launch/production-onboarding.md | Local-only diagnosis, deployment and verification report; ignored by Git. |

Stopgaps introduced: none. Test doubles are confined to verification and are not a production fallback.
