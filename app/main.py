import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from html import escape
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from pydantic import BaseModel, Field
from sqlalchemy import select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import buffer_client, media, oauth
from app.cleanup import CleanupWorker
from app.config import get_settings
from app.crypto import InvalidToken, decrypt, encrypt
from app.db import FileState, MediaFile, User, get_db, init_db

log = logging.getLogger(__name__)

# Holds OAuth `state` + PKCE verifier between /login and /callback. Encrypted, 10 min max.
OAUTH_TX_COOKIE = "oauth_tx"
OAUTH_TX_TTL = 600
# Channels rarely change; cache them so page views don't spend the shared API quota.
CHANNEL_CACHE_TTL = 3600
_channel_cache: dict[int, tuple[float, list[dict]]] = {}


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    with httpx.Client() as http:
        app.state.http = http
        app.state.cleanup = CleanupWorker(http)
        if get_settings().cleanup_worker_enabled:
            app.state.cleanup.start()
        try:
            yield
        finally:
            if get_settings().cleanup_worker_enabled:
                app.state.cleanup.stop()


settings = get_settings()
app = FastAPI(title="media-bridge", lifespan=lifespan)
app.add_middleware(
    SessionMiddleware,
    secret_key=settings.session_secret,
    https_only=True,
    same_site="lax",
    max_age=60 * 60 * 24 * 14,
)


def get_http(request: Request) -> httpx.Client:
    return request.app.state.http


DB = Annotated[Session, Depends(get_db)]
Http = Annotated[httpx.Client, Depends(get_http)]


def current_user(request: Request, db: Session) -> User | None:
    uid = request.session.get("uid")
    return db.get(User, uid) if uid else None


def page(body: str) -> HTMLResponse:
    return HTMLResponse(
        "<!doctype html><html><head><meta charset='utf-8'>"
        "<meta name='viewport' content='width=device-width,initial-scale=1'>"
        "<title>media-bridge</title></head>"
        f"<body style='font-family:system-ui;max-width:40rem;margin:2rem auto;padding:0 1rem'>"
        f"<h1>media-bridge</h1>{body}"
        "<p><small>Built on the Buffer API.</small></p></body></html>"
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "buffer_rate_limit_min_remaining": buffer_client.rate_limits.min_remaining,
    }


@app.get("/")
def index(request: Request, db: DB, http: Http):
    user = current_user(request, db)
    if user is None or user.disconnected_at is not None:
        return page("<p><a href='/login'>Connect your Buffer account</a></p>")

    try:
        channels = _get_channels_cached(db, user, http)
    except oauth.ReauthRequired:
        return page("<p>Your Buffer connection expired. <a href='/login'>Reconnect</a></p>")
    except buffer_client.BufferRateLimited as exc:
        return page(f"<p>Buffer's rate limit was reached. Try again in {exc.retry_after}s.</p>")

    items = "".join(
        f"<li>{escape(c.get('displayName') or c['name'])} ({escape(c['service'])})"
        f"{' — disconnected' if c.get('isDisconnected') else ''}</li>"
        for c in channels
    )
    return page(
        f"<p>Connected to Buffer.</p><h2>Your channels</h2><ul>{items or '<li>none</li>'}</ul>"
        "<form method='post' action='/logout'><button>Log out</button></form>"
    )


def _get_channels_cached(db: Session, user: User, http: httpx.Client) -> list[dict]:
    cached = _channel_cache.get(user.id)
    if cached and time.monotonic() - cached[0] < CHANNEL_CACHE_TTL:
        return cached[1]
    token = oauth.get_access_token(db, user, http)
    try:
        channels = buffer_client.get_channels(http, token, user.buffer_org_id)
    except buffer_client.BufferUnauthorized as exc:
        oauth.mark_disconnected(db, user)
        raise oauth.ReauthRequired(str(exc)) from exc
    _channel_cache[user.id] = (time.monotonic(), channels)
    return channels


@app.get("/login")
def login():
    state = secrets.token_urlsafe(32)
    verifier, challenge = oauth.new_pkce_pair()
    resp = RedirectResponse(oauth.authorize_url(state, challenge), status_code=302)
    resp.set_cookie(
        OAUTH_TX_COOKIE,
        encrypt(json.dumps({"state": state, "verifier": verifier})),
        max_age=OAUTH_TX_TTL,
        httponly=True,
        secure=True,
        samesite="lax",
    )
    return resp


