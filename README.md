# media-bridge

**Attach images to Buffer posts without hosting them yourself.** Upload an image, pick a channel, and media-bridge creates the Buffer post. It keeps the image online for exactly as long as the post needs it, then deletes it.

**Live:** https://media-bridge-b4qm.onrender.com · [Privacy](https://media-bridge-b4qm.onrender.com/privacy) · [Stats](https://media-bridge-b4qm.onrender.com/stats)

Built on the Buffer API for the [Buffer Commit](https://buffer.com/api/commit) contest. media-bridge is an independent project. It isn't affiliated with or endorsed by Buffer.

## The problem

Buffer's API takes images only as URLs. You have to host the file somewhere public first, and the file has to stay there until the post goes out: Buffer fetches it when the post is created and again when it publishes. Two of the most-voted requests on [Buffer's public API roadmap](https://developers.buffer.com/roadmap.html) are about this:

| Roadmap request | Votes |
|---|---|
| Image assets for the API: any image must already be hosted online | 24 |
| Copy media to Buffer storage after post creation: deleting source files early breaks scheduled posts | 18 |

So anyone posting through the API, whether a script, an agent or a small tool, needs a host *and* a cleanup rule. Delete the file too early and a scheduled post fails. Never delete it and public files pile up.

## How it works

1. **Connect Buffer.** Standard Buffer OAuth, so any Buffer account can connect.
2. **Upload an image** by dragging, pasting or choosing a file. The file is stored on Cloudflare R2 under an unguessable name (`uuid4.ext`).
3. **Create the post.** Pick a channel, write the caption and alt text, then add it to the queue, schedule it, share it now or save it as a draft. media-bridge calls Buffer's `createPost` with the image URL.
4. **Hold, then delete.** A background worker asks Buffer about each post only once it is due. When the post is `sent`, the image is deleted. History keeps the file name and a link to the live post, but no copy of the image.

```
UPLOADED ──post──> HELD ──post sent──────────────> PURGED
   │                │ ──post deleted in Buffer───> PURGED
   │                │ ──"Delete now"─────────────> PURGED
   │                └──never published (TTL)─────> EXPIRED
   └──never attached to a post (24 h)────────────> EXPIRED
```

Every decision (keep, purge, expire) is written to an audit log, which also feeds the public [stats page](https://media-bridge-b4qm.onrender.com/stats).

## Buffer API surface

**OAuth (App Client)**
- Authorization Code with PKCE (S256).
- Scopes: `posts:read posts:write account:read offline_access`.
- The OAuth `state` and the PKCE verifier travel in an encrypted, short-lived cookie, so they survive restarts.
- **Refresh tokens are single-use** (reusing one revokes the grant). Exactly one function refreshes them, under a database row lock. It saves the new token before using it and never retries a failed refresh with the same token.
- Tokens are encrypted at rest with Fernet and never logged.

**GraphQL** (`https://api.buffer.com`)
| Operation | Used for |
|---|---|
| `account { id organizations { id name } }` | Identify the user at login, and list their organizations |
| `channels(input: { organizationId })` | Channel picker: channels from every organization the user belongs to (cached for an hour) |
| `createPost(input: { channelId, text, mode, dueAt, saveToDraft, assets: [{ image: { url, metadata: { altText } } }] })` | Create the post. `mode` is `addToQueue`, `customScheduled` or `shareNow`, or a draft. |
| `post(input: { id }) { status dueAt sentAt externalLink error { message } }`, up to 30 aliased per request | Batched status checks by the cleanup worker |

**Rate limits.** The quota is per App Client and shared by every user, including the judges, so the worker is built to spend very little of it:
- It never polls a post before its `dueAt`. A scheduled post is first checked 2 minutes after it's due. A post that's due but not yet sent is checked every 10 minutes, an `error` post every 6 hours, and a draft once a day.
- Up to 30 posts are checked in one request using aliased `post(id)` lookups.
- No timer runs on a fixed interval. The worker sleeps until the earliest `next_check_at` (6 hours at most) and is woken early by new uploads.
- On a 429 it honors `Retry-After`, and it reads the `RateLimit` header on every response.
- `createPost` has no idempotency key, so it is never retried blindly after a timeout.

## Privacy and data retention

media-bridge stores as little as it can, for as short a time as it can. See the [privacy page](https://media-bridge-b4qm.onrender.com/privacy).
- **Stored:** the image (public but unguessable), Buffer account and organization IDs, encrypted tokens, the post ID, channel ID, status and timestamps, the file name and, after publishing, the live post link.
- **Not stored:** post text, passwords, or anything from the social accounts.
- **Images are deleted** when the post is sent, when the post is deleted in Buffer, or 24 hours after upload if never posted. If the post never publishes, the image is deleted after 60 days. A post scheduled further out than that keeps its image until 7 days after its date.
- **Delete now** removes any image immediately. If the post still needs it, a warning says so.
- **Delete my data** removes every image and every record about the user. Posts in Buffer are not touched.

## Agent access

Buffer's own MCP server can't upload images, so media-bridge gives agents a way in. On the app page, create an **agent key** (`mb_…`). It's shown once, and only its SHA-256 hash is stored. Then copy the ready-made prompt into any agent that can run `curl`: Claude Code, Cursor, Codex and others. The agent uploads the local file with `curl -F` and creates the post through the same JSON API the web page uses:

```
GET  /api/channels
POST /api/files                  (multipart upload)
POST /api/files/{id}/post        {"channel_id", "text", "mode": "queue|schedule|now|draft", "alt_text", "due_at"}
GET  /api/files                  (status)
POST /api/files/{id}/delete
```

Keys use `Authorization: Bearer mb_…`. They can be revoked, and they can't create or revoke other keys; managing keys needs a browser login.

## Run it locally

You need Python 3.12+, [uv](https://docs.astral.sh/uv/), a Buffer App Client, a Cloudflare R2 bucket with public access, and Postgres (or SQLite for offline use).

```sh
uv sync
cp .env.example .env          # fill in the values
# Buffer requires HTTPS even on localhost: make a self-signed pair in certs/
openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "/CN=localhost" \
  -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" \
  -keyout certs/key.pem -out certs/cert.pem
uv run uvicorn app.main:app --port 8000 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem --reload
```

Then register `https://localhost:8000/callback` as a redirect URI on your App Client. Tables are created on startup.

```sh
uv run pytest                          # tests; Buffer is faked with httpx.MockTransport
uv run python -m scripts.cli files     # lifecycle from the terminal: post / files / check / delete
```

## Deploy

`render.yaml` is a Render Blueprint: one always-on web service (native Python runtime) in Frankfurt, next to the Neon database and the R2 bucket.
- The cleanup worker runs inside the app process. A Postgres advisory lock stops two workers from running during a deploy overlap.
- `/health` never touches the database, so health checks don't keep it awake.

## Project layout

| Path | What it does |
|---|---|
| `app/main.py` | Routes: pages, OAuth login and callback, JSON API |
| `app/oauth.py` | PKCE, code exchange, the single token-refresh path |
| `app/buffer_client.py` | GraphQL helper, typed errors, batched status lookups, rate-limit state |
| `app/media.py` | File lifecycle: upload (type sniffing, size limit), post, delete |
| `app/cleanup.py` | Cleanup worker: TTL expiry and batched status checks |
| `app/storage.py` | R2 upload and delete (S3 API) |
| `app/agent_keys.py` | Agent keys |
| `app/stats.py` | Anonymous aggregates for `/stats` |
| `app/templates/`, `app/static/` | UI: Jinja templates and vanilla JS, no build step |

## Known limits

- Images only: JPEG, PNG, GIF and WebP, up to 20 MB. Each social network has its own limits on top of that.
- Channels from up to 10 Buffer organizations are listed (one request each).
- Buffer's Free plan allows 10 scheduled posts per organization. When Buffer rejects a post for that or any other reason, its message is shown to the user and the image stays uploaded, so the user can retry.

## Next steps

- When Buffer's API gains native media upload (on its roadmap, undated), hand files straight to Buffer and keep the lifecycle tracking and agent access.
- Resize and compress images for each network's limits before upload.
- Video.
