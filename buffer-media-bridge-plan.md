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
- Builder handbook (technical FAQ, could not be fetched automatically; read it manually): https://buffer.notion.site/Buffer-Commit-Developer-Handbook-3d7a7f5a00fd80918466e36eb2cba9f8
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

Scheduled cleanup job (every few minutes):
  for each media_file in state HELD:
    query post status via Buffer API
    if sent        -> delete object, state = PURGED
    if post deleted-> delete object, state = PURGED
    if now > ttl   -> delete object, state = EXPIRED
    else keep
```

### Stack decisions
- **API**: Python 3.12, FastAPI, httpx for Buffer calls.
- **DB**: Postgres (Neon or Supabase free tier). SQLAlchemy or raw SQL; keep it light.
- **Storage**: Cloudflare R2 (S3-compatible, no egress fees). Public bucket with unguessable object keys (e.g. `uuid4.ext`). Do **not** use expiring signed URLs: a scheduled post may be published weeks later.
- **Jobs**: APScheduler inside the app or a separate worker process. Avoid Celery/Redis unless needed.
- **Hosting**: Fly.io or Render (must stay up through judging).
- **Secrets**: encrypt Buffer refresh tokens at rest (Fernet / libsodium); never log tokens.

### Data model (initial)
```
users          id, buffer_org_id, created_at
oauth_tokens   user_id, access_token_enc, refresh_token_enc, expires_at
media_files    id, user_id, object_key, public_url, content_type, size_bytes,
               buffer_post_id (nullable), state (UPLOADED|HELD|PURGED|EXPIRED|FAILED),
               ttl_expires_at, created_at, purged_at, last_checked_at
