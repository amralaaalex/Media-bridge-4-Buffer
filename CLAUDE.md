# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Current state

No code exists yet. The only source of truth is `buffer-media-bridge-plan.md`: it holds the objective, contest rules, scope, architecture, open questions, the day-by-day task plan, and a decisions log. Read it before starting any work. When you finish work, update it: tick task statuses (`[ ]` / `[~]` / `[x]` / `[-]`) in section 7, tick the unknowns in section 6 as they are verified, and add dated entries to the Decisions log (section 10).

When the repo skeleton is created, add the real build, run, test and lint commands to this file. Until then, don't assume any.

## What is being built

A small service for the Buffer Commit contest (submission deadline **Nov 13, 2026, 11:59 PM PT**). It lets a Buffer user upload an image, hosts the image for them, creates a Buffer post that uses it, and deletes the file once the post has been sent. The guiding principle is to keep it simple: get the core feature (plan section 4) working fully before starting any add-on.

## Planned architecture (plan section 5)

- **FastAPI** (Python 3.12) app, with **httpx** for calls to Buffer's **GraphQL** API.
- **Buffer OAuth via an App Client.** Do not use a personal API key: the contest requires OAuth, and it must work for any Buffer account because judges use their own test accounts.
- **Postgres** with the tables `users`, `oauth_tokens`, `media_files` and `cleanup_events`. `media_files.state` moves through `UPLOADED → HELD → PURGED | EXPIRED | FAILED`.
- **Cloudflare R2** public bucket with unguessable `uuid4.ext` keys. Do not use expiring signed URLs, because a scheduled post may publish weeks later.
- **Cleanup job** (APScheduler or a separate worker, not Celery/Redis). It polls `HELD` files and deletes the object when the post is sent, when the post has been deleted, or when the TTL expires. Every decision is written to `cleanup_events`.

## Hard constraints

- **Rate limits are per client and shared by all users, including judges.** The contest handbook gives about 100 requests per 15 minutes and 250 per 24 hours.
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
