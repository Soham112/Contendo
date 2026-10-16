# Publish-paywall launch changes

## What changed

- Every generation variant now reviews every final sentence against sources after all writing/compression steps. Unsupported details trigger up to two source-only repairs, each followed by a full review. Exhausted repairs, incomplete reviews and expected provider failures return the draft as `needs_review` with visible flags. A previous B review cannot label that response clean. A’s obsolete background-only fact check is no longer scheduled; the historical wire snapshot exercises that retired helper explicitly without changing any frozen request data.
- Generation and onboarding display the flagged text. Flags and source trace ids survive editor handoff and reload. The returned draft still uses a generation quota slot.
- Publishing requires a server-stored review, explicit resolution of every flag and approval of the exact content/media. Both job creation and worker dispatch enforce the approved snapshot. Legacy jobs without approval fail before contacting the provider. A free user opening final review is sent through the existing Pro upgrade flow. Auto-publish without review is not an accepted request option.
- Pro remains 300 posts/month and allows one account per platform. The API, plan screens and account gate agree; provider synchronization and a database unique index prevent duplicate platform connections. Sync releases stale account references before inserting replacements, so valid reconnects also work with the index.
- The business-profile prompt now says: “Never add a listing, sale, price, client, review, award or result that it does not state.” `PROMPTS.md` matches.
- Public platform names come only from `frontend/content/verified-platforms.ts`. It starts empty; neither the visible FAQ nor FAQ structured data advertises an unverified platform.
- `docs/` is tracked, including the architecture inventory and publishing roadmap. Local secrets, environment files, keys, scratch directories and OS metadata remain ignored. Existing local plans and provider-evaluation research were not included in these commits.
- `/privacy-policy` and `/terms-of-service` are public, accessible without an auth-service round trip and linked from the footers and sitemap. Both pages carry `Draft: needs legal review` in code only. They cover actual account/memory handling, Anthropic, Zernio, Stripe, deletion and contact, without claiming self-service account deletion exists.
- The eval environment guard now explicitly disables publishing and clears inherited billing credentials. Returned flagged drafts stay in completed-run metrics with their distinct generation status and grounding flags, instead of being excluded or called clean. No live integration is enabled by the unit suites.

## Required deployment settings and migrations

Apply migrations `010_one_account_per_platform.sql` and `011_publish_approvals.sql` after the existing migrations, before deploying the new backend. They were written and tested through application fakes, not executed against a database in this task. Migration 010 intentionally fails if legacy duplicate platform connections exist: disconnect extras explicitly rather than silently removing an account. Migration 011 adds immutable approvals and database validation for new publishing snapshots. Old unapproved jobs cannot be dispatched by the new worker.

Set these non-secret server build settings in the frontend deployment:

- `CONTENDO_LEGAL_OPERATOR`: the real person or legal entity operating Contendo.
- `CONTENDO_LEGAL_CONTACT_EMAIL`: a monitored public contact address for support, privacy and deletion requests.

The legal-page build refuses missing or invalid contact details instead of publishing an invented identity. Real values were requested but not supplied during this task. Validation uses a clearly fictional CI operator and `legal@example.test`; these are not defaults in application code. Rebuild the deployed frontend with real values. The legal text still needs the requested legal review, including retention practices and launch jurisdictions.

No production publishing platform was tested or added to the verified list. Follow `docs/publishing-roadmap.md` to test live connections, publish, schedule, cancel and disconnect, then add only the verified platform to the single config. No migrations, Stripe changes, publishing actions, deployments, pushes, merges or PRs were performed.

## Cost

See [llm-costs.md](llm-costs.md) for actual token-log aggregates and the modeled grounding overhead. The clean-path estimate is $0.079698/post, or $23.91 for 300 posts; $15.09 remains from $39 before other expenses. At 10% of posts requiring both repairs, the estimate is $28.44/month. A workload where all posts need both repairs is approximately $69.22/month at historical call sizes, not a maximum bill. Fresh production usage is needed to measure the new repair distribution. No unit-test fake usage was treated as real usage.

