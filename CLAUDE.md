# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project plan

`buffer-media-bridge-plan.md` is the source of truth. It holds the objective, contest rules, scope, architecture, Buffer API facts (section 6a), the day-by-day task plan, and a decisions log. Read it before starting any work. When you finish work, update it:
- Tick task statuses (`[ ]` / `[~]` / `[x]` / `[-]`) in section 7.
- Tick the unknowns in section 6 as they are verified.
- Add dated entries to the Decisions log (section 10).

## Commands

The project uses uv (Python ≥3.12). Secrets live in `.env`, which is gitignored. `.env.example` is the template.

```sh
uv sync                                   # install deps
uv run pytest                             # all tests
uv run pytest tests/test_oauth.py::test_failed_refresh_disconnects_and_is_not_retried  # one test
uv run ruff check . && uv run ruff format .
# dev server — Buffer requires HTTPS even on localhost; certs/ is a gitignored self-signed pair
uv run uvicorn app.main:app --port 8000 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem --reload
```

Regenerate the dev certificate with:
`openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "//CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" -keyout certs/key.pem -out certs/cert.pem`

The database is Neon Postgres: project `media-bridge` (`wild-king-33369087`), Frankfurt, linked through the gitignored `.neon` file.
- **Schema changes:** there are no migrations. `init_db()` runs `create_all` and then `_add_missing_columns()`, which adds any new **nullable** column to existing tables on startup (dev and prod alike). Anything else (renames, type changes, NOT NULL) needs a hand-written migration.
- Local development uses the **`dev` branch** (`br-raspy-tree-b94qulg7`). **`main` is production only.** Never point a local server at `main`: its cleanup worker would act on live files, and a copied refresh token could get replayed and revoke the user's Buffer grant.
- `DATABASE_URL` must use the `postgresql+psycopg://` scheme and the **direct** (non-`-pooler`) host.
- `neon env pull` writes a plain `postgresql://` URL, so rewrite it by hand.
- SQLite (`sqlite:///./dev.db`) still works as an offline fallback.
- The Neon CLI, MCP server and skills (`.claude/skills/neon*`) are installed. Tables are created by `init_db()` on startup; there are no migrations yet.

Tests set their env vars in `tests/conftest.py` before importing `app.*`, because `app/db.py` builds the engine at import time. Buffer HTTP calls are faked with `httpx.MockTransport`. The app passes one shared `httpx.Client` into the functions that call Buffer, so tests can swap it.

## Windows editing gotcha

Python's default file encoding here is cp1252. When editing files from scripts, always pass `encoding="utf-8"` (or set `PYTHONUTF8=1`): writing a non-cp1252 character such as `↗` raises mid-write and **truncates the file to 0 bytes**. That happened once to `app/static/app.js`. Prefer the Edit tool.

## Deploy (Render)

**Production: https://media-bridge-b4qm.onrender.com.** It auto-deploys on every push to `main`.


- `render.yaml` is a Blueprint: native Python runtime (no Docker) in Frankfurt.
  - Build: `pip install uv && uv sync --frozen --no-dev`.
  - Start: `uv run --no-sync uvicorn app.main:app --host 0.0.0.0 --port $PORT --proxy-headers`.
- Production env vars live in the gitignored `.env.production`.
  - `DATABASE_URL` there is the Neon **main** branch.
  - `FORWARDED_ALLOW_IPS=*` must stay an env var. A `*` in the start command gets glob-expanded into file names.
- Keep `/health` free of DB access, because Render's health checks would otherwise keep Neon awake.
- The cleanup worker takes a Postgres advisory lock (`cleanup.single_runner()`) each pass, so deploy overlap can't run two workers.

## Code map

- `app/oauth.py` handles PKCE, the code exchange and `get_access_token()`. That function is the **only** place tokens are refreshed (see the rotation rules below).
- `app/buffer_client.py` holds the `graphql()` helper, typed errors (`BufferUnauthorized`, `BufferRateLimited`) and the module-level `rate_limits` state parsed from the `RateLimit` header.
- `app/storage.py` uploads to and deletes from R2 with boto3 (S3 API). Keys are `uuid4.ext`, and public URLs come from `R2_PUBLIC_BASE_URL`.
- `scripts/smoke_test.py` (`uv run python -m scripts.smoke_test`) runs the live end-to-end check: dummy PNG → R2 → Buffer **draft** on the first channel, using the first logged-in user in the local DB.
- `app/media.py` is the lifecycle service layer: `upload_file` sniffs magic bytes and enforces the size limit, `post_file` creates the post and moves the file UPLOADED → HELD, `remove_file` deletes from R2 and writes a `CleanupEvent`, and `next_check_for` decides when to look again. Routes, the CLI and the cleanup job all go through it.
- `app/cleanup.py` holds `run_pass()`, which runs TTL expiry and then batched status checks of due HELD files, and `CleanupWorker`.
  - The worker is a daemon thread that sleeps until the earliest `next_check_at` (capped at 6 h). `poke()` wakes it early.
  - It assumes **one app process**. Running several workers would double-check files.
  - Any code path that leaves a file due must advance `next_check_at` or return a back-off time. Otherwise the worker spins.
