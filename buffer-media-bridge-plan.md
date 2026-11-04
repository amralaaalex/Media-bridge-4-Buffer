# Media bridge for Buffer — project plan

Working name only. The terms say a submission must not be named or presented so that it looks like an official Buffer product. Pick a neutral product name before submitting (see section 2, Naming) and describe it as "built on the Buffer API".

Last updated: 2026-11-04 (contest rules verified against the official page and the terms at https://buffer.com/api/commit/terms)
Owner: Amr
Purpose of this file: a single source of truth so any session (human or Claude) can pick up the project without re-reading the chat history. Update the task statuses and the "Decisions log" as work progresses.

---

## 1. Objective

Build a small, working service for the **Buffer Commit** build contest that lets a Buffer user attach images to posts **without hosting them anywhere themselves**, and that keeps those files alive for exactly as long as the post needs them.

Two goals behind it:
1. Win or place in Buffer Commit (visibility with Buffer's CEO, Staff PM and Staff Engineer, who judge every entry).
2. Serve as a portfolio piece toward a data engineering or agentic AI engineering role at Buffer.

Guiding principle agreed with Amr: **keep it simple**. One core feature done well, add-ons only if time allows.

## 2. Contest rules (verified against https://buffer.com/api/commit on 2026-11-04)

**Dates**
- Build window: Oct 28 – Nov 13, 2026. Submit by **Nov 13, 11:59 PM PT**.
- Judging begins Nov 16. Winners announced **Dec 7** (project gallery opens the same day).
- Registration stays open until submissions close, but you must **register with your Buffer account** before submitting: https://buffer.com/api/commit/register

**Eligibility (every build must)**
- Work end to end, connect through **Buffer OAuth** (App Client, not a personal API key), and make real API calls.
- Be **publicly available** at submission and stay up through judging (at least until Dec 7).
- Existing projects are allowed, but only work done inside the build window is judged and it must be clearly identified. This project is new, so everything counts.
- Entrants must be 18+. Egypt is not on the excluded list (excluded: Quebec, Cuba, Iran, North Korea, Syria, Sudan, Belarus, Myanmar, China, Crimea, Russia, Donetsk/Luhansk, and other comprehensively US-sanctioned regions).
- Solo or team of any size. One person can be on only one team.

**What to submit** (form: https://buffer.com/api/commit/submit; all items except #6 are required for eligibility)
1. **Demo video, two minutes or less**, showing the project working end to end against the live Buffer API. Slides are not a substitute.
2. **Public link** to the hosted app.
3. **Written summary, about 300 words**, covering: the problem it solves, the intended audience, the Buffer API surface it uses, and planned next steps.
4. **Full legal name, email, and social handles** for credit. The email must match the one used at registration (which must be the verified Buffer account email).
5. **The app's Buffer API app client ID**, so Buffer can verify it is built on the API.
6. *(Optional)* **Build-in-public trail**: up to five links to public social posts about participating, made between Oct 15 and Nov 13. Each post must disclose it is connected with promoting the contest. Required only for the Build-in-Public Award.

**Judging window:** approximately Nov 16–20. The project must stay live through judging (keeping it up to Dec 7 is the safe choice).

**Judging (from the terms)**
- Judges: Joel Gascoigne (CEO), Amanda Marochko (Staff PM), Joe Birch (Staff Engineer).
- Each judge scores 1–5 on three equally weighted criteria: **real usefulness** (solves a problem a realistic user would actually have, explicitly *not* a demonstration of technical skill), **technical execution and craft** (how well it is built on the Buffer API), **creativity and originality**.
- Final score = average of the three judges' totals. **Minimum 9/15** to be eligible to win; up to 16 winners.
- Tie-break: higher usefulness score wins.
- The build-in-public trail does not affect the score.
- Buffer may test the app with its own test accounts, so OAuth must work for any Buffer account, not only Amr's.

**Prizes**
- Commit Award: up to 16 winners split $25,600 (10% of Buffer's August 2026 net profit), $1,600+ each, plus a gallery spotlight, a mention in the wrap-up blog post, a ~90-minute group session with Joel, and one year of Buffer Essentials (or current paid plan covered).
- Build-in-Public Award: up to 3 winners who shared their build most openly, picked by Buffer's content team (swag kit on top of a winning share).
- Delight Award: up to 3 winners with the most distinctive user experience, picked by Buffer's design team (swag kit). Implication: a little UI polish is worth a few hours.
- Everyone who submits an eligible project gets a Buffer Commit cap.

**Project requirements (terms, section 3)**
- Publicly available at submission and through judging; connectable to a Buffer account; authenticates via Buffer OAuth; makes at least one successful API call.
- Must comply with Buffer's API terms and rate limits, and with the terms of any third-party platform it connects to.
- No malicious code. **Must not collect, store, or use any person's data beyond what the project needs, or without consent.** For this project that means: a short privacy note on the upload page, store only the image + minimal metadata, delete files on the lifecycle schedule, and offer a "delete now" button.

**Naming**
- Entrants may say "built on the Buffer API", but the product must not look like an official Buffer product or endorsed by Buffer. Avoid "Buffer" as the first word of the product name. Buffer can request a rename.

**Ownership and IP**
- You keep full ownership. Buffer gets a non-exclusive, perpetual, royalty-free license to display and promote the submission (gallery, blog, marketing). Fine for a portfolio project.
- You warrant it is your original work (AI-assisted code is fine if you have the right to submit it), contains no confidential information, and that you have your employer's permission to enter and receive a prize.
- No confidentiality: Buffer may already be building, or later build, something similar.

**Prize logistics (if it wins)**
- Cash is paid in USD via Bill.com; non-US winners complete a W-8BEN. Taxes are the winner's responsibility. Winners must respond within 10 days of the announcement (notification around Dec 4–7).
- Swag ships only to eligible regions; Egypt is eligible.

**Support**
- Office hours every Tuesday and Thursday.
- Discord (contest): https://discord.com/invite/kqZ7HNZu2u (channel: buffer-commit-support). Docs-site Discord: https://discord.gg/9skbzTz6vQ
- Builder handbook (technical FAQ; read on 2026-11-04, and the key points are in section 6a): https://buffer.notion.site/Buffer-Commit-Developer-Handbook-3d7a7f5a00fd80918466e36eb2cba9f8
- Terms and conditions: https://buffer.com/api/commit/terms

**Case studies Buffer highlighted as inspiration** (useful for the write-up's tone): PostIQ, Hiding Elephant, WriteStack, Pokémon Cards App — all at https://buffer.com/resources/case-studies/

## 3. What problem it solves (from Buffer's public API roadmap)

Roadmap: https://developers.buffer.com/roadmap.html (checked 2026-11-02: "Planned" and "In Progress" are both empty, so Buffer has not scheduled any of these).

| Roadmap request | Votes | How this project answers it |
|---|---|---|
| Image assets for API — any image must already be hosted online | 24 | Upload the file to us; we host it and create the post |
| Copy media to Buffer storage after post creation — deleting source files early breaks scheduled posts | 18 | We keep the file until the post is actually sent, then delete it |
| Claude Code skill for common Buffer actions | 20 | Optional add-on: an "upload and post" skill / MCP tool |

Not addressed (and should not be promised): video in `createIdea` is rejected by Buffer's public API itself; external hosting cannot fix that.

## 4. Scope

### Core (must ship)
1. Buffer OAuth login (App Client).
2. Image upload (web page + JSON API).
3. Store file in object storage, return a public URL.
4. Create a Buffer post (draft or scheduled) with that image URL via the GraphQL API.
5. Track file ↔ post in a database.
6. Background cleanup job: poll post status; delete the file only after the post is sent. Also delete if the post is deleted or a max-hold TTL passes.
7. Minimal status page: list of files, their linked post, and lifecycle state.

### Add-ons (in priority order, only if core is done)
1. Image prep per network: resize/compress to each platform's limits before upload.
2. Claude Code skill or MCP tool exposing one "upload and post" action.
3. AI alt text (Arabic/English) — first verify Buffer's API accepts alt text on assets.
4. Stats page: files held, files purged, bytes saved, average hold time (data-engineering touch).
5. Scoped tokens for agents (the earlier "Leash" idea) — only if everything else is done.

### Explicitly out of scope
- Post metrics/analytics (metrics require a personal API key; App Clients cannot read them).
- Video for Ideas (blocked on Buffer's side).
- Multi-tenant billing, teams, anything enterprise.

## 5. Architecture

```
Browser / agent
      |
      v
FastAPI app  ── OAuth ──> Buffer GraphQL API (createPost, posts status)
   |   |
   |   +──> Postgres (users, oauth tokens, media_files)
   |
   +──> Object storage (Cloudflare R2) ── public URL ──> Buffer fetches image

Scheduled cleanup job (every ~10 min, but only spends API calls on files that are due):
  candidates = media_files in state HELD where due_at <= now (or due_at is null and last_checked_at is old)
  group by user; per user, ONE request with up to 30 aliased post(id) lookups
  for each result:
    status sent              -> delete object, state = PURGED
    post deleted (NOT_FOUND) -> delete object, state = PURGED
    status error             -> keep (user may fix and reschedule in Buffer); re-check later
    draft / needs_approval   -> keep; re-check daily
    scheduled / sending      -> keep; re-check soon
  any HELD file past ttl_expires_at -> delete object, state = EXPIRED (no API call needed)
```

**Wake-up scheduling (protects both Buffer quota and Neon compute hours):** no fixed polling interval.
- After each pass, compute the next wake time from the DB: `min(due_at of HELD files, next re-check time for scheduled/error/draft files, next ttl_expires_at)`.
- Schedule a single APScheduler `date` job for that time.
- Creating or deleting a file reschedules the job if the new time is earlier.
- With nothing due, the DB isn't touched, so Neon can scale to zero.
- Also make sure idle pooled connections don't keep the compute awake (short `pool_recycle`, or NullPool). Verify the free plan's monthly compute hours and suspend behaviour in the Neon console before deploying.

Budget: about 250 calls a day are shared by every user and by token refreshes. Do the arithmetic before demo day. For example, 50 due files is 2 calls per pass. Never poll files whose `due_at` is still in the future.

### Stack decisions
- **API**: Python 3.12, FastAPI, httpx for Buffer calls.
- **DB**: Postgres (Neon or Supabase free tier). SQLAlchemy or raw SQL; keep it light.
- **Storage**: Cloudflare R2 (S3-compatible, no egress fees). Public bucket with unguessable object keys (e.g. `uuid4.ext`). Do **not** use expiring signed URLs: a scheduled post may be published weeks later.
- **Jobs**: APScheduler inside the app or a separate worker process. Avoid Celery/Redis unless needed.
- **Hosting**: Fly.io or Render (must stay up through judging).
- **Secrets**: encrypt Buffer refresh tokens at rest (Fernet / libsodium); never log tokens.

### Data model (initial)
```
users          id, buffer_account_id, buffer_org_id, created_at, disconnected_at
oauth_tokens   user_id, access_token_enc, refresh_token_enc, expires_at   (refresh under a row lock)
media_files    id, user_id, object_key, public_url, content_type, size_bytes,
               buffer_post_id (nullable), channel_id, due_at (nullable),
               last_post_status, state (UPLOADED|HELD|PURGED|EXPIRED), next_check_at,
               ttl_expires_at, created_at, purged_at, last_checked_at
cleanup_events id, media_file_id, decision, reason, checked_at   (audit trail, feeds stats page)
```

## 6. Things to verify before building (unknowns)

Resolved on 2026-11-04 from the developer handbook and docs. Details are in section 6a.
- [x] `createPost` shape for an image post. See 6a.
- [x] Post status values. `sent` = published, `error` = failed. See 6a.
- [x] Fetch timing. **Buffer validates the URL at create time and fetches the media again at publish time.** Hosting media guide: "The URL must stay reachable until the post publishes, not just when you create it." This confirms the hold-until-sent design.
- [x] OAuth scopes and registration flow. See 6a.
- [x] Rate limits. See 6a. Budget for the conservative handbook numbers.
- [x] Alt text. Supported via `image.metadata.altText`, so add-on 3 is unblocked.

Still open (test empirically):
- [ ] Image format and size limits. The docs list none, and Buffer resolves dimensions itself. Try a large PNG, a large JPEG and a WebP against each target network.
- [x] `needsApproval` is not required: createPost succeeded without it (2026-11-04).
- [x] Drafts do fetch the URL at create time: Buffer resolved 1200x627 for a `saveToDraft` post.
- [x] (2026-11-04, live) What `post(input:{id})` returns after a post is deleted in Buffer: an `errors[]` entry with `extensions.code = NOT_FOUND` and `path = [alias]`, and **`data: null` for the whole response**. `get_posts` handles this.
- [-] Original note: what `post(input:{id})` returns after a post is deleted in Buffer. Probably a top-level `errors[]` entry with `NOT_FOUND` and null `data`. Test it, because one failing alias may null the whole aliased response.

## 6a. Buffer API facts (from handbook + docs, 2026-11-04)

**App client registration:** https://publish.buffer.com/settings/api → App Clients → New Client.
- Choose **Private (confidential)** to get a client secret.
- Fields: name, logo, privacy-policy link and permissions. Link the privacy note here as well.
- Redirect URIs are matched character for character. Several are allowed: register both localhost and production.
- **HTTPS is required, even on localhost**, so local dev needs a self-signed or mkcert certificate.
- The Free plan allows 1 app client.
- Sample app: https://github.com/bufferapp/buffer-sample-apps (`samples/app-client-starter-app`).

**OAuth:** Authorization Code with **PKCE (S256), required even with a client secret**.
- Authorize: `GET https://auth.buffer.com/auth` with `client_id, redirect_uri, response_type=code, scope, state, code_challenge, code_challenge_method=S256`.
- Token: `POST https://auth.buffer.com/token`, form-encoded, with `grant_type=authorization_code` (or `refresh_token`), `client_id`, `client_secret`, `code`, `redirect_uri`, `code_verifier`.
- Scopes needed: `posts:read posts:write account:read offline_access`. **Without `offline_access` there is no refresh token.**
- Access tokens last 1 hour.
- **Refresh tokens are single-use and rotating.** Reusing a spent one revokes the whole grant. Persist the new refresh token in the same transaction as the refresh, let exactly one code path or lock own refreshing, and never retry a failed refresh with the same token.
- If `state` is lost between `/login` and `/callback` you get "Invalid state parameter". Keep `state` and `code_verifier` in a shared store or an encrypted cookie, not in-process memory.
- A `401` means the user revoked access. Mark the user as disconnected and ask them to re-authorize.

**GraphQL:**
- One endpoint: `POST https://api.buffer.com` with `Authorization: Bearer <token>`.
- It always returns HTTP 200 except for 429. System errors appear in `errors[].extensions.code`.
- There are no webhooks, so polling is the only way to learn a post's status.
- Get the org and channels in one request: `account { organizations { id name } }` and `channels(input:{organizationId}) { id name service isDisconnected }`. Cache them.

**createPost:**
```graphql
createPost(input: {
  channelId: "...", text: "...", schedulingType: automatic,
  mode: customScheduled, dueAt: "2026-11-10T15:00:00.000Z",   # or mode: addToQueue / shareNow
  saveToDraft: false,
  assets: [{ image: { url: "https://...", metadata: { altText: "..." } } }]
}) {
  ... on PostActionSuccess { post { id status dueAt } }
  ... on MutationError { message }
}
```
- There is no `organizationId` in the input; the channel implies it.
- `needsApproval` is marked non-null in the schema but none of the examples send it. Test whether it's required.
- `ShareMode` values: `addToQueue | customScheduled | shareNext | shareNow`.
- A URL Buffer can't fetch fails at create time with "Failed to fetch image dimensions".
- **No idempotency key:** after a timeout, check `posts` (by channel and a narrow `createdAt` window) before retrying.
- `saveToDraft: true` creates a draft that never publishes. Use it for testing.

**Post status:**
- `PostStatus` values: `draft | needs_approval | scheduled | sending | sent | error`.
- Useful fields: `status`, `dueAt`, `sentAt`, `externalLink`, `error { message }`.

**Bulk status checks:**
- `posts(first:100, input:{organizationId, filter:{status:[...], channelIds:[...], dueAt:{start,end}, createdAt:{...}}})`. This query **cannot filter by ID**.
- For specific IDs, alias `post(input:{id})` lookups into one query, up to **30 aliases**.
- Query limits: complexity 175k, depth 25, 15k tokens.

**Amr's dev account (checked via the Buffer MCP, 2026-11-04):**
- Org "My organization" `6ad197de6393066695630954`, on the Free plan.
  - Limits: **3 channels, 10 scheduled posts**, 100 ideas.
  - Timezone Africa/Cairo.
- One channel: LinkedIn profile "Amr Alaa" `6aeaf8e8e29c69a1715a60d9`. This is the **real public profile**, so test with `saveToDraft: true`. Consider adding a throwaway second channel for publish tests (e.g. Bluesky or Mastodon).
- The MCP draws on the personal quota: 150 / 15 min, 600 / 24 h, 1,000 / 30 days. That is separate from the app client's quota.

**Rate limits (the binding constraint for cleanup):**
- The contest handbook gives the Free tier as **100 / 15 min, 250 / 24 h, 3,000 / 30 days, per client, shared by all users including judges**.
- The docs give a base of 100 / 500 / 15,000, plus +10 / +25 / +100 per authorized user.
- Design for the handbook numbers. A 429 includes a `Retry-After` header and the code `RATE_LIMIT_EXCEEDED`, and doesn't count against quota. Every other failed request does count.
- Every response carries `RateLimit` and `RateLimit-Policy` headers with `r` (remaining) and `t` (seconds to reset). Match the window by `w`.
- Throttle at about 10% remaining.

## 7. Task plan

Status key: `[ ]` todo, `[~]` in progress, `[x]` done, `[-]` dropped.
Owner tags: **[YOU]** means Amr does it (accounts, setup, content, recording). **[CC]** means Claude Code does it. Update the boxes as you go.

### Done (Nov 4)
- [x] [YOU] Register for the contest (confirmation email received).
- [x] [CC] Read the handbook and API guides. Findings are in section 6a.
- [x] [YOU] App client `media-bridge` (Private) with scopes `posts:read posts:write account:read offline_access` and redirect `https://localhost:8000/callback`.
- [x] [CC] uv + FastAPI skeleton, local HTTPS, OAuth with PKCE and rotating refresh, Buffer GraphQL client.
- [x] [YOU] R2 bucket `media-bridge` with a public r2.dev URL and an API token.
- [x] [CC] R2 upload/delete helper. Smoke test: R2 image → LinkedIn draft with alt text, verified live.

### Setup on Amr's side, start now (these block later steps)
- [-] [YOU] **Second Buffer channel for publish tests.** Dropped: Amr is OK with publishing on LinkedIn. Test posts are listed in `test_data/posts.csv`. Connect a throwaway Bluesky or Mastodon account to the same Buffer org (the Free plan allows 3). Needed by the Day 3–4 "post publishes → file purged" test, so it doesn't post to the real LinkedIn.
- [ ] [YOU] **Second Buffer account** (different email, Free plan, one channel). Use it to test the OAuth flow the way judges will, as an account that isn't the app owner.
- [x] [YOU] **Postgres:** Neon project `media-bridge` (`wild-king-33369087`) in org Amr, region aws-eu-central-1 (Frankfurt), close to the R2 bucket (WEUR). `.env` uses the direct (unpooled) endpoint as `postgresql+psycopg://`.
- [ ] [YOU] **Hosting account:** Render or Fly.io, on a paid **always-on** instance (a few USD a month). Free tiers sleep, which stops the cleanup job and can fail the judges' first request. Connect it to the GitHub repo.
- [ ] [YOU] **Domain (recommended):** a domain on Cloudflare for `media.<domain>` (the R2 custom domain, replacing r2.dev, which Cloudflare rate-limits and labels as dev-only) and `app.<domain>` (the app). Skip it if needed; r2.dev plus the host's default URL also work.
- [x] [YOU] **Product name:** `media-bridge`.
- [ ] [YOU] Join the contest Discord and post a one-line intro. That is build-in-public post #1, and it must disclose it's about Buffer Commit.
- [ ] [YOU] Delete the smoke-test draft in Buffer (post `6aeb02cd1d881477a61aa3cc`). After that, its R2 object can be removed.

### Day 3–4 (Nov 5–7): lifecycle [CC]
- [x] [CC] `media_files` and `cleanup_events` tables. Keep `create_all` (no Alembic) unless the schema needs to change after deploy.
- [x] [CC] `POST /api/files` (upload): validate type and size, store in R2, insert a row (UPLOADED).
- [x] [CC] `POST /api/files/{id}/post`: create the Buffer post (queue, scheduled or draft) with the file URL, then set `buffer_post_id` and `due_at`, state HELD. Show a clear error on `LimitReachedError` (the Free plan allows 10 scheduled posts).
- [x] [CC] Cleanup job (in-process thread that sleeps until the next `next_check_at`; APScheduler wasn't needed). It checks only files past `due_at`, with up to 30 aliased lookups per call, follows the section 5 decision table, writes `cleanup_events`, and backs off on rate limits.
- [x] [CC] TTL expiry (`MEDIA_TTL_DAYS`) and handling for a post deleted in Buffer (resolves the open question in section 6).
- [x] [CC] "Delete now" per file (`POST /api/files/{id}/delete`). If the post is still pending, warn that it will lose its image.
- [ ] [CC + YOU] Live test: schedule a post 5–10 min out on the throwaway channel, then confirm the file survives until `sent` and is purged after. Needs the second channel.

### Day 5 (Nov 8): UI [CC]
- [ ] [CC] Upload page: drag-and-drop, channel picker, caption, alt text, and a queue / schedule / draft choice.
- [ ] [CC] Status page: files with state, linked post, due and purge times, and the delete-now button.
- [ ] [CC] Privacy note: what is stored, for how long, and how to delete it. Also serve it at `/privacy` so its URL can go on the app client.
- [ ] [CC] Friendly errors: Buffer rejections, rate limits, reconnect prompts.
- [ ] [YOU] Review the UI. The Delight Award is judged on user experience.

### Day 6–7 (Nov 9–10): add-ons, only if core is done
- [ ] [CC] Image prep per network (Pillow: resize, compress, convert format).
- [ ] [CC] Agent access: a per-user API token plus a Claude Code skill or MCP tool `upload_and_post`. Buffer's own MCP can't upload, which makes a good story for the write-up.
- [ ] [CC] Stats page from `cleanup_events` (files held and purged, bytes, average hold time).

### Day 8 (Nov 11): ship
- [ ] [CC] Dockerfile, deploy config, README, structured logging. `/health` already exists.
- [ ] [YOU] Deploy. Set the env vars on the host (the `.env` values with the Postgres URL, and `BUFFER_REDIRECT_URI` / `APP_BASE_URL` set to the production URL).
- [ ] [YOU] App client: add the production redirect URI `https://<app-domain>/callback`, the logo and the privacy policy URL (`/privacy`).
- [ ] [YOU] R2: attach the custom domain and update `R2_PUBLIC_BASE_URL` (if a domain is used).
- [ ] [CC + YOU] End-to-end test on production using the **second Buffer account**.
- [ ] [CC] Rate-limit review of the cleanup job against real usage.

### Day 9 (Nov 12): submit
- [ ] [CC] Draft the ~300-word summary (problem with the roadmap votes, audience, API surface, next steps) and a longer README. [YOU] Edit it into your voice.
- [ ] [YOU] Record the demo video (**≤ 2 min**, live API, no slides): upload → schedule → shows in Buffer → publishes → file purged. Use section 8 as the script; schedule the post ~5 min out before recording.
- [ ] [YOU] Get ready for the form: app client ID, full legal name, registration email (the verified Buffer email), social handles.
- [ ] [YOU] Check the public app link from a fresh private browser window.
- [ ] [YOU] Submit at https://buffer.com/api/commit/submit before **Nov 13, 11:59 PM PT** (Nov 14, 09:59 Cairo).
- [ ] [YOU] Build-in-public: 3–5 posts between now and Nov 13, each disclosing it's about Buffer Commit. Save the links; the form takes up to five.
- [ ] [YOU] Keep the host, DB and R2 running until at least **Dec 7**.

Buffer slack: Nov 13 is the hard deadline; the plan leaves one day of margin.

## 8. Demo script (what judges should see)

1. Log in with Buffer (OAuth).
2. Drag an image in, write a caption, pick a channel, schedule for 10 minutes out.
3. Show the post in Buffer's queue with the image attached.
4. Show the status page: file is HELD with the post ID.
5. After the post publishes, refresh: file is PURGED, with the cleanup event and timestamp.
6. (If built) Run the same flow from Claude Code with the skill.

## 9. Risks and mitigations

| Risk | Mitigation |
|---|---|
| ~~Buffer copies media at creation time~~ | Resolved. The docs confirm Buffer fetches at publish time, so the hold logic is needed. |
| App client rate limits (about 250/day, shared by all users and judges) | Poll only files that are past `due_at`. Use 30 aliased lookups per call, cache org and channels, and throttle at 10% remaining. |
| Refresh-token replay revokes a user's grant | Rotate tokens under a DB row lock, persist the new token before using it, and never retry a refresh with the same token. |
| Hosting goes down during judging (Nov 16 – Dec 7) | Health checks, pick a provider with an always-on tier (free tiers that sleep may fail), test a day early. |
| Scope creep | Add-ons only after section 4 "Core" is fully checked off. |
| Judged as a "technical demo" rather than useful | The terms say usefulness means a real user's problem, not technical skill. Lead the video and summary with the user's pain, show the tech second. |
| OAuth app restricted to the developer account | Confirm the App Client works for a second Buffer account before submitting; judges use test accounts. |

## 10. Decisions log

- 2026-10-31: Explored four ideas (content agent, bilingual pipeline, agent gateway, warehouse connector).
- 2026-11-03: Designed "Leash" scoped-token gateway; judged too complex / low roadmap demand (4 votes).
- 2026-11-04: **Chose media hosting as the core feature.** Keep it simple. Leash parked as a late add-on.
- 2026-11-04: Verified contest rules on the official page; confirmed submission needs app link + write-up + demo video, registration required, service must stay up through judging (to Dec 7).
- 2026-11-04: Lifecycle built and tested live (scenarios 1, 3, 4 and 6 pass).
  - The cleanup job is a thread that sleeps until `min(next_check_at)`, woken early by uploads and posts. This replaced APScheduler.
  - Postgres connections use NullPool, so idle pooled connections can't keep Neon awake.
  - Uploads never attached to a post expire after 24 h.
  - A Buffer rejection leaves the file UPLOADED so the user can retry. The `FAILED` state was dropped as unused.
  - `scripts/cli.py` drives the lifecycle from the terminal.
- 2026-11-04: Moved to Neon Postgres in Frankfurt, matching the R2 bucket's WEUR location.
  - The app uses the **direct** endpoint, not `-pooler`: a long-running server with its own SQLAlchemy pool doesn't need PgBouncer, and this avoids prepared-statement issues in transaction pooling mode.
  - Installed the Neon CLI, the Neon MCP server (user level) and the `neon` and `neon-postgres` skills (project level).
- 2026-11-04: The name is **media-bridge**. Live tests publish to Amr's LinkedIn.
  - `test_data/posts.csv` holds the 9 test scenarios. Only 3 publish on LinkedIn, and those double as build-in-public posts.
  - The images go in `test_data/images/`, which is gitignored.
- 2026-11-04: Smoke test passed. A dummy PNG went to R2, and a LinkedIn draft was created with the image and alt text attached.
  - Buffer stores **our URL** as the asset source (`assets[0].source` = the r2.dev URL), not a copy. This confirms the file must outlive the post.
  - The live app-client quota with 1 user is 110 / 15 min, 525 / 24 h and 15,100 / 30 days. That matches the docs' formula (base + per-user), not the handbook's 250 a day. Keep the cleanup design conservative anyway.
- 2026-11-04: OAuth verified live against Amr's account; a refresh token was issued. The first attempt failed with `invalid_scope` because `posts:write` wasn't enabled on the client. Check the client's permissions if a judge ever sees that error.
- 2026-11-04: Day 1 code: uv project, FastAPI, SQLAlchemy (SQLite locally, Postgres in prod), confidential App Client named `media-bridge`. The OAuth tx is held in an encrypted cookie, users are keyed by `buffer_account_id`, and the first org is used.
- 2026-11-04: Read the developer handbook and the API docs.
  - Buffer fetches media at publish time, which confirms the core value.
  - Rate limits are per client and shared, about 250 a day per the handbook, so cleanup polls only due files with batched aliased lookups.
  - PKCE is mandatory and refresh tokens rotate. Local dev needs HTTPS.
  - Alt text is supported.
  - `media_files` gains `channel_id`, `due_at` and `last_post_status`.
- 2026-11-04: Read the terms. Changes: demo video ≤ 2 min; summary ~300 words with four required parts; app client ID required; name must not imply an official Buffer product; data-minimization clause → add privacy note and delete action; judging ~Nov 16–20 with a 9/15 minimum score.

## 11. Useful links

- Contest: https://buffer.com/api/commit
- Register: https://buffer.com/api/commit/register
- Submit: https://buffer.com/api/commit/submit
- Terms: https://buffer.com/api/commit/terms
- Builder handbook: https://buffer.notion.site/Buffer-Commit-Developer-Handbook-3d7a7f5a00fd80918466e36eb2cba9f8
- API docs home: https://developers.buffer.com
- Roadmap: https://developers.buffer.com/roadmap.html
- Rate limits: https://developers.buffer.com/guides/api-limits.html
- Post metrics (why analytics is out of scope): https://developers.buffer.com/guides/post-metrics.html
- Explorer: https://developers.buffer.com/explorer.html
- Feature suggestions board: https://suggestions.buffer.com
