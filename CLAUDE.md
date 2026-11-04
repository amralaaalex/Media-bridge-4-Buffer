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

Local dev uses `DATABASE_URL=sqlite:///./dev.db`. Production uses `postgresql+psycopg://…`. Tables are created by `init_db()` on startup; there are no migrations yet.

Tests set their env vars in `tests/conftest.py` before importing `app.*`, because `app/db.py` builds the engine at import time. Buffer HTTP calls are faked with `httpx.MockTransport`. The app passes one shared `httpx.Client` into the functions that call Buffer, so tests can swap it.

## Code map

- `app/oauth.py` handles PKCE, the code exchange and `get_access_token()`. That function is the **only** place tokens are refreshed (see the rotation rules below).
- `app/buffer_client.py` holds the `graphql()` helper, typed errors (`BufferUnauthorized`, `BufferRateLimited`) and the module-level `rate_limits` state parsed from the `RateLimit` header.
- `app/storage.py` uploads to and deletes from R2 with boto3 (S3 API). Keys are `uuid4.ext`, and public URLs come from `R2_PUBLIC_BASE_URL`.
- `scripts/smoke_test.py` (`uv run python -m scripts.smoke_test`) runs the live end-to-end check: dummy PNG → R2 → Buffer **draft** on the first channel, using the first logged-in user in the local DB.
- `app/main.py` holds the routes. The OAuth `state` and PKCE verifier travel in the Fernet-encrypted `oauth_tx` cookie, and the logged-in user id is kept in Starlette's signed session cookie.

## What is being built

A small service for the Buffer Commit contest (submission deadline **Nov 13, 2026, 11:59 PM PT**). It lets a Buffer user upload an image, hosts the image for them, creates a Buffer post that uses it, and deletes the file once the post has been sent. The guiding principle is to keep it simple: get the core feature (plan section 4) working fully before starting any add-on.

## Planned architecture (plan section 5)

- **FastAPI** (Python 3.12) app, with **httpx** for calls to Buffer's **GraphQL** API.
- **Buffer OAuth via an App Client.** Do not use a personal API key: the contest requires OAuth, and it must work for any Buffer account because judges use their own test accounts.
- **Postgres** with the tables `users`, `oauth_tokens`, `media_files` and `cleanup_events`. `media_files.state` moves through `UPLOADED → HELD → PURGED | EXPIRED | FAILED`.
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