## Validation

Final results: **1,525 backend tests passed**, including both frozen A snapshot suites; **128 eval tests passed**; **90 frontend tests passed**; TypeScript checking and `next build` passed. The build includes static `/privacy-policy` and `/terms-of-service` pages. `git diff --check` passed. The new migrations were not applied to a database, and live model repair quality, Stripe behavior, provider billing and production social connections remain unverified.

All Python tests run with plugin autoload disabled and dotenv disabled. The unrelated pytest-rerunfailures plugin otherwise binds a local socket prohibited by the sandbox. Backend tests replace Supabase, Claude and embeddings with fakes and block outbound network; eval tests stay offline. Frontend tests use Vitest.

```sh
cd backend
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 venv/bin/python -B -m pytest -p no:cacheprovider
cd ../evals
PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 PYTHON_DOTENV_DISABLED=1 PYTHONDONTWRITEBYTECODE=1 DEEPEVAL_DISABLE_DOTENV=1 DEEPEVAL_TELEMETRY_OPT_OUT=YES ../backend/venv/bin/python -B -m pytest -p no:cacheprovider
cd ../frontend
npm test
npx tsc --noEmit
npm run build
```

Builds require the two legal settings above plus the existing frontend deployment settings. CI validation used dummy Supabase credentials and an unreachable local backend URL, with telemetry disabled. Font downloads used public Google Fonts; no live customer, billing or publishing API was called.

## Files created

| File | Reason |
|---|---|
| `backend/agents/grounding_agent.py` | Semantic final-text review and source-only repair calls. |
| `backend/pipeline/grounding.py` | Bounded repair orchestration and explicit verification failures. |
| `backend/tests/test_grounding.py` | Young-couple/price regressions and all-variant gate integration. |
| `frontend/components/GroundingNotice.tsx` | Visible unresolved claim flags on generated drafts. |
| `backend/memory/approval_store.py` | User-scoped persistent final-text approvals. |
| `backend/publishing/approval.py` | Source review, individual flag resolution and exact-snapshot matching. |
| `backend/migrations/010_one_account_per_platform.sql` | Enforce the per-platform connection invariant under concurrency. |
| `backend/migrations/011_publish_approvals.sql` | Store immutable approvals and enforce them for publishing snapshots. |
| `backend/tests/test_publishing_account_limits.py` | Provider sync cannot bypass account entitlements. |
| `backend/tests/test_publish_approval.py` | API and worker approval bypass regressions. |
| `frontend/components/publishing/ApprovalReview.tsx` | Show the final text and collect explicit approvals. |
| `frontend/components/publishing/ApprovalReview.test.tsx` | Exercise the actual flag and approval controls. |
| `frontend/content/verified-platforms.ts` | Single production-verified public platform config. |
| `frontend/lib/verified-platforms.test.ts` | Empty and limited platform-claim cases. |
| `frontend/components/marketing/LegalDocument.tsx` | Shared Editorial Atelier legal-page presentation. |
| `frontend/app/privacy-policy/page.tsx` | Public privacy policy at the footer URL. |
| `frontend/app/terms-of-service/page.tsx` | Public terms at the footer URL. |
| `frontend/lib/legal.ts` | Public legal routes and required operator/contact configuration. |
| `frontend/lib/legal.test.tsx` | Legal content and fail-closed contact configuration tests. |
| `frontend/lib/legal-routing.test.ts` | Anonymous access without an authentication dependency. |
| `docs/launch/llm-costs.md` | Reproducible cost evidence and projection. |
| `docs/launch/publish-paywall.md` | Implementation, validation and remaining launch configuration. |
| `docs/architecture/as-is.md` | Existing architecture inventory, newly tracked as requested. |
| `docs/publishing-roadmap.md` | Existing publishing roadmap, newly tracked as requested. |

Stopgaps introduced: none. Semantic checks remain probabilistic; failures and uncertainty are explicit and require user review rather than an implicit clean result.