cleanup_events id, media_file_id, decision, reason, checked_at   (audit trail, feeds stats page)
```

## 6. Things to verify before building (unknowns)

- [ ] Exact GraphQL mutation shape for `createPost` with an image asset (field names, required channel/org IDs). Check Explorer: https://developers.buffer.com/explorer.html and the "Create Image Post" example.
- [ ] Which post status values exist and which one means "sent/published". Check "Posts & Scheduling" guide.
- [ ] Does Buffer fetch the image at post-creation time or at publish time? This decides whether we must hold the file until publish. The roadmap complaint suggests publish time; confirm empirically with a scheduled post.
- [ ] Image constraints Buffer enforces (max size, formats) — "Hosting Media" guide.
- [ ] OAuth scopes available to App Clients and the registration flow — "Building Apps" + "Authentication" guides.
- [ ] Rate limits for App Clients: 100 req / 15 min and 500 / 24 h base, growing per authorized user. Cleanup polling must stay well inside this (batch posts per query, back off on 429, honor Retry-After).
- [ ] Whether assets support alt text (only matters for add-on 3).

## 7. Task plan

Status key: `[ ]` todo, `[~]` in progress, `[x]` done, `[-]` dropped. Update as you go.

### Day 1–2 (Nov 4–5): foundation
- [ ] Register for the contest with the Buffer account: https://buffer.com/api/commit/register
- [ ] Read the builder handbook and the terms; note anything that changes this plan in the "Decisions log".
- [ ] Join the contest Discord and post a one-line "what I'm building" intro (first build-in-public post).
- [ ] Register Buffer App Client, get client id/secret, set redirect URL.
- [ ] Repo skeleton: FastAPI app, config via env vars, Dockerfile, README stub.
- [ ] OAuth flow: login → callback → store encrypted tokens → token refresh helper.
- [ ] Buffer client module: `get_channels()`, `create_post(channel_id, text, image_url, scheduled_at | draft)`, `get_post(post_id)`.
- [ ] R2 bucket + upload helper returning public URL.
- [ ] Smoke test: upload a file manually, create a draft post with it, see it in Buffer.

### Day 3–4 (Nov 6–7): lifecycle
- [ ] Postgres schema (section 5) + migrations.
- [ ] `POST /upload` → stores object, inserts `media_files` row (UPLOADED).
- [ ] `POST /posts` → creates Buffer post with the file's URL, sets `buffer_post_id`, state HELD.
- [ ] Cleanup job: poll HELD files, apply decision table, write `cleanup_events`.
- [ ] TTL default (e.g. 60 days) and a "post deleted on Buffer" check.
- [ ] Test: create a post scheduled 5–10 minutes out, confirm file survives until sent and is purged after.

### Day 5 (Nov 8): UI
- [ ] Upload page (file picker, channel dropdown, text, schedule or draft).
- [ ] Privacy note on the upload page (what is stored, for how long, how to delete) and a "delete now" action per file — required by the terms' data-minimization clause.
- [ ] Decide the product name (not Buffer-first; see Naming in section 2).
- [ ] Status page listing files with state, linked post, and timestamps.
- [ ] Basic error display (Buffer errors, rate limit messages).

### Day 6–7 (Nov 9–10): add-ons (pick what fits)
- [ ] Image prep per network (Pillow: resize, compress, format convert).
- [ ] Claude Code skill / MCP tool: single `upload_and_post` action calling the JSON API.
- [ ] Stats page from `cleanup_events` (optional).

### Day 8 (Nov 11): ship
- [ ] Deploy to Fly.io/Render with Postgres + R2 credentials.
- [ ] Full end-to-end test from a fresh Buffer account via OAuth.
- [ ] Rate-limit safety check on the cleanup job.
- [ ] Logging and a simple health endpoint.

### Day 9 (Nov 12): submit
- [ ] Written summary (required), ~300 words, in this order: problem solved (cite the two roadmap requests and vote counts), intended audience (people who post daily and automate with the API or agents), Buffer API surface used (OAuth, createPost with image asset, post status queries), planned next steps. Keep a longer README separately.
- [ ] Have the app client ID, full legal name, registration email, and social handles ready for the form.
- [ ] Demo video link (required), **under 2 minutes**, recorded against the live API: upload → schedule → post publishes → file auto-purged. No slides.
- [ ] Public app link (required): confirm it works logged-out from a fresh browser.
- [ ] Submit at https://buffer.com/api/commit/submit before Nov 13, 11:59 PM PT (that is Nov 14, 09:59 AM Cairo time).
- [ ] Keep the service running until at least Dec 7 (winners announced).
- [ ] Build-in-public: 3–5 public posts during the week, each disclosing it is about participating in Buffer Commit. Save the links; the form takes up to five.
- [ ] Spend 1–2 hours on UI polish before submitting (Delight Award is judged on user experience).

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
| Buffer copies media at creation time, making the hold logic unnecessary | Still valuable: users get hosting they didn't have. Reframe the hold as "safe by default"; shorten default TTL. |
| App Client rate limits too low for polling | Batch post lookups; poll HELD files on a backoff schedule (e.g. only near scheduled time). |
| Hosting goes down during judging (Nov 16 – Dec 7) | Health checks, pick a provider with an always-on tier (free tiers that sleep may fail), test a day early. |
| Scope creep | Add-ons only after section 4 "Core" is fully checked off. |
| Judged as a "technical demo" rather than useful | The terms say usefulness means a real user's problem, not technical skill. Lead the video and summary with the user's pain, show the tech second. |
| OAuth app restricted to the developer account | Confirm the App Client works for a second Buffer account before submitting; judges use test accounts. |

## 10. Decisions log

- 2026-10-31: Explored four ideas (content agent, bilingual pipeline, agent gateway, warehouse connector).
- 2026-11-03: Designed "Leash" scoped-token gateway; judged too complex / low roadmap demand (4 votes).
- 2026-11-04: **Chose media hosting as the core feature.** Keep it simple. Leash parked as a late add-on.
- 2026-11-04: Verified contest rules on the official page; confirmed submission needs app link + write-up + demo video, registration required, service must stay up through judging (to Dec 7).
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