- `app/buffer_client.get_posts()` checks up to 30 posts per request using aliases. A deleted post comes back as `NOT_FOUND` with `data: null` for the *whole* response, so its siblings come back unknown and get re-checked 15 min later.
- **UI:** `app/templates/*.html` (Jinja, extending `base.html`) and `app/static/{style.css,app.js}`.
  - The JS calls only the JSON API (`/api/files`, `/api/files/{id}/post`, `/api/files/{id}/delete`, `/api/channels`, `/api/account/delete`) and turns states into plain-language copy in `describe()`.
  - CSS colours are tokens on `:root`, with a dark-mode override. `[hidden]` is forced to `display: none` because component `display` rules would otherwise beat it.
- **Running, screenshotting and driving the UI** is covered by the project skill `/run-media-bridge` (`.claude/skills/run-media-bridge/`). Its `driver.py` drives the installed Edge via Playwright, and its gotchas section covers stale `--reload`, the forged session cookie and Buffer quota costs.
- `app/stats.py` computes the public, anonymous aggregates for `/stats` and `/api/stats`. "Status checks per post" counts `CleanupEvent`s with reason `status_*`, `post_sent` or `post_deleted`. The chart (`app/static/stats.js`) uses the `--chart-bar` token, validated light (`#0d8f7f`) and dark (`#27ab99`) with the dataviz `validate_palette.js`. Don't swap in the brighter accent.
- `app/agent_keys.py` handles agent keys (`mb_` + 32 random bytes). Only the SHA-256 is stored, and the key is shown once.
  - `require_user` accepts `Authorization: Bearer mb_…` or the session cookie.
  - `require_session_user` (key management) accepts the session **only**, so a leaked key can't mint keys.
  - The copy-paste agent prompt is built client-side in `agentPrompt()` in `app/static/app.js`. If an API route changes, update that prompt too: agents follow it literally.
- `scripts/cli.py` handles `post` / `files` / `check [--force]` / `delete` as the first DB user. Use it for live tests.
- `app/main.py` holds the routes. The OAuth `state` and PKCE verifier travel in the Fernet-encrypted `oauth_tx` cookie, and the logged-in user id is kept in Starlette's signed session cookie.

## What is being built

A small service for the Buffer Commit contest (submission deadline **Nov 13, 2026, 11:59 PM PT**). It lets a Buffer user upload an image, hosts the image for them, creates a Buffer post that uses it, and deletes the file once the post has been sent. The guiding principle is to keep it simple: get the core feature (plan section 4) working fully before starting any add-on.

## Planned architecture (plan section 5)

- **FastAPI** (Python 3.12) app, with **httpx** for calls to Buffer's **GraphQL** API.
- **Buffer OAuth via an App Client.** Do not use a personal API key: the contest requires OAuth, and it must work for any Buffer account because judges use their own test accounts.
- **Postgres** with the tables `users`, `oauth_tokens`, `media_files` and `cleanup_events`. `media_files.state` moves through `UPLOADED → HELD → PURGED | EXPIRED`.
- **Cloudflare R2** public bucket with unguessable `uuid4.ext` keys. Do not use expiring signed URLs, because a scheduled post may publish weeks later.
- **Cleanup job** (APScheduler or a separate worker, not Celery/Redis). It polls `HELD` files and deletes the object when the post is sent, when the post has been deleted, or when the TTL expires. Every decision is written to `cleanup_events`.

## Hard constraints

- **Rate limits are per client and shared by all users, including judges.** Measured live: 110 per 15 minutes, 525 per 24 hours and 15,100 per 30 days with 1 user, growing per authorized user. The handbook says 250 a day, so stay conservative.
  - The cleanup job polls only files past their `due_at`.
  - It batches up to 30 aliased `post(id)` lookups per request.
  - It caches the org and channels, honors `Retry-After` on 429, and throttles using the `RateLimit` header.
- **OAuth:** PKCE (S256) is mandatory even for confidential clients. Request `offline_access` or no refresh token is issued.
  - **Refresh tokens are single-use.** Reusing one revokes the user's whole grant. Refresh under a DB lock, persist the new token immediately, and never retry a failed refresh with the same token.
  - Keep `state` and `code_verifier` in a shared store or encrypted cookie, not in process memory.
  - HTTPS is required even on localhost.
- **Media hosting:** Buffer has no upload endpoint. It fetches the image URL at `createPost` time and again at publish time, so an object must not be deleted before the post's status is `sent`.
- **No idempotency on `createPost`:** don't blindly retry after a timeout.
- Section 6a of the plan has the exact GraphQL shapes, endpoints, scopes and status enums. Use them instead of guessing.
- **Secrets:** encrypt OAuth tokens at rest (Fernet or libsodium) and never log them.
- **Data minimization (contest terms):** store only the image and minimal metadata. Show a privacy note on the upload page, provide a "delete now" action for each file, and enforce the lifecycle deletion.
- **Naming:** the product must not look like an official Buffer product. Don't put "Buffer" first in the product name. "Built on the Buffer API" is allowed.
- **Out of scope:** post analytics (App Clients can't read metrics), video in Ideas (Buffer's API rejects it), and billing/teams features.
- The service must stay publicly reachable through Dec 7, 2026.
