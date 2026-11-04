import json
import logging
import secrets
import time
from contextlib import asynccontextmanager
from datetime import datetime
from pathlib import Path
from typing import Annotated

import httpx
from fastapi import Depends, FastAPI, HTTPException, Request, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from pydantic import BaseModel, Field
from sqlalchemy import delete, select
from sqlalchemy.orm import Session
from starlette.middleware.sessions import SessionMiddleware

from app import buffer_client, media, oauth
from app.cleanup import CleanupWorker
from app.config import get_settings
from app.crypto import InvalidToken, decrypt, encrypt
from app.db import CleanupEvent, FileState, MediaFile, OAuthToken, User, get_db, init_db

# Uvicorn only configures its own loggers; this makes app.* (e.g. cleanup) show up too.
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
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
_HERE = Path(__file__).parent
app.mount("/static", StaticFiles(directory=_HERE / "static"), name="static")
templates = Jinja2Templates(directory=_HERE / "templates")
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


def page(request: Request, title: str, message: str, status_code: int = 200) -> HTMLResponse:
    """A simple message page (login errors and the like). `message` is plain text."""
    return templates.TemplateResponse(
        request, "message.html", {"title": title, "message": message}, status_code=status_code
    )


@app.get("/health")
def health() -> dict:
    return {
        "status": "ok",
        "buffer_rate_limit_min_remaining": buffer_client.rate_limits.min_remaining,
    }


@app.get("/")
def index(request: Request, db: DB):
    user = current_user(request, db)
    if user is None or user.disconnected_at is not None:
        return templates.TemplateResponse(request, "landing.html", {"reconnect": user is not None})
    s = get_settings()
    return templates.TemplateResponse(
        request,
        "app.html",
        {
            "max_upload_mb": s.max_upload_mb,
            "unattached_ttl_hours": s.unattached_ttl_hours,
            "media_ttl_days": s.media_ttl_days,
        },
    )


@app.get("/privacy")
def privacy(request: Request):
    s = get_settings()
    return templates.TemplateResponse(
        request,
        "privacy.html",
        {"unattached_ttl_hours": s.unattached_ttl_hours, "media_ttl_days": s.media_ttl_days},
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
        return page(request, "Not connected", f"Buffer did not connect ({params['error']}).")

    raw_tx = request.cookies.get(OAUTH_TX_COOKIE)
    try:
        tx = json.loads(decrypt(raw_tx, ttl=OAUTH_TX_TTL)) if raw_tx else None
    except InvalidToken:
        tx = None
    if not tx or not secrets.compare_digest(tx["state"], params.get("state", "")):
        return page(request, "Login expired", "The login took too long or was opened twice.")

    try:
        tokens = oauth.exchange_code(params.get("code", ""), tx["verifier"], http)
        account = buffer_client.get_account(http, tokens["access_token"])
    except (oauth.OAuthError, buffer_client.BufferError, httpx.HTTPError) as exc:
        log.warning("OAuth callback failed: %s", exc)
        return page(request, "Not connected", "Could not finish connecting to Buffer.")

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


def _file_json(f: MediaFile, removed_reason: str | None = None) -> dict:
    return {
        "removed_reason": removed_reason,
        "original_name": f.original_name,
        "post_url": f.post_url,
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
    files = (
        db.execute(
            select(MediaFile)
            .where(MediaFile.user_id == user.id)
            .order_by(MediaFile.created_at.desc())
        )
        .scalars()
        .all()
    )
    # Why each removed file was removed: its final purge/expire event.
    reasons = dict(
        db.execute(
            select(CleanupEvent.media_file_id, CleanupEvent.reason)
            .join(MediaFile, MediaFile.id == CleanupEvent.media_file_id)
            .where(MediaFile.user_id == user.id, CleanupEvent.decision != "keep")
        ).all()
    )
    return [_file_json(f, reasons.get(f.id)) for f in files]


@app.get("/api/channels")
def list_channels(db: DB, http: Http, user: CurrentUser) -> list[dict]:
    try:
        channels = _get_channels_cached(db, user, http)
    except oauth.ReauthRequired as exc:
        raise HTTPException(401, "Your Buffer connection expired. Reconnect to continue.") from exc
    except buffer_client.BufferRateLimited as exc:
        raise HTTPException(
            429, f"Buffer's rate limit was reached. Try again in {exc.retry_after}s."
        ) from exc
    return [c for c in channels if not c.get("isLocked")]


@app.post("/api/files", status_code=201)
def upload(file: UploadFile, request: Request, db: DB, user: CurrentUser) -> dict:
    limit = get_settings().max_upload_mb * 1024 * 1024
    data = file.file.read(limit + 1)
    try:
        f = media.upload_file(db, user, data, file.filename)
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
    return {**_file_json(f, "user_deleted"), "warning": warning}


@app.post("/api/account/delete")
def delete_account(request: Request, db: DB, user: CurrentUser) -> dict:
    """Delete every stored image and every row about this user. Buffer posts are untouched."""
    for f in (
        db.execute(
            select(MediaFile).where(
                MediaFile.user_id == user.id,
                MediaFile.state.in_((FileState.UPLOADED, FileState.HELD)),
            )
        )
        .scalars()
        .all()
    ):
        media.remove_file(db, f, state=FileState.PURGED, decision="purge", reason="account_deleted")
    file_ids = select(MediaFile.id).where(MediaFile.user_id == user.id)
    db.execute(delete(CleanupEvent).where(CleanupEvent.media_file_id.in_(file_ids)))
    db.execute(delete(MediaFile).where(MediaFile.user_id == user.id))
    db.execute(delete(OAuthToken).where(OAuthToken.user_id == user.id))
    db.execute(delete(User).where(User.id == user.id))
    db.commit()
    _channel_cache.pop(user.id, None)
    request.session.clear()
    return {"deleted": True}
