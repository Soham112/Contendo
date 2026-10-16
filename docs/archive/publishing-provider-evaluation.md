# Publishing provider evaluation

Researched 2026-10-13 from each provider's public docs and pricing pages. Decision pending.

## What we need

Each Contendo user connects their own social accounts through a link we open from our app, without creating an account with the provider. We publish on their behalf from our backend, isolated per user.

## Recommendation

**Zernio**, with bundle.social as the fallback if Zernio fails a sandbox test.

Zernio is the only candidate whose docs confirm all three things we need: a tenant per customer, a connect link we generate per tenant, and every platform on our list including Google Business Profile. Its webhooks are signed and it documents idempotency keys for retries. At $39 a month per Pro user, its cost is roughly $1 to $4 per user.

bundle.social is far cheaper at scale (a flat plan rather than a per-account charge), and its hosted connect portal is the most polished. I could not confirm Google Business Profile support from its docs, which matters for local businesses. If that checks out, it is the better choice above a few hundred users.

Post Bridge and Postiz do not fit: both are built around one owner's accounts.

Before committing, run one sandbox test on the chosen provider: create a tenant, open the connect link in a browser with no provider login, connect an Instagram and a Facebook Page, publish, and receive the webhook. Several answers below are marked "not stated", and that test settles them.

## Comparison

| | Zernio | bundle.social | Upload-Post | Ayrshare | Post Bridge | Postiz (hosted) |
|---|---|---|---|---|---|---|
| End users connect without a provider account | Connect URL per profile; headless mode for our own UI. Docs don't say a login is needed | Hosted portal link per team. Docs don't say a login is needed | Yes, stated: the browser "needs no session with Upload-Post" | Linking URL per profile. Not stated | No such flow | No. OAuth is for existing Postiz users |
| Tenant isolation | One profile per customer, with our ID as `externalId`; keys can be scoped to a profile | One team per customer inside our organization | One profile per customer, with a profile-scoped JWT | One user profile and Profile-Key per customer | None ("no per-client separation") | One organization per key |
| Instagram, Facebook Pages | Yes | Yes | Yes | Yes | Yes | Yes |
| LinkedIn personal and pages | Both | LinkedIn listed; personal vs page not stated | LinkedIn listed; not broken down | Yes | Yes | Both |
| Google Business Profile | Yes | Not confirmed | Yes | Yes | Not checked | Yes |
| TikTok, YouTube, X | Yes | Yes | Yes | Yes | Yes | Yes |
| Publish status | Signed webhooks (`post.published`, `post.partial`, `post.failed`), 7 attempts | Webhooks, organization-level; failure is a status on `post.published` | Webhooks mentioned, not read | Webhooks, not read | Not found | Not mentioned |
| Rate limits | Shared across all customers, grows with connected accounts; no figures published | Daily caps per connected account (Pro: X 15, Facebook 50); monthly post cap per plan | Facebook 25 posts per Page per day; others not read | Not read | "100 posts/hour" per a competitor's page | 90 to 100 post-creation requests per hour |
| Identical content to many accounts | Not stated | Not stated | Not stated | Not read | A competitor claims it is restricted; unverified | Not stated |

"Not stated" means the page I read did not say. "Not read" means I did not reach that page.

## Pricing

Assumes three connected accounts per user. Figures are monthly and are my arithmetic from the published rates unless noted.

| Users | Zernio | bundle.social | Upload-Post | Ayrshare |
|---|---|---|---|---|
| 10 | $108 | $100 (Pro) | $39 to $50 | $299 (Launch) |
| 100 | $518 | $100 (Pro, 10,000 posts) | $212 | $1,228 (Business, from their calculator) |
| 1,000 | $3,218 | $400 (Business, 100,000 posts) | Not published | Custom |

- **Zernio:** per connected account, graduated: first 2 free, $6 each to 10, $3 each to 100, $1 each after. Profiles are free. X posts are passed through at X's rates ($0.015 a post, $0.20 with a link), so X needs its own decision.
- **bundle.social:** flat per organization with unlimited teams and accounts on paid plans. The monthly post cap is the real limit.
- **Upload-Post:** per profile tier. White-label starts at Professional ($50).
- **Ayrshare:** multi-user starts at Launch ($299, 10 profiles); Business is $599 for 30 plus $8.99 per extra profile.
- **Post Bridge:** $39 for 15 accounts, $99 for 99 accounts, API as a $5 add-on. Not applicable to our model.

## Licence and terms

- **Postiz** source is AGPL-3.0. None of its code is in Contendo and we are not self-hosting it. Self-hosting it as part of our product would bring the AGPL network-use clause into play and needs a decision first.
- The other candidates are hosted services under their own terms. I have not read any provider's terms of service for resale or white-label clauses; read the chosen one's before going live.
- Every provider publishes through its own approved app on each platform, so users see the provider's app name on the consent screen unless the provider supports our own app credentials. That goes away with the direct integrations in `publishing-roadmap.md`.

## Open items

- Whether Zernio and bundle.social connect links work with no provider login (sandbox test).
- bundle.social Google Business Profile support.
- Each provider's rule on identical content across accounts. Low risk for us, since every post is written per user.
- Zernio reliability: reviews are mixed, including one calling it error-prone.

## Sources

- Zernio: docs.zernio.com/guides/multi-tenant, /multi-tenant, /webhooks, /platforms; zernio.com/pricing
- bundle.social: info.bundle.social/api-reference (introduction, connect-social-accounts/hosted-flow, rate-limits, webhooks); bundle.social/pricing
- Upload-Post: docs.upload-post.com (Connect API); upload-post.com/llms-full.txt
- Ayrshare: ayrshare.com/pricing; ayrshare.com/docs/apis/profiles/generate-jwt
- Post Bridge: post-bridge.com/manage-multiple-social-media-accounts (the API reference at api.post-bridge.com/reference did not render for me)
- Postiz: docs.postiz.com/public-api and /public-api/oauth
