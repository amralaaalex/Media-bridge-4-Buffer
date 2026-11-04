---
name: run-media-bridge
description: Start, run, test, screenshot and drive the media-bridge web app (FastAPI + Buffer API). Use when asked to run or start the server, take screenshots of the UI, check the UI in a browser, drive an upload/post through the page, run the lifecycle CLI, or run the tests.
---

media-bridge is a FastAPI app served over local HTTPS. The agent path has three steps:
1. Start the server in the background and poll `/health`.
2. Drive the real UI in the installed **Microsoft Edge** through Playwright with
   `.claude/skills/run-media-bridge/driver.py`.
3. Use `scripts/cli.py` for the file lifecycle without a browser.

All paths are relative to the repo root.

Everything below was verified on **Windows 11** (Git Bash plus PowerShell), not in a Linux container.

## Prerequisites

- `uv` and Python ≥ 3.12. uv uses the project's `.venv`.
- `openssl` and `curl`. Both ship with Git for Windows.
- Microsoft Edge, preinstalled on Windows. The driver launches it with `channel="msedge"`, so **no Playwright browser download** is needed.
- A filled-in `.env`. Copy `.env.example`; it needs the real Buffer app client, R2 and Neon values. It's gitignored, so get it from the owner.

## Setup

```bash
uv sync
mkdir -p certs .run
openssl req -x509 -newkey rsa:2048 -nodes -days 365 -subj "//CN=localhost" -addext "subjectAltName=DNS:localhost,IP:127.0.0.1" -keyout certs/key.pem -out certs/cert.pem
```

**A human must log in once** at https://localhost:8000/login. Buffer's OAuth consent page can't be automated. That creates user `1` in the DB, and both the driver and the CLI act as that user.

## Run (agent path)

Start the server in the background (no `--reload`, see Gotchas) and wait until it answers:

```bash
(uv run uvicorn app.main:app --port 8000 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem > .run/server.log 2>&1 &)
timeout 60 bash -c 'until curl -skf https://localhost:8000/health >/dev/null; do sleep 1; done'
curl -sk https://localhost:8000/health
```

Drive the UI. Both commands exit non-zero if the page logged console errors:

```bash
uv run --with playwright python .claude/skills/run-media-bridge/driver.py shots
uv run --with playwright python .claude/skills/run-media-bridge/driver.py draft-flow
```

| command | what it does |
|---|---|
| `shots` | Screenshots the landing page, `/privacy`, and the app page (empty, plus a filled composer in Schedule mode) at 1280 and 390 px, in light and dark. **No Buffer calls** except the cached channel list. |
| `draft-flow` | Uploads a generated PNG through the composer as a Buffer **draft** (never publishes), then clicks **Delete now** and accepts the warning. It prints `leftover Buffer draft to delete: <id>`; delete that post with the Buffer MCP `delete_post` or in Buffer's UI. |

Options are `--base` (default `https://localhost:8000`) and `--uid` (default `1`). Screenshots go to `.run/shots/*.png`, which is gitignored. **Look at them** with the Read tool.

Drive the lifecycle without a browser, using the same code paths as the API:

```bash
uv run python -m scripts.cli files                 # every file with state, post status, next check
uv run python -m scripts.cli check --force         # one cleanup pass now (treats all HELD as due)
uv run python -m scripts.cli post IMG --text "..." --mode draft --alt "..."
uv run python -m scripts.cli delete FILE_ID        # "delete now"
uv run python -m scripts.smoke_test                # dummy PNG -> R2 -> Buffer draft
```

Stop the server, killing the process tree on the port, in PowerShell:

```powershell
taskkill /T /F /PID (Get-NetTCPConnection -LocalPort 8000 -State Listen).OwningProcess
```

## Run (human path)

```bash
uv run uvicorn app.main:app --port 8000 --ssl-keyfile certs/key.pem --ssl-certfile certs/cert.pem --reload
```

Then open https://localhost:8000 and accept the self-signed certificate warning. Stop with Ctrl+C.

## Test

```bash
uv run pytest
uv run ruff check . && uv run ruff format --check .
```

Expect 21 passed. Buffer and R2 are faked, the DB is a temporary SQLite file, and the cleanup worker is off (`CLEANUP_WORKER_ENABLED=false` in `tests/conftest.py`).

## Gotchas

- **The channel is Amr's real LinkedIn profile.** `--mode now`, `queue` and `schedule` publish publicly. Use `draft` for anything automated. The 3 planned public posts are listed in `test_data/posts.csv`.
- **The Buffer quota is shared by every user, judges included.**
  - It's about 525 app-client calls a day; `/health` shows `buffer_rate_limit_min_remaining`.
  - `draft-flow` costs about 2 calls and `check --force` about 1 per 30 held files.
  - The Buffer **MCP** draws on the owner's *personal* quota instead, which is why it's the right tool for deleting test drafts.
- **`uvicorn --reload` can stop reloading** after a few edits and keep serving old code. The symptom is a new route (e.g. `/privacy`) returning `{"detail":"Not Found"}`. The agent path runs without `--reload`; restart after code changes.
- **Logged-in pages come from a forged session cookie.** The driver signs Starlette's `session` cookie as `TimestampSigner(SESSION_SECRET).sign(base64(json({"uid": N})))`.
  - If user N doesn't exist or is disconnected, `/` renders the landing page instead.
  - Then `wait_for_selector(".channel")` times out.
- **Wait for `.channel`, not page load.** Channels arrive later from `/api/channels`, and the file list can render before them.
- **Scope text selectors** like `#modes >> text=Schedule`. A bare `text=Schedule` can match the "Scheduled" status badges in the file list.
- **`[hidden]` needs `display: none !important`** in `style.css`. Component `display:flex/grid` rules otherwise beat the attribute. That bug showed both the dropzone prompt and the date picker at once.
- **The first request after idle is slow**, by hundreds of ms. Neon scales to zero and the app opens a fresh connection per request (NullPool) on purpose.

## Troubleshooting

- **`Page.wait_for_selector: Timeout 20000ms exceeded ... locator(".channel")`**: the server is stale (check `curl -sk https://localhost:8000/privacy`) or user `--uid` isn't logged in. Restart the server, or log in at `/login`.
- **Buffer page says `invalid_scope` at login**: a scope isn't enabled on the app client. `posts:write` was the culprit once; enable it in publish.buffer.com → Settings → API → App Clients.
- **`curl` to `/health` never succeeds after start**: read `.run/server.log`. A port already in use means a previous server is alive; run the stop command first.