@app.get("/callback")
def callback(request: Request, db: DB, http: Http):
    params = request.query_params
    if params.get("error"):
        return page(
            f"<p>Buffer did not connect: {escape(params['error'])}.</p>"
            "<p><a href='/login'>Try again</a></p>"
        )

    raw_tx = request.cookies.get(OAUTH_TX_COOKIE)
    try:
        tx = json.loads(decrypt(raw_tx, ttl=OAUTH_TX_TTL)) if raw_tx else None
    except InvalidToken:
        tx = None
    if not tx or not secrets.compare_digest(tx["state"], params.get("state", "")):
        return page("<p>Login session expired or invalid. <a href='/login'>Start again</a></p>")

    try:
        tokens = oauth.exchange_code(params.get("code", ""), tx["verifier"], http)
        account = buffer_client.get_account(http, tokens["access_token"])
    except (oauth.OAuthError, buffer_client.BufferError, httpx.HTTPError) as exc:
        log.warning("OAuth callback failed: %s", exc)
        return page("<p>Could not finish connecting to Buffer. <a href='/login'>Try again</a></p>")

    orgs = account.get("organizations") or []
    user = db.execute(
        select(User).where(User.buffer_account_id == account["id"])
    ).scalar_one_or_none()
    if user is None:
        user = User(buffer_account_id=account["id"])
        db.add(user)
    # Buffer users can have several orgs; the first one is enough for now.
    user.buffer_org_id = orgs[0]["id"] if orgs else None
    user.disconnected_at = None
    db.flush()
    oauth.store_tokens(db, user, tokens)
    db.commit()
    _channel_cache.pop(user.id, None)

    if not tokens.get("refresh_token"):
        log.warning("Buffer issued no refresh token; is offline_access enabled on the client?")

    request.session["uid"] = user.id
    resp = RedirectResponse("/", status_code=302)
    resp.delete_cookie(OAUTH_TX_COOKIE)
    return resp


@app.post("/logout")
def logout(request: Request):
    request.session.clear()
    return RedirectResponse("/", status_code=303)


# --- JSON API (used by the upload page and, later, agents) ---------------------------


def require_user(request: Request, db: DB) -> User:
    user = current_user(request, db)
    if user is None or user.disconnected_at is not None:
        raise HTTPException(401, "Connect your Buffer account first.")
    return user


CurrentUser = Annotated[User, Depends(require_user)]


def _owned_file(db: Session, user: User, file_id: str) -> MediaFile:
    f = db.get(MediaFile, file_id)
    if f is None or f.user_id != user.id:
        raise HTTPException(404, "File not found.")
    return f


def _file_json(f: MediaFile) -> dict:
    return {
        "id": f.id,
        "url": f.public_url if f.state in (FileState.UPLOADED, FileState.HELD) else None,
        "state": f.state.value,
        "content_type": f.content_type,
        "size_bytes": f.size_bytes,
        "buffer_post_id": f.buffer_post_id,
        "channel_id": f.channel_id,
        "post_status": f.last_post_status,
        "due_at": f.due_at,
        "next_check_at": f.next_check_at,
        "expires_at": f.ttl_expires_at,
        "created_at": f.created_at,
        "purged_at": f.purged_at,
    }


@app.get("/api/files")
def list_files(db: DB, user: CurrentUser) -> list[dict]:
    files = db.execute(
        select(MediaFile).where(MediaFile.user_id == user.id).order_by(MediaFile.created_at.desc())
    ).scalars()
    return [_file_json(f) for f in files]


@app.post("/api/files", status_code=201)
def upload(file: UploadFile, request: Request, db: DB, user: CurrentUser) -> dict:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    try:
        f = media.upload_file(db, user, data)
    except media.UploadRejected as exc:
        raise HTTPException(400, str(exc)) from exc
    request.app.state.cleanup.poke()
    return _file_json(f)


class PostRequest(BaseModel):
    channel_id: str = Field(pattern=r"^[a-f0-9]{24}$")
    text: str = Field(max_length=3000)
    mode: str = Field(pattern=r"^(queue|schedule|now|draft)$")
    alt_text: str | None = Field(default=None, max_length=1000)
    due_at: datetime | None = None  # ISO 8601 with offset; required for "schedule"


@app.post("/api/files/{file_id}/post")
def create_post(
    file_id: str, body: PostRequest, request: Request, db: DB, http: Http, user: CurrentUser
) -> dict:
    f = _owned_file(db, user, file_id)
    if body.due_at is not None and body.due_at.tzinfo is None:
        raise HTTPException(400, "due_at needs a timezone offset.")
    try:
        f = media.post_file(
            db,
            http,
            user,
            f,
            channel_id=body.channel_id,
            text=body.text,
            mode=body.mode,
            alt_text=body.alt_text,
            due_at=body.due_at if body.mode == "schedule" else None,
        )
    except media.PostFailed as exc:
        raise HTTPException(422, str(exc)) from exc
    except oauth.ReauthRequired as exc:
        raise HTTPException(401, "Your Buffer connection expired. Reconnect and retry.") from exc
    except buffer_client.BufferRateLimited as exc:
        raise HTTPException(
            429, f"Buffer's rate limit was reached. Try again in {exc.retry_after}s."
        ) from exc
    request.app.state.cleanup.poke()
    return _file_json(f)


@app.post("/api/files/{file_id}/delete")
def delete_now(file_id: str, db: DB, user: CurrentUser) -> dict:
    """Delete the file immediately. If its post is still pending, the post loses its image."""
    f = _owned_file(db, user, file_id)
    if f.state not in (FileState.UPLOADED, FileState.HELD):
        return {**_file_json(f), "warning": None}
    broke_post = media.post_still_needs_file(f)
    media.remove_file(
        db,
        f,
        state=FileState.PURGED,
        decision="purge",
        reason="user_deleted",
        post_status=f.last_post_status,
    )
    warning = (
        "The Buffer post still needs this image and will fail when it publishes. "
        "Delete or edit the post in Buffer."
        if broke_post
        else None
    )
    return {**_file_json(f), "warning": warning}
