# Publishing roadmap

## Where we are

Contendo publishes through a third-party provider (Zernio), behind the `PublishingProvider` interface in `backend/publishing/provider.py`. The provider holds each user's platform tokens and uses its own approved apps on each platform.

This is a deliberate dependency, not the end state. It costs a per-account fee, users see the provider's app name on consent screens, and an outage or policy change there is ours too.

## Where we are going

Our own OAuth apps with each platform, wrapped in a `DirectProvider` that implements the same interface. Nothing outside `backend/publishing/` changes: accounts, jobs, the worker, the endpoints and the screens all talk to the interface.

What `DirectProvider` has to add that the provider does for us today:

- Storing platform tokens ourselves, encrypted at rest, with refresh before expiry.
- Each platform's own upload flow for images and video.
- Each platform's own publish call, limits and error codes, mapped to `publishing.types.ErrorCode`.
- A way to move users over: they reconnect each account once through our app.

## Before Zernio is switched on

The adapter (`backend/publishing/zernio.py`) is written from Zernio's OpenAPI spec and tested against recorded shapes. It has not run against a live Zernio account. Do this once, with a test account on each platform:

1. Create a Zernio account, an API key, and a webhook endpoint pointing at `https://<backend>/publishing/webhook` with a secret. Subscribe it to `post.published`, `post.partial`, `post.failed` and `post.cancelled`.
2. Set `PUBLISHING_PROVIDER=zernio`, `ZERNIO_API_KEY` and `ZERNIO_WEBHOOK_SECRET` on a staging backend.
3. As a Pro test user, connect an Instagram account and a Facebook Page. Confirm the connect page opens **without a Zernio login**.
4. Publish now, schedule one, cancel one. Confirm the job statuses change and the webhook arrives.
5. Disconnect an account on the platform side and publish to it. Confirm the job fails with "Reconnect …".

If step 3 asks for a Zernio login, Zernio does not fit and bundle.social is the fallback (see `publishing-provider-evaluation.md`).

## Platform app reviews to start now

Reviews take weeks and run independently of the code, so start them in parallel. The requirements below are each platform's as I know them, not re-read from their developer portals for this document, and platforms change them: confirm each list on the portal when you apply.

Every platform needs these first:

- A public **privacy policy URL** and **terms of service URL**. The site's footer links to `/privacy-policy` and `/terms-of-service`, but neither page exists yet. This blocks every application below.
- A public page that explains what the app does (the landing page serves).
- A demo video per platform: a screen recording of a user connecting their account in Contendo and publishing a post, with the consent screen visible.
- A test login for the reviewer.

### Meta (Instagram and Facebook Pages)

- Create a Meta developer app of type Business, and complete **Business Verification** (legal business documents and a matching domain or phone).
- Request **Advanced Access** through App Review for: `pages_show_list`, `pages_manage_posts`, `pages_read_engagement`, `instagram_basic`, `instagram_content_publish`, and `business_management` if Pages are reached through a Business portfolio.
- Each permission needs its own written use case and screen recording.
- Instagram publishing works only for Business or Creator accounts linked to a Facebook Page.
- Complete the Data Handling questions and set a data deletion callback or instructions URL.

### LinkedIn

- Create an app on the LinkedIn Developer portal, linked to a LinkedIn Company Page you administer, and verify that link.
- Personal posting: the **Share on LinkedIn** product (`w_member_social`) and **Sign In with LinkedIn using OpenID Connect** (`openid`, `profile`). These are self-serve.
- Company Page posting: the **Community Management API** (`w_organization_social`, `r_organization_social`, `rw_organization_admin`). This needs an access request form describing the use case, and LinkedIn reviews it. It is the slow one.

### TikTok

- Register on TikTok for Developers and create an app with **Login Kit** and the **Content Posting API**.
- Scopes: `user.info.basic`, `video.publish` (direct post), `video.upload` (draft to the user's inbox).
- Until the app passes TikTok's audit, every post is forced to private visibility. The audit needs a demo video, the privacy policy and terms URLs, and a UI that follows TikTok's content-sharing guidelines (the user must see and choose the privacy level and interaction settings for each post).
- Domain or URL-prefix verification is required for pulling video from our storage.

### YouTube (Google)

- Create a Google Cloud project, enable the **YouTube Data API v3**, and configure the OAuth consent screen with the production domain verified in Search Console.
- Scope: `https://www.googleapis.com/auth/youtube.upload`. It is a sensitive scope, so the app needs **OAuth verification**: a demo video, the privacy policy, and a written justification.
- Videos uploaded by an unverified API project are locked to private, so also complete the **YouTube API Services compliance audit**.
- The default quota is 10,000 units a day and an upload costs 1,600: about six uploads a day until a quota extension is granted. Request it with the audit.

### Google Business Profile

- Request access to the **Business Profile APIs** through Google's access form. It requires a verified Business Profile that has been active for 60 days or more, and a business website.
- Scope: `https://www.googleapis.com/auth/business.manage`, which also needs OAuth verification.

### X

- Not through review: X's API is paid. Posting needs at least the Basic tier, billed monthly, with per-app posting caps. Decide whether X is worth offering before building it.

## Order of work

1. Publish the privacy policy and terms pages.
2. Start Meta Business Verification and the LinkedIn Community Management request (the two longest waits).
3. Build `DirectProvider` one platform at a time, behind a per-platform switch, starting with whichever review lands first.
4. Move users platform by platform, and drop the third-party provider when the last platform is moved.
